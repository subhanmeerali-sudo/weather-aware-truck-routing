"""
The big boss function that runs the whole trip plan, step by step:

  1. find where the places are (geocode)
  2. get 3 roads (OSRM)
  3. drop checkpoints on each road + figure out ETAs
  4. pack geometry + heat dots/times for the frontend
     (NO Open-Meteo calls here! Render shares its IP with a bunch of other
     apps so Open-Meteo keeps saying "too many requests". the browser asks
     for weather itself after this comes back.)
  5. send empty risk summaries + a provisional "best road" (shortest time).
     the frontend fills in weather, risk, and the real recommendation.
"""
import logging
import time
from datetime import datetime, timedelta, timezone

from .check_points import make_check_points
from .errors import TripPlanningError
from .find_places import find_where_place_is
from .get_roads import get_the_roads
from .get_weather import as_utc, iso
from .heat_dots import FORECAST_HOURS, make_heat_dots, make_heat_times
from .map_math import squish_the_line
from .scary_rules import SCARY_LEVELS

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


def empty_summary(checkpoint_count):
    """zeroed-out risk summary so the JSON shape stays the same until the browser fills it in"""
    return {
        "miles_by_level": {level: 0.0 for level in SCARY_LEVELS},
        "severe_miles": 0.0,
        "high_miles": 0.0,
        "no_travel_miles": 0.0,
        "avg_risk": 1.0,
        "worst_level": "Low",
        "has_no_travel": False,
        "checkpoint_count": checkpoint_count,
    }


def pack_checkpoint(cp):
    """rounds the numbers and makes times into text. weather/risk are null on purpose
    (the browser fills those in after it asks Open-Meteo itself)"""
    return {
        "index": cp["index"],
        "mile": round(cp["mile"], 1),
        "lat": round(cp["lat"], 5),
        "lon": round(cp["lon"], 5),
        "eta": iso(cp["eta"]),
        "hours_from_departure": round(cp["hours_from_departure"], 3),
        "miles_covered": round(cp["miles_covered"], 2),
        "weather": None,
        "risk": None,
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

    # step 3: checkpoints with ETAs (no weather yet)
    for road in roads:
        road["checkpoints"] = make_check_points(road, sample_miles, departure_utc)
        road["summary"] = empty_summary(len(road["checkpoints"]))

    # step 4: name the roads. provisional rank = fastest first (weather ties are all zero
    # so the real pick happens in the browser after Open-Meteo answers)
    for i, road in enumerate(roads):
        road["id"] = chr(ord("a") + i)
        road["label"] = ROAD_NAMES[i] if i < len(ROAD_NAMES) else f"Route {i + 1}"

    ranked_by_time = sorted(roads, key=lambda r: r["duration_seconds"])
    for rank, road in enumerate(ranked_by_time, start=1):
        road["rank"] = rank
        road["recommended"] = rank == 1
    provisional = ranked_by_time[0]
    provisional_reason = "Checking weather… ranking will update once the forecast lands."

    # step 5: heatmap dots + times for the slider. NO weather in here.
    heat_dots = make_heat_dots(roads)
    heat_times = make_heat_times(departure_utc)

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

    checkpoint_count = sum(len(r["checkpoints"]) for r in packed_roads)
    took = time.perf_counter() - started
    log.info(
        "planned trip %s -> %s in %.1fs (%d checkpoints, weather deferred to client)",
        origin_text,
        destination_text,
        took,
        checkpoint_count,
    )

    return {
        "origin": origin,
        "destination": destination,
        "departure": iso(departure_utc),
        "load_lbs": load_lbs,
        "sample_miles": sample_miles,
        "risk_levels": SCARY_LEVELS,
        "needs_client_weather": True,
        "routes": packed_roads,
        "recommendation": {
            "route_id": provisional["id"],
            "label": provisional["label"],
            "reason": provisional_reason,
        },
        "heatmap": {
            "hours": list(range(FORECAST_HOURS + 1)),
            "times": [iso(t) for t in heat_times],
            "points": [[lat, lon] for lat, lon in heat_dots],
            "needs_client_weather": True,
            "wind_mph": [],
            "rain_in_hr": [],
            "snow_in_hr": [],
            "risk": [],
        },
        "warnings": warnings,
        "meta": {
            "took_seconds": round(took, 2),
            "weather_spots": checkpoint_count,  # how many the browser will ask about
            "heat_dots": len(heat_dots),
            "needs_client_weather": True,
        },
    }
