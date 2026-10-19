from datetime import datetime, timezone

from django.test import SimpleTestCase

from trips.services.check_points import count_scary_miles, make_check_points
from trips.services.get_weather import weather_at_time
from trips.services.map_math import add_up_the_miles, squish_the_line
from trips.services.pick_road import pick_best_road


def fake_road(label, duration, severe=0.0, high=0.0, avg=1.0):
    return {
        "label": label,
        "duration_seconds": duration,
        "summary": {"severe_miles": severe, "high_miles": high, "avg_risk": avg, "has_no_travel": False},
    }


class PickBestRoadTest(SimpleTestCase):
    def test_fewest_severe_miles_beats_faster(self):
        ranked, reason = pick_best_road([fake_road("A", 3600, severe=20), fake_road("B", 7200, severe=0, high=50)])
        self.assertEqual(ranked[0]["label"], "B")
        self.assertIn("Severe", reason)

    def test_high_miles_break_severe_tie(self):
        ranked, _ = pick_best_road([fake_road("A", 3600, high=30), fake_road("B", 5000, high=10)])
        self.assertEqual(ranked[0]["label"], "B")

    def test_avg_risk_then_time(self):
        ranked, _ = pick_best_road([fake_road("A", 3600, avg=1.5), fake_road("B", 5000, avg=1.2)])
        self.assertEqual(ranked[0]["label"], "B")
        ranked, reason = pick_best_road([fake_road("A", 5000), fake_road("B", 3600)])
        self.assertEqual(ranked[0]["label"], "B")
        self.assertIn("fastest", reason)
        self.assertTrue(ranked[0]["recommended"])
        self.assertFalse(ranked[1]["recommended"])


class CheckPointsTest(SimpleTestCase):
    def setUp(self):
        # a straight-ish road going north ~69 miles per degree of latitude
        coords = [[40.0 + i * 0.1, -100.0] for i in range(11)]  # ~69 miles total
        cum = add_up_the_miles(coords)
        self.road = {"coords": coords, "cum_miles": cum, "cum_seconds": [m / 60 * 3600 for m in cum]}  # 60 mph

    def test_points_every_n_miles_and_eta(self):
        dep = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        pts = make_check_points(self.road, 10, dep)
        self.assertEqual(pts[0]["mile"], 0)
        self.assertAlmostEqual(pts[1]["mile"], 10)
        self.assertAlmostEqual(pts[-1]["mile"], self.road["cum_miles"][-1])
        self.assertAlmostEqual(pts[1]["hours_from_departure"], 10 / 60, places=3)
        # all the owned miles should add up to the whole road
        self.assertAlmostEqual(sum(p["miles_covered"] for p in pts), self.road["cum_miles"][-1], places=6)

    def test_count_scary_miles(self):
        cps = [
            {"miles_covered": 10, "risk": {"level": "Low"}},
            {"miles_covered": 10, "risk": {"level": "Severe"}},
            {"miles_covered": 5, "risk": {"level": "No Travel"}},
            {"miles_covered": 5, "risk": {"level": "High"}},
        ]
        s = count_scary_miles(cps)
        self.assertEqual(s["severe_miles"], 15)
        self.assertEqual(s["high_miles"], 5)
        self.assertTrue(s["has_no_travel"])
        self.assertAlmostEqual(s["avg_risk"], (10 * 1 + 10 * 4 + 5 * 5 + 5 * 3) / 30, places=3)


class WeatherMathTest(SimpleTestCase):
    def test_interpolates_between_hours(self):
        t0 = int(datetime(2026, 1, 1, 0, tzinfo=timezone.utc).timestamp())
        series = {
            "times": [t0, t0 + 3600],
            "wind_mph": [10.0, 20.0],
            "gust_mph": [0.0, 0.0],
            "rain_in_hr": [0.0, 0.2],
            "snow_in_hr": [0.0, 0.0],
            "temp_f": [30.0, 40.0],
        }
        wx = weather_at_time(series, datetime(2026, 1, 1, 0, 30, tzinfo=timezone.utc))
        self.assertAlmostEqual(wx["wind_mph"], 15.0)
        self.assertAlmostEqual(wx["rain_in_hr"], 0.1)

    def test_squish_keeps_ends(self):
        line = [[0, i * 0.001] for i in range(100)]
        squished = squish_the_line(line)
        self.assertEqual(squished, [line[0], line[-1]])
