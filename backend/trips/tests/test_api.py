from unittest import mock

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from trips.services.errors import TripPlanningError


class PlanTripApiTest(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.good_ask = {
            "origin": "Denver, CO",
            "destination": "Salt Lake City, UT",
            "departure_iso": "2026-10-20T14:00:00Z",
            "load_lbs": 35000,
            "sample_miles": 25,
        }

    def test_bad_sample_interval_is_rejected(self):
        resp = self.client.post("/api/plan-trip/", {**self.good_ask, "sample_miles": 7}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("sample_miles", resp.json())

    def test_same_place_twice_is_rejected(self):
        resp = self.client.post("/api/plan-trip/", {**self.good_ask, "destination": "denver, co"}, format="json")
        self.assertEqual(resp.status_code, 400)

    @mock.patch("trips.views.plan_the_trip", return_value={"routes": []})
    def test_good_ask_calls_planner(self, fake_plan):
        resp = self.client.post("/api/plan-trip/", self.good_ask, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(fake_plan.call_args.kwargs["sample_miles"], 25)

    @mock.patch("trips.views.plan_the_trip", side_effect=TripPlanningError("nope"))
    def test_planner_errors_turn_into_json(self, _):
        resp = self.client.post("/api/plan-trip/", self.good_ask, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "nope")

    def test_health(self):
        self.assertEqual(self.client.get("/api/health/").json(), {"ok": True})
