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
import logging
import math
import time
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

SPOTS_PER_REQUEST = 40  # smaller groups so Open-Meteo doesnt get mad at us
HOURLY_STUFF = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall,temperature_2m"

# Open-Meteo gets grumpy (HTTP 429) if we ask too fast. so we go one at a time,
# take a little nap between asks, and if it still says "slow down" we wait
# longer and longer before trying again.
NAP_BETWEEN_ASKS = 0.6  # seconds
WAIT_TIMES_WHEN_TOO_FAST = (2, 5, 10)  # seconds, gets bigger each time
REMEMBER_WEATHER_FOR = 60 * 20  # 20 minutes


def round_spot(lat, lon):
    """rounds a spot to ~5 km so nearby spots share the same weather lookup"""
    # weather models are like 3-10 km boxes anyway so this barely changes anything
    return (round(round(lat * 20) / 20, 2), round(round(lon * 20) / 20, 2))


def memory_name(spot, start_hour, end_hour):
    """the name we save one spot's weather under in the cache"""
    return f"wx1:{spot[0]:.2f},{spot[1]:.2f}|{start_hour:%Y%m%d%H}|{end_hour:%Y%m%d%H}"


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

    last_error = None
    too_fast_count = 0
    other_fails = 0
    while True:
        try:
            resp = requests.get(settings.OPEN_METEO_URL, params=params, timeout=settings.HTTP_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            last_error = exc
            other_fails += 1
            log.warning("open-meteo attempt failed: %s", exc)
            if other_fails >= 2:  # try twice, sometimes the internet hiccups
                raise OutsideApiBroke(f"Weather service (Open-Meteo) failed: {last_error}") from exc
            time.sleep(1)
            continue

        if resp.status_code == 429:
            if too_fast_count >= len(WAIT_TIMES_WHEN_TOO_FAST):
                raise OutsideApiBroke("Open-Meteo rate limit hit (too many requests). Wait a minute and try again.")
            nap = wait_how_long(resp, too_fast_count)
            too_fast_count += 1
            log.warning("open-meteo said slow down (429), napping %.1fs (try %s)", nap, too_fast_count)
            time.sleep(nap)
            continue

        try:
            data = resp.json()
        except ValueError as exc:
            last_error = exc
            other_fails += 1
            if other_fails >= 2:
                raise OutsideApiBroke(f"Weather service (Open-Meteo) failed: {last_error}") from exc
            time.sleep(1)
            continue

        if isinstance(data, dict) and data.get("error"):
            raise OutsideApiBroke(f"Open-Meteo said: {data.get('reason')}")
        return data if isinstance(data, list) else [data]


def wait_how_long(resp, try_number):
    """how long to nap after a 429. if Open-Meteo tells us (Retry-After) we listen, kinda"""
    nap = WAIT_TIMES_WHEN_TOO_FAST[try_number]
    told_us = resp.headers.get("Retry-After") if resp is not None else None
    try:
        if told_us:
            nap = max(nap, min(float(told_us), 15.0))  # dont wait forever tho
    except ValueError:
        pass
    return nap


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

    # first check our memory (cache) so we dont ask for the same spot twice
    weather = {}
    still_need = []
    for spot in unique:
        remembered = cache.get(memory_name(spot, start_hour, end_hour))
        if remembered is not None:
            weather[spot] = remembered
        else:
            still_need.append(spot)

    groups = [still_need[i : i + SPOTS_PER_REQUEST] for i in range(0, len(still_need), SPOTS_PER_REQUEST)]
    log.info("weather: %s spots, %s from cache, %s requests", len(unique), len(weather), len(groups))

    # one group at a time (no more 4 at once, thats what got us rate limited)
    for i, group in enumerate(groups):
        if i > 0:
            time.sleep(NAP_BETWEEN_ASKS)
        answers = ask_open_meteo(group, start_hour, end_hour)
        for spot, answer in zip(group, answers):
            series = turn_into_truck_units(answer.get("hourly", {}))
            weather[spot] = series
            cache.set(memory_name(spot, start_hour, end_hour), series, REMEMBER_WEATHER_FOR)
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

