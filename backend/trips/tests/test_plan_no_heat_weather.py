"""
makes sure the server only asks for weather at the checkpoints now, and NOT
for the ~140 heatmap dots (the browser does those so Render doesnt get a 429).
"""
from datetime import datetime, timedelta, timezone
from unittest import mock

from django.test import SimpleTestCase

from trips.services import plan_trip as plan_module
from trips.services.get_weather import round_spot
from trips.services.map_math import add_up_the_miles

DENVER = {"query": "Denver", "name": "Denver", "lat": 39.7392, "lon": -104.9903}
SLC = {"query": "SLC", "name": "Salt Lake City", "lat": 40.7608, "lon": -111.8910}


def fake_road(wiggle):
    """a pretend road from Denver to SLC with a little bend in the middle"""
    coords = []
    for i in range(41):
        f = i / 40
        lat = DENVER["lat"] + (SLC["lat"] - DENVER["lat"]) * f + wiggle * (1 - abs(0.5 - f) * 2)
        lon = DENVER["lon"] + (SLC["lon"] - DENVER["lon"]) * f
        coords.append((lat, lon))
    cum_miles = add_up_the_miles(coords)
    total_seconds = cum_miles[-1] / 60 * 3600  # 60 mph
    return {
        "source": "test",
        "coords": coords,
        "cum_miles": cum_miles,
        "cum_seconds": [m / 60 * 3600 for m in cum_miles],
        "distance_miles": cum_miles[-1],
        "duration_seconds": total_seconds,
        "eta_method": "test",
    }


def fake_weather(spots, start_utc, end_utc):
    """calm weather for every spot we get asked about"""
    t0 = int(start_utc.replace(minute=0, second=0, microsecond=0).timestamp()) - 3600
    hours = int((end_utc - start_utc).total_seconds() // 3600) + 4
    series = {
        "times": [t0 + 3600 * h for h in range(hours)],
        "wind_mph": [5.0] * hours,
        "gust_mph": [8.0] * hours,
        "rain_in_hr": [0.0] * hours,
        "snow_in_hr": [0.0] * hours,
        "temp_f": [50.0] * hours,
    }
    return {round_spot(lat, lon): series for lat, lon in spots}


class PlanSkipsHeatWeatherTest(SimpleTestCase):
    def setUp(self):
        self.departure = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1)

    @mock.patch.object(plan_module, "get_the_weather", side_effect=fake_weather)
    @mock.patch.object(plan_module, "get_the_roads", side_effect=lambda o, d: ([fake_road(0), fake_road(0.4), fake_road(-0.4)], []))
    @mock.patch.object(plan_module, "find_where_place_is", side_effect=lambda t: DENVER if "Denver" in t else SLC)
    def test_only_checkpoints_get_weather(self, _places, _roads, weather_mock):
        plan = plan_module.plan_the_trip("Denver, CO", "Salt Lake City, UT", self.departure, 35000, 50)

        # only ONE weather ask, and only checkpoint spots in it
        self.assertEqual(weather_mock.call_count, 1)
        asked_spots = weather_mock.call_args[0][0]
        checkpoint_spots = [(cp["lat"], cp["lon"]) for r in plan["routes"] for cp in r["checkpoints"]]
        self.assertEqual(len(asked_spots), len(checkpoint_spots))
        unique = {round_spot(lat, lon) for lat, lon in asked_spots}
        self.assertLessEqual(len(unique), 40)  # fits in one Open-Meteo request

        # the window is just the trip, not +48h anymore
        _, start, end = weather_mock.call_args[0]
        longest = max(r["duration_seconds"] for r in plan["routes"])
        self.assertAlmostEqual((end - start).total_seconds(), longest, delta=2)

        # heatmap: dots + times, but the weather is left for the browser
        heat = plan["heatmap"]
        self.assertTrue(heat["needs_client_weather"])
        self.assertGreater(len(heat["points"]), 0)
        self.assertEqual(len(heat["hours"]), 49)
        self.assertEqual(len(heat["times"]), 49)
        for key in ("wind_mph", "rain_in_hr", "snow_in_hr", "risk"):
            self.assertEqual(heat[key], [])

        # the normal stuff still works
        self.assertEqual(len(plan["routes"]), 3)
        self.assertIn(plan["recommendation"]["route_id"], {"a", "b", "c"})
        self.assertEqual(plan["meta"]["weather_spots"], len(unique))
        self.assertEqual(plan["routes"][0]["checkpoints"][0]["risk"]["level"], "Low")
