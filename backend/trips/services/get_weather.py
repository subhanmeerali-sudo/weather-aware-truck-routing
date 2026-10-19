"""
Weather from Open-Meteo (free, no key!).

we ask for hourly weather for a bunch of spots at once (Open-Meteo lets you
send many lat/lons in one request, which is way faster than 1 by 1).

units: we ask for the default metric units and convert ourselves so its
super clear what is going on:
    wind:      km/h -> mph       (x 0.621371)
    rain:      mm   -> inches    (/ 25.4)    rain + showers = "rain" for us
    snowfall:  cm   -> inches    (/ 2.54)    (Open-Meteo snowfall is in cm, not mm!)

Open-Meteo hourly rain/snow at hour T is the total for the hour BEFORE T,
which is basically an in/hr rate. we interpolate between hours to the exact ETA.
"""
import hashlib
import logging
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, timezone

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import OutsideApiBroke
from .map_math import mix_two_numbers

log = logging.getLogger(__name__)

KMH_TO_MPH = 0.621371
MM_TO_INCHES = 1 / 25.4
CM_TO_INCHES = 1 / 2.54

SPOTS_PER_REQUEST = 60  # keeps the URL short enough
HOURLY_STUFF = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall,temperature_2m"


def round_spot(lat, lon):
    """rounds a spot to ~1 km so nearby spots share the same weather lookup"""
    return (round(lat, 2), round(lon, 2))


def ask_open_meteo(spots, start_hour, end_hour):
    """one request to Open-Meteo for a small group of spots"""
    params = {
        "latitude": ",".join(f"{lat:.2f}" for lat, _ in spots),
        "longitude": ",".join(f"{lon:.2f}" for _, lon in spots),
        "hourly": HOURLY_STUFF,
        "timezone": "GMT",
        "timeformat": "unixtime",
        "start_hour": start_hour.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": end_hour.strftime("%Y-%m-%dT%H:%M"),
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }
    cache_key = "wx:" + hashlib.sha1(
        f"{params['latitude']}|{params['longitude']}|{params['start_hour']}|{params['end_hour']}".encode()
    ).hexdigest()
    remembered = cache.get(cache_key)
    if remembered is not None:
        return remembered

    last_error = None
    for attempt in range(2):  # try twice, sometimes the internet hiccups
        try:
            resp = requests.get(settings.OPEN_METEO_URL, params=params, timeout=settings.HTTP_TIMEOUT_SECONDS)
            if resp.status_code == 429:
                raise OutsideApiBroke("Open-Meteo rate limit hit (too many requests). Wait a minute and try again.")
            data = resp.json()
            if isinstance(data, dict) and data.get("error"):
                raise OutsideApiBroke(f"Open-Meteo said: {data.get('reason')}")
            answers = data if isinstance(data, list) else [data]
            cache.set(cache_key, answers, 60 * 20)
            return answers
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            log.warning("open-meteo attempt %s failed: %s", attempt + 1, exc)
    raise OutsideApiBroke(f"Weather service (Open-Meteo) failed: {last_error}")


def turn_into_truck_units(hourly):
    """converts one spot's hourly weather into mph + inches per hour"""

    def safe(name):
        return [0.0 if v is None else float(v) for v in hourly.get(name, [])]

    wind = safe("wind_speed_10m")
    gust = safe("wind_gusts_10m")
    rain = safe("rain")
    showers = safe("showers") or [0.0] * len(rain)
    snow = safe("snowfall")
    temp = safe("temperature_2m")
    return {
        "times": [int(t) for t in hourly.get("time", [])],
        "wind_mph": [w * KMH_TO_MPH for w in wind],
        "gust_mph": [g * KMH_TO_MPH for g in gust],
        "rain_in_hr": [(r + s) * MM_TO_INCHES for r, s in zip(rain, showers)],
        "snow_in_hr": [s * CM_TO_INCHES for s in snow],
        "temp_f": [c * 9 / 5 + 32 for c in temp],
    }


def get_the_weather(spots, start_utc, end_utc):
    """
    gets hourly weather for every spot between start and end.
    returns a dict: rounded spot -> hourly series (in truck units)
    """
    start_hour = start_utc.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    end_hour = end_utc.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    unique = list(dict.fromkeys(round_spot(lat, lon) for lat, lon in spots))
    groups = [unique[i : i + SPOTS_PER_REQUEST] for i in range(0, len(unique), SPOTS_PER_REQUEST)]

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda g: ask_open_meteo(g, start_hour, end_hour), groups))

    weather = {}
    for group, answers in zip(groups, results):
        for spot, answer in zip(group, answers):
            weather[spot] = turn_into_truck_units(answer.get("hourly", {}))
    return weather


def weather_at_time(series, when_utc):
    """
    figures out the weather at an exact time by mixing the two closest hours.
    like if you get there at 2:30, its halfway between the 2:00 and 3:00 weather.
    """
    times = series["times"]
    if not times:
        return {"wind_mph": 0.0, "gust_mph": 0.0, "rain_in_hr": 0.0, "snow_in_hr": 0.0, "temp_f": None}
    t = when_utc.timestamp()
    pos = (t - times[0]) / 3600.0
    pos = max(0.0, min(len(times) - 1.0, pos))
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(times) - 1)
    frac = pos - lo
    out = {}
    for key in ("wind_mph", "gust_mph", "rain_in_hr", "snow_in_hr", "temp_f"):
        values = series[key]
        if not values:
            out[key] = None
            continue
        out[key] = mix_two_numbers(values[lo], values[hi], frac)
    return out


def look_up_weather(weather, lat, lon, when_utc):
    """shortcut: find the right spot's series and mix to the exact time"""
    return weather_at_time(weather[round_spot(lat, lon)], when_utc)


def as_utc(dt):
    """makes sure a time has a timezone (UTC if it didnt have one)"""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def iso(dt):
    return as_utc(dt).replace(microsecond=0).isoformat().replace("+00:00", "Z")

