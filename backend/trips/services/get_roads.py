"""
Routing = asking OSRM how to drive from A to B.

we want 3 different roads. OSRM can give "alternatives" but sometimes it only
finds 1 or 2. when that happens we make extra ones by forcing the route to go
through a spot off to the side (a "via" point). its like telling your GPS
"go through that town over there".
"""
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import OutsideApiBroke, TripPlanningError
from .map_math import (
    add_up_the_miles,
    find_spot_at_mile,
    how_far_apart,
    quick_how_far,
    walk_from_here,
    which_way_is_it,
    METERS_PER_MILE,
)

log = logging.getLogger(__name__)

HOW_MANY_ROADS = 3
SAME_ROAD_OVERLAP = 0.85  # if 85% of a road sits on top of another road, its basically the same road
TOO_LONG_DETOUR = 1.5  # dont suggest a road thats 50% slower, thats just silly


def ask_osrm(points, want_alternatives):
    """
    calls OSRM once. points is a list of (lat, lon). OSRM wants lon,lat order
    (backwards from everyone else, classic) so we flip them.
    """
    coord_text = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
    url = f"{settings.OSRM_BASE_URL.rstrip('/')}/route/v1/driving/{coord_text}"
    params = {
        "alternatives": "3" if want_alternatives else "false",
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "annotations": "duration,distance",
    }
    cache_key = "osrm:" + hashlib.sha1((coord_text + params["alternatives"]).encode()).hexdigest()
    remembered = cache.get(cache_key)
    if remembered is not None:
        return remembered
    try:
        resp = requests.get(url, params=params, timeout=settings.HTTP_TIMEOUT_SECONDS)
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise OutsideApiBroke(f"Routing service (OSRM) failed: {exc}") from exc

    if data.get("code") != "Ok":
        if data.get("code") in {"NoRoute", "NoSegment"}:
            raise TripPlanningError("No drivable road between those places (is there an ocean in the way?).")
        raise OutsideApiBroke(f"Routing service said: {data.get('message') or data.get('code')}")
    routes = data.get("routes", [])
    cache.set(cache_key, routes, 60 * 30)
    return routes


def clean_up_road(raw, source):
    """
    turns OSRM's answer into our own simple road dict.
    OSRM speaks meters + seconds, we speak miles + seconds (we're american truckers today).
    """
    coords = [[lat, lon] for lon, lat in raw["geometry"]["coordinates"]]
    cum_miles = add_up_the_miles(coords)

    # per-segment drive times from OSRM. only trust them if they line up 1:1 with the dots
    seg_seconds = []
    for leg in raw.get("legs", []):
        seg_seconds.extend((leg.get("annotation") or {}).get("duration", []))
    total_seconds = float(raw["duration"]) * settings.TRUCK_DURATION_FACTOR

    if len(seg_seconds) == len(coords) - 1 and sum(seg_seconds) > 0:
        scale = total_seconds / sum(seg_seconds)
        cum_seconds = [0.0]
        for s in seg_seconds:
            cum_seconds.append(cum_seconds[-1] + s * scale)
        eta_method = "osrm-segment-durations"
    else:
        # backup plan: assume the truck goes the same speed the whole way
        total_miles = cum_miles[-1] or 1.0
        cum_seconds = [total_seconds * m / total_miles for m in cum_miles]
        eta_method = "distance-fraction"

    return {
        "source": source,
        "coords": coords,
        "cum_miles": cum_miles,
        "cum_seconds": cum_seconds,
        "distance_miles": float(raw["distance"]) / METERS_PER_MILE,
        "duration_seconds": total_seconds,
        "eta_method": eta_method,
    }


def check_if_same_road(road_a, road_b, samples=40):
    """
    checks how much of road_a sits right on top of road_b (0.0 to 1.0).
    we drop dots every so often along road_a and see if road_b is close (<1 mile).
    """
    b_coords = road_b["coords"][:: max(1, len(road_b["coords"]) // 1500)]
    total = road_a["cum_miles"][-1]
    if total <= 0:
        return 1.0
    hits = 0
    idx = 0
    for k in range(1, samples):
        lat, lon, idx = find_spot_at_mile(road_a["coords"], road_a["cum_miles"], total * k / samples, idx)
        if any(quick_how_far(lat, lon, blat, blon) < 1.0 for blat, blon in b_coords):
            hits += 1
    return hits / (samples - 1)


def make_wiggle_spots(main_road):
    """
    makes some "go through here" spots off to the side of the main road, so
    OSRM is forced to find a different way. we try left and right of the middle,
    and also around the 1/3 and 2/3 marks.
    """
    coords, cum = main_road["coords"], main_road["cum_miles"]
    total = cum[-1]
    start, end = coords[0], coords[-1]
    straight = how_far_apart(start[0], start[1], end[0], end[1])
    push = max(8.0, min(90.0, straight * 0.18))
    heading = which_way_is_it(start[0], start[1], end[0], end[1])

    spots = []
    for fraction in (0.5, 0.35, 0.65):
        lat, lon, _ = find_spot_at_mile(coords, cum, total * fraction)
        for side in (90, -90):
            spots.append(walk_from_here(lat, lon, heading + side, push))
    return spots


def make_roads_wiggle(origin, dest, roads):
    """
    if OSRM didnt give us 3 roads, we make more using wiggle spots.
    we ask OSRM for all the wiggle roads at the same time (in parallel) cuz its faster.
    """
    main = roads[0]
    spots = make_wiggle_spots(main)

    def try_one(spot):
        try:
            found = ask_osrm([(origin["lat"], origin["lon"]), spot, (dest["lat"], dest["lon"])], False)
            return clean_up_road(found[0], "via-detour") if found else None
        except TripPlanningError as exc:  # also catches OutsideApiBroke
            log.info("wiggle road failed: %s", exc)
            return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        candidates = [c for c in pool.map(try_one, spots) if c]

    # try the fastest wiggle roads first, those are the ones a real driver might take
    candidates.sort(key=lambda r: r["duration_seconds"])
    for road in candidates:
        if len(roads) >= HOW_MANY_ROADS:
            break
        if road["duration_seconds"] > main["duration_seconds"] * TOO_LONG_DETOUR:
            continue
        if any(check_if_same_road(road, other) > SAME_ROAD_OVERLAP for other in roads):
            continue
        roads.append(road)
    return roads


def get_the_roads(origin, dest):
    """
    the main thing: get up to 3 different roads from origin to dest.
    returns (roads, warnings)
    """
    warnings = []
    raw = ask_osrm([(origin["lat"], origin["lon"]), (dest["lat"], dest["lon"])], True)
    if not raw:
        raise TripPlanningError("OSRM found no routes.")
    roads = [clean_up_road(raw[0], "osrm-primary")]
    for alt in raw[1:]:
        road = clean_up_road(alt, "osrm-alternative")
        if all(check_if_same_road(road, other) <= SAME_ROAD_OVERLAP for other in roads):
            roads.append(road)
    roads = roads[:HOW_MANY_ROADS]

    if len(roads) < HOW_MANY_ROADS:
        roads = make_roads_wiggle(origin, dest, roads)
    if len(roads) < HOW_MANY_ROADS:
        warnings.append(
            f"Only {len(roads)} meaningfully different route(s) exist between these points; showing what we found."
        )
    return roads, warnings
