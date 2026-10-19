"""
Math helpers for maps.

the earth is round (shocking i know) so we cant just use a ruler on lat/lon.
these helpers do the round-earth math for us.
"""
import math

EARTH_RADIUS_MILES = 3958.7613
METERS_PER_MILE = 1609.344


def how_far_apart(lat1, lon1, lat2, lon2):
    """haversine distance in miles between two dots on the earth"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = p2 - p1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(a)))


def quick_how_far(lat1, lon1, lat2, lon2):
    """
    a faster (kinda sloppy) distance for tiny distances. good enough to check
    if two roads are basically the same road. dont use it for long trips.
    """
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return EARTH_RADIUS_MILES * math.hypot(x, y)


def which_way_is_it(lat1, lon1, lat2, lon2):
    """compass direction (degrees) from dot 1 to dot 2. 0 = north, 90 = east"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def walk_from_here(lat, lon, bearing_deg, miles):
    """start at a dot, face a direction, walk some miles. where do you end up?"""
    d = miles / EARTH_RADIUS_MILES
    b = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def mix_two_numbers(a, b, fraction):
    """linear interpolation. fraction 0 = all a, fraction 1 = all b, 0.5 = halfway"""
    return a + (b - a) * fraction


def add_up_the_miles(coords):
    """
    coords are [lat, lon] dots along the road. returns how many miles youve
    driven when you reach each dot (first one is always 0).
    """
    total = 0.0
    running = [0.0]
    for (lat1, lon1), (lat2, lon2) in zip(coords, coords[1:]):
        total += how_far_apart(lat1, lon1, lat2, lon2)
        running.append(total)
    return running


def find_spot_at_mile(coords, cum_miles, target_mile, start_index=0):
    """
    finds the lat/lon that is exactly target_mile down the road.
    start_index lets us skip ahead so we dont search from the start every time (speedy).
    returns (lat, lon, index_of_segment)
    """
    i = max(0, start_index)
    last = len(coords) - 1
    while i < last and cum_miles[i + 1] < target_mile:
        i += 1
    if i >= last:
        return coords[last][0], coords[last][1], last
    seg_len = cum_miles[i + 1] - cum_miles[i]
    frac = 0.0 if seg_len <= 0 else (target_mile - cum_miles[i]) / seg_len
    lat = mix_two_numbers(coords[i][0], coords[i + 1][0], frac)
    lon = mix_two_numbers(coords[i][1], coords[i + 1][1], frac)
    return lat, lon, i


def squish_the_line(coords, tolerance_deg=0.0004):
    """
    Douglas-Peucker line simplify. a road from OSRM can have like 20,000 dots,
    and the browser doesnt need that many to draw it. this throws out dots
    that are basically on a straight line anyway. (no recursion so big roads dont crash)
    """
    n = len(coords)
    if n < 3:
        return list(coords)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    tol2 = tolerance_deg * tolerance_deg
    while stack:
        start, end = stack.pop()
        ax, ay = coords[start][1], coords[start][0]
        bx, by = coords[end][1], coords[end][0]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        worst_d2, worst_i = -1.0, -1
        for i in range(start + 1, end):
            px, py = coords[i][1], coords[i][0]
            if seg2 == 0:
                d2 = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
                d2 = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d2 > worst_d2:
                worst_d2, worst_i = d2, i
        if worst_d2 > tol2:
            keep[worst_i] = True
            stack.append((start, worst_i))
            stack.append((worst_i, end))
    return [c for c, k in zip(coords, keep) if k]
