"""
Heatmap dots for the trip corridor.

we spread dots along every road AND a bit to the left and right of it (the
"corridor"), so the heatmap looks like a wide band instead of a skinny line.
then for every hour from 0 to 48 after departure we figure out the weather
at each dot. the frontend slider just flips between these hours (fast!).
"""
from datetime import timedelta

from .get_weather import look_up_weather
from .map_math import find_spot_at_mile, walk_from_here, which_way_is_it
from .scary_rules import quick_scary_score

FORECAST_HOURS = 48
CORRIDOR_MILES = 18  # how far left/right of the road we look
MAX_DOTS = 140  # less dots = less weather asks = no rate limit


def make_heat_dots(roads, max_dots=MAX_DOTS):
    """
    makes the corridor dots. we snap them to a grid so roads that overlap
    dont make double dots (double dots = extra api calls = slow).
    """
    grid = 0.15
    while True:
        seen = {}
        for road in roads:
            coords, cum = road["coords"], road["cum_miles"]
            total = cum[-1]
            step = max(12.0, total / 22)
            m = 0.0
            idx = 0
            while m <= total + 0.01:
                lat, lon, idx = find_spot_at_mile(coords, cum, min(m, total), idx)
                a_lat, a_lon, _ = find_spot_at_mile(coords, cum, max(0.0, m - 2))
                b_lat, b_lon, _ = find_spot_at_mile(coords, cum, min(total, m + 2))
                heading = which_way_is_it(a_lat, a_lon, b_lat, b_lon)
                for side_miles in (0, CORRIDOR_MILES, -CORRIDOR_MILES):
                    if side_miles:
                        dot = walk_from_here(lat, lon, heading + 90, side_miles)
                    else:
                        dot = (lat, lon)
                    key = (round(dot[0] / grid), round(dot[1] / grid))
                    seen.setdefault(key, (round(key[0] * grid, 3), round(key[1] * grid, 3)))
                m += step
        if len(seen) <= max_dots:
            return list(seen.values())
        grid *= 1.25  # too many dots, make the grid chunkier and try again


def make_heat_frames(dots, weather, departure_utc, load_lbs):
    """
    for each hour 0..48, how windy/rainy/snowy/scary is it at each dot.
    output is arrays shaped [hour][dot] so the frontend can grab one hour super fast.
    """
    frames = {"wind_mph": [], "rain_in_hr": [], "snow_in_hr": [], "risk": []}
    times = []
    for hour in range(FORECAST_HOURS + 1):
        when = departure_utc + timedelta(hours=hour)
        times.append(when)
        wind_row, rain_row, snow_row, risk_row = [], [], [], []
        for lat, lon in dots:
            wx = look_up_weather(weather, lat, lon, when)
            wind_row.append(round(wx["wind_mph"], 1))
            rain_row.append(round(wx["rain_in_hr"], 3))
            snow_row.append(round(wx["snow_in_hr"], 2))
            risk_row.append(quick_scary_score(wx["wind_mph"], wx["rain_in_hr"], wx["snow_in_hr"], load_lbs))
        frames["wind_mph"].append(wind_row)
        frames["rain_in_hr"].append(rain_row)
        frames["snow_in_hr"].append(snow_row)
        frames["risk"].append(risk_row)
    return times, frames


