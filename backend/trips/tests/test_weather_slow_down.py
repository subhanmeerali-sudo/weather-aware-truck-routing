from datetime import datetime, timezone
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase

from trips.services import get_weather
from trips.services.errors import OutsideApiBroke


def fake_answer(status, body=None):
    """pretend Open-Meteo answer"""
    resp = mock.Mock()
    resp.status_code = status
    resp.headers = {}
    resp.json.return_value = body
    return resp


GOOD = [{"hourly": {"time": [0, 3600], "wind_speed_10m": [10, 20]}}]
START = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
END = datetime(2026, 10, 20, 18, tzinfo=timezone.utc)


class TooFastTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @mock.patch("trips.services.get_weather.time.sleep")
    @mock.patch("trips.services.get_weather.requests.get")
    def test_waits_then_works(self, fake_get, fake_sleep):
        # first it says slow down twice, then it works
        fake_get.side_effect = [fake_answer(429), fake_answer(429), fake_answer(200, GOOD)]
        wx = get_weather.get_the_weather([(39.74, -104.99)], START, END)
        self.assertEqual(len(wx), 1)
        self.assertEqual([c.args[0] for c in fake_sleep.call_args_list], [2, 5])

    @mock.patch("trips.services.get_weather.time.sleep")
    @mock.patch("trips.services.get_weather.requests.get")
    def test_gives_up_after_too_many(self, fake_get, fake_sleep):
        fake_get.return_value = fake_answer(429)
        with self.assertRaises(OutsideApiBroke):
            get_weather.get_the_weather([(39.74, -104.99)], START, END)
        self.assertEqual(fake_get.call_count, 4)

    @mock.patch("trips.services.get_weather.time.sleep")
    @mock.patch("trips.services.get_weather.requests.get")
    def test_remembers_spots(self, fake_get, fake_sleep):
        fake_get.return_value = fake_answer(200, GOOD)
        get_weather.get_the_weather([(39.74, -104.99)], START, END)
        get_weather.get_the_weather([(39.74, -104.99)], START, END)
        self.assertEqual(fake_get.call_count, 1)  # 2nd time came from the cache
