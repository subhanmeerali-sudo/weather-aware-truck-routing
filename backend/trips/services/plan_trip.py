"""
The big boss function that runs the whole trip plan, step by step:

  1. find where the places are (geocode)
  2. get 3 roads (OSRM)
  3. drop checkpoints on each road + figure out ETAs
  4. get the weather for every checkpoint + heatmap dot (Open-Meteo, batched)
  5. decide how scary each checkpoint is
  6. pick the best road
  7. pack it all up for the frontend
"""
import logging
import time
from datetime import datetime, timedelta, timezone

from .check_points import count_scary_miles, make_check_points
from .errors import TripPlanningError
from .find_places import find_where_place_is
from .get_roads import get_the_roads
from .get_weather import as_utc, get_the_weather, iso, look_up_weather
from .heat_dots import FORECAST_HOURS, make_heat_dots, make_heat_frames
from .map_math import squish_the_line
from .pick_road import pick_best_road
from .scary_rules import SCARY_LEVELS, check_if_scary

log = logging.getLogger(__name__)

ROAD_NAMES = ["Route A", "Route B", "Route C"]
FARTHEST_FUTURE_DAYS = 10  # Open-Meteo only forecasts ~16 days and we need +48h + trip time
FARTHEST_PAST_DAYS = 3


def check_the_departure_time(departure_utc):
    """makes sure the departure time is one we can actually get weather for"""
    now = datetime.now(timezone.utc)
    if departure_utc > now + timedelta(days=FARTHEST_FUTURE_DAYS):
        raise TripPlanningError(f"Departure must be within {FARTHEST_FUTURE_DAYS} days from now (forecast limit).")
    if departure_utc < now - timedelta(days=FARTHEST_PAST_DAYS):
        raise TripPlanningError(f"Departure can't be more than {FARTHEST_PAST_DAYS} days in the past.")


def pack_checkpoint(cp):
    """rounds the numbers and makes times into text so it fits in JSON nicely"""
    wx = cp["weather"]
    return {
        "index": cp["index"],
        "mile": round(cp["mile"], 1),
        "lat": round(cp["lat"], 5),
        "lon": round(cp["lon"], 5),
        "eta": iso(cp["eta"]),
        "hours_from_departure": round(cp["hours_from_departure"], 3),
        "miles_covered": round(cp["miles_covered"], 2),
        "weather": {
            "wind_mph": round(wx["wind_mph"], 1),
            "gust_mph": round(wx["gust_mph"], 1) if wx["gust_mph"] is not None else None,
            "rain_in_hr": round(wx["rain_in_hr"], 3),
            "snow_in_hr": round(wx["snow_in_hr"], 2),
            "temp_f": round(wx["temp_f"], 1) if wx["temp_f"] is not None else None,
        },
        "risk": cp["risk"],
    }


def plan_the_trip(origin_text, destination_text, departure, load_lbs, sample_miles):
    started = time.perf_counter()
    departure_utc = as_utc(departure)
    check_the_departure_time(departure_utc)

    # step 1: where are we going
    origin = find_where_place_is(origin_text)
    destination = find_where_place_is(destination_text)

    # step 2: get the roads
    roads, warnings = get_the_roads(origin, destination)

    # step 3: checkpoints with ETAs
    for road in roads:
        road["checkpoints"] = make_check_points(road, sample_miles, departure_utc)

    # step 4: weather for everything in one big (batched) go
    heat_dots = make_heat_dots(roads)
    longest_trip = max(r["duration_seconds"] for r in roads)
    window_end = departure_utc + timedelta(seconds=longest_trip)
    window_end = max(window_end, departure_utc + timedelta(hours=FORECAST_HOURS))
    all_spots = [(cp["lat"], cp["lon"]) for r in roads for cp in r["checkpoints"]] + heat_dots
    weather = get_the_weather(all_spots, departure_utc, window_end)

    # step 5: how scary is each checkpoint
    for road in roads:
        for cp in road["checkpoints"]:
            cp["weather"] = look_up_weather(weather, cp["lat"], cp["lon"], cp["eta"])
            cp["risk"] = check_if_scary(cp["weather"], load_lbs)
        road["summary"] = count_scary_miles(road["checkpoints"])

    # step 6: name the roads (in the order OSRM gave them) and pick the winner
    for i, road in enumerate(roads):
        road["id"] = chr(ord("a") + i)
        road["label"] = ROAD_NAMES[i] if i < len(ROAD_NAMES) else f"Route {i + 1}"
    ranked, reason = pick_best_road(roads)
    best = ranked[0]

    # step 7: heatmap frames for the slider
    heat_times, frames = make_heat_frames(heat_dots, weather, departure_utc, load_lbs)

    packed_roads = []
    for road in sorted(roads, key=lambda r: r["id"]):
        packed_roads.append(
            {
                "id": road["id"],
                "label": road["label"],
                "source": road["source"],
                "rank": road["rank"],
                "recommended": road["recommended"],
                "distance_miles": round(road["distance_miles"], 1),
                "duration_seconds": round(road["duration_seconds"]),
                "duration_hours": round(road["duration_seconds"] / 3600, 2),
                "departure": iso(departure_utc),
                "arrival": iso(departure_utc + timedelta(seconds=road["duration_seconds"])),
                "eta_method": road["eta_method"],
                "geometry": [[round(lat, 5), round(lon, 5)] for lat, lon in squish_the_line(road["coords"])],
                "checkpoints": [pack_checkpoint(cp) for cp in road["checkpoints"]],
                "summary": road["summary"],
            }
        )

    took = time.perf_counter() - started
    log.info("planned trip %s -> %s in %.1fs (%d weather spots)", origin_text, destination_text, took, len(weather))

    return {
        "origin": origin,
        "destination": destination,
        "departure": iso(departure_utc),
        "load_lbs": load_lbs,
        "sample_miles": sample_miles,
        "risk_levels": SCARY_LEVELS,
        "routes": packed_roads,
        "recommendation": {"route_id": best["id"], "label": best["label"], "reason": reason},
        "heatmap": {
            "hours": list(range(FORECAST_HOURS + 1)),
            "times": [iso(t) for t in heat_times],
            "points": [[lat, lon] for lat, lon in heat_dots],
            **frames,
        },
        "warnings": warnings,
        "meta": {"took_seconds": round(took, 2), "weather_spots": len(weather)},
    }
