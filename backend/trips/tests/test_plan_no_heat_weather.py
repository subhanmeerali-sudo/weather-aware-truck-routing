"""
makes sure the server NEVER asks Open-Meteo. weather (checkpoints + heatmap)
comes from the browser so Render's shared IP doesnt get a 429.
"""
from datetime import datetime, timedelta, timezone
from unittest import mock

from django.test import SimpleTestCase

from trips.services import plan_trip as plan_module
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


class PlanSkipsAllWeatherTest(SimpleTestCase):
    def setUp(self):
        self.departure = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1)

    @mock.patch.object(plan_module, "get_the_roads", side_effect=lambda o, d: ([fake_road(0), fake_road(0.4), fake_road(-0.4)], []))
    @mock.patch.object(plan_module, "find_where_place_is", side_effect=lambda t: DENVER if "Denver" in t else SLC)
    def test_plan_never_calls_open_meteo(self, _places, _roads):
        # if plan_the_trip still imported get_the_weather somehow and called it, this would fail
        with mock.patch("trips.services.get_weather.get_the_weather") as weather_mock:
            with mock.patch("trips.services.get_weather.ask_open_meteo") as ask_mock:
                plan = plan_module.plan_the_trip("Denver, CO", "Salt Lake City, UT", self.departure, 35000, 50)

        weather_mock.assert_not_called()
        ask_mock.assert_not_called()

        # top-level flag so the UI knows to fetch weather itself
        self.assertTrue(plan["needs_client_weather"])
        self.assertTrue(plan["meta"]["needs_client_weather"])

        # heatmap: dots + times, but the weather is left for the browser
        heat = plan["heatmap"]
        self.assertTrue(heat["needs_client_weather"])
        self.assertGreater(len(heat["points"]), 0)
        self.assertEqual(len(heat["hours"]), 49)
        self.assertEqual(len(heat["times"]), 49)
        for key in ("wind_mph", "rain_in_hr", "snow_in_hr", "risk"):
            self.assertEqual(heat[key], [])

        # routes still pack geometry + checkpoints with ETAs, but no weather/risk yet
        self.assertEqual(len(plan["routes"]), 3)
        checkpoint_count = 0
        for route in plan["routes"]:
            self.assertGreater(len(route["geometry"]), 1)
            self.assertGreater(len(route["checkpoints"]), 1)
            for cp in route["checkpoints"]:
                checkpoint_count += 1
                self.assertIsNotNone(cp["eta"])
                self.assertIsNotNone(cp["lat"])
                self.assertIsNotNone(cp["lon"])
                self.assertIsNone(cp["weather"])
                self.assertIsNone(cp["risk"])
            self.assertEqual(route["summary"]["severe_miles"], 0.0)
            self.assertEqual(route["summary"]["high_miles"], 0.0)

        self.assertEqual(plan["meta"]["weather_spots"], checkpoint_count)
        self.assertIn(plan["recommendation"]["route_id"], {"a", "b", "c"})
        self.assertIn("Checking weather", plan["recommendation"]["reason"])

    def test_plan_module_does_not_import_get_the_weather(self):
        # hard guard: plan_trip must not even pull get_the_weather into its namespace
        self.assertFalse(hasattr(plan_module, "get_the_weather"))
        self.assertFalse(hasattr(plan_module, "look_up_weather"))
        self.assertFalse(hasattr(plan_module, "check_if_scary"))
