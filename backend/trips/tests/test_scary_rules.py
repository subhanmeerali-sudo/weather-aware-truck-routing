from django.test import SimpleTestCase

from trips.services.scary_rules import (
    check_if_scary,
    quick_scary_score,
    see_how_rainy,
    see_how_snowy,
    see_how_windy,
)


class WindRulesTest(SimpleTestCase):
    """making sure the wind table from the PDF works exactly right"""

    def test_wind_buckets_for_light_truck(self):
        cases = [(0, "Low"), (24.9, "Low"), (25, "Moderate"), (34.9, "Moderate"), (35, "High"),
                 (44.9, "High"), (45, "Severe"), (54.9, "Severe"), (55, "No Travel"), (80, "No Travel")]
        for mph, expected in cases:
            with self.subTest(mph=mph):
                self.assertEqual(see_how_windy(mph, 10_000)[0], expected)

    def test_55_mph_is_no_travel_for_any_load(self):
        self.assertEqual(see_how_windy(55, 0)[0], "No Travel")

    def test_heavy_truck_in_45_to_54_wind_is_no_travel(self):
        self.assertEqual(see_how_windy(47, 30_001)[0], "No Travel")
        self.assertEqual(see_how_windy(47, 30_000)[0], "Severe")  # exactly 30k is not ">30,000"

    def test_heavy_truck_in_35_to_44_wind_is_severe(self):
        self.assertEqual(see_how_windy(38, 40_001)[0], "Severe")
        self.assertEqual(see_how_windy(38, 40_000)[0], "High")


class RainAndSnowRulesTest(SimpleTestCase):
    def test_rain_buckets(self):
        cases = [(0.0, "Low"), (0.09, "Low"), (0.10, "Moderate"), (0.25, "High"), (0.49, "High"),
                 (0.50, "Severe"), (1.00, "Severe"), (1.01, "No Travel")]
        for rate, expected in cases:
            with self.subTest(rate=rate):
                self.assertEqual(see_how_rainy(rate)[0], expected)

    def test_snow_buckets(self):
        cases = [(0.0, "Low"), (0.49, "Low"), (0.5, "Moderate"), (1.0, "High"), (2.0, "Severe"),
                 (3.0, "Severe"), (3.1, "No Travel")]
        for rate, expected in cases:
            with self.subTest(rate=rate):
                self.assertEqual(see_how_snowy(rate)[0], expected)


class OverallScaryTest(SimpleTestCase):
    def test_worst_condition_wins(self):
        risk = check_if_scary({"wind_mph": 10, "rain_in_hr": 0.3, "snow_in_hr": 0.6}, 20_000)
        self.assertEqual(risk["level"], "High")
        self.assertEqual(risk["score"], 3)
        self.assertEqual(risk["snow_level"], "Moderate")
        self.assertEqual(len(risk["reasons"]), 2)

    def test_quick_score_matches_full_check(self):
        for wind, rain, snow, load in [(5, 0, 0, 0), (40, 0, 0, 45_000), (50, 0.6, 0, 35_000), (20, 0, 2.5, 0)]:
            full = check_if_scary({"wind_mph": wind, "rain_in_hr": rain, "snow_in_hr": snow}, load)
            self.assertEqual(quick_scary_score(wind, rain, snow, load), full["score"])
