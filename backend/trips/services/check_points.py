"""
Checkpoints = the spots along the road where we check the weather.

we drop one every N miles (10, 25 or 50, the user picks) plus one at the very
start and one at the very end. then we figure out WHEN the truck gets to each
one, cuz the weather at 3pm might be totally different than at 9am.
"""
from datetime import timedelta

from .map_math import find_spot_at_mile, mix_two_numbers
from .scary_rules import SCARY_LEVELS, SCARY_POINTS, SEVERE, NO_TRAVEL, HIGH


def figure_out_eta(road, mile, seg_index, departure_utc):
    """
    when does the truck reach this mile? we look at how many seconds it took
    OSRM to get to the dots on both sides of the spot and mix them.
    """
    cum_m, cum_s = road["cum_miles"], road["cum_seconds"]
    i = min(seg_index, len(cum_m) - 2) if len(cum_m) > 1 else 0
    if len(cum_m) < 2:
        return departure_utc, 0.0
    seg_len = cum_m[i + 1] - cum_m[i]
    frac = 0.0 if seg_len <= 0 else max(0.0, min(1.0, (mile - cum_m[i]) / seg_len))
    seconds = mix_two_numbers(cum_s[i], cum_s[i + 1], frac)
    return departure_utc + timedelta(seconds=seconds), seconds


def make_check_points(road, sample_miles, departure_utc):
    """
    makes the list of checkpoints for one road. each one knows its mile, spot,
    ETA, and how many miles of road it "owns" (half the gap to the one before +
    half the gap to the one after). that way adding up all the owned miles = the whole trip.
    """
    total = road["cum_miles"][-1]
    miles = []
    m = 0.0
    while m < total:
        miles.append(m)
        m += sample_miles
    miles.append(total)
    if len(miles) >= 3 and miles[-1] - miles[-2] < 0.5:
        miles.pop(-2)  # the last 2 were basically on top of each other

    points = []
    idx = 0
    for k, mile in enumerate(miles):
        lat, lon, idx = find_spot_at_mile(road["coords"], road["cum_miles"], mile, idx)
        eta, seconds = figure_out_eta(road, mile, idx, departure_utc)
        before = miles[k] - miles[k - 1] if k > 0 else 0.0
        after = miles[k + 1] - miles[k] if k < len(miles) - 1 else 0.0
        points.append(
            {
                "index": k,
                "mile": mile,
                "lat": lat,
                "lon": lon,
                "eta": eta,
                "hours_from_departure": seconds / 3600.0,
                "miles_covered": (before + after) / 2,
            }
        )
    return points


def count_scary_miles(checkpoints):
    """
    adds up how many miles of the trip are at each scary level.
    "severe miles" counts Severe AND No Travel, cuz No Travel is even worse than
    severe and it would be weird if a No Travel road looked better than a Severe one.
    """
    by_level = {level: 0.0 for level in SCARY_LEVELS}
    weighted = 0.0
    total = 0.0
    worst = SCARY_LEVELS[0]
    for cp in checkpoints:
        level = cp["risk"]["level"]
        by_level[level] += cp["miles_covered"]
        weighted += SCARY_POINTS[level] * cp["miles_covered"]
        total += cp["miles_covered"]
        if SCARY_POINTS[level] > SCARY_POINTS[worst]:
            worst = level
    avg = weighted / total if total else 1.0
    return {
        "miles_by_level": {k: round(v, 1) for k, v in by_level.items()},
        "severe_miles": round(by_level[SEVERE] + by_level[NO_TRAVEL], 1),
        "high_miles": round(by_level[HIGH], 1),
        "no_travel_miles": round(by_level[NO_TRAVEL], 1),
        "avg_risk": round(avg, 3),
        "worst_level": worst,
        "has_no_travel": by_level[NO_TRAVEL] > 0,
        "checkpoint_count": len(checkpoints),
    }
