"""
Geocoding = turning "Dallas, TX" into a lat/lon.

we use Nominatim (OpenStreetMap). their rules say you MUST send a real
User-Agent and dont spam them (max 1 request per second), so we cache answers.
"""
import hashlib
import logging
import re
import threading
import time

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import OutsideApiBroke, TripPlanningError

log = logging.getLogger(__name__)

LAT_LON_PATTERN = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")

_nominatim_lock = threading.Lock()
_last_call = [0.0]


def wait_your_turn():
    """nominatim only wants 1 request per second, so we wait in line nicely"""
    with _nominatim_lock:
        gap = time.monotonic() - _last_call[0]
        if gap < 1.05:
            time.sleep(1.05 - gap)
        _last_call[0] = time.monotonic()


def find_where_place_is(text):
    """
    turns a place name into {name, lat, lon}.
    if the user already typed "lat, lon" we just use that and skip the api. ez.
    """
    text = (text or "").strip()
    if not text:
        raise TripPlanningError("Please type a place.")

    match = LAT_LON_PATTERN.match(text)
    if match:
        lat, lon = float(match.group(1)), float(match.group(2))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise TripPlanningError(f"'{text}' is not a real lat, lon.")
        return {"query": text, "name": f"{lat:.5f}, {lon:.5f}", "lat": lat, "lon": lon}

    cache_key = "geo:" + hashlib.sha1(f"{text.lower()}|{settings.NOMINATIM_COUNTRY_CODES}".encode()).hexdigest()
    remembered = cache.get(cache_key)
    if remembered:
        return remembered

    try:
        place = ask_nominatim(text)
    except OutsideApiBroke as exc:
        # nominatim said no (403/429/timeout). try photon instead, its also OpenStreetMap data
        log.warning("nominatim failed, trying photon: %s", exc)
        place = ask_photon(text)

    if place is None:
        raise TripPlanningError(f"Couldn't find a place called '{text}'. Try adding the state, like 'Dallas, TX'.")
    cache.set(cache_key, place, 60 * 60 * 24)
    return place


def ask_nominatim(text):
    """the main geocoder. returns a place or None if it found nothing"""
    params = {"q": text, "format": "jsonv2", "limit": 1, "addressdetails": 0}
    if settings.NOMINATIM_COUNTRY_CODES:
        params["countrycodes"] = settings.NOMINATIM_COUNTRY_CODES

    wait_your_turn()
    try:
        resp = requests.get(
            settings.NOMINATIM_URL,
            params=params,
            headers={"User-Agent": settings.NOMINATIM_USER_AGENT, "Accept-Language": "en"},
            timeout=settings.HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        hits = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise OutsideApiBroke(f"Geocoding service failed for '{text}': {exc}") from exc

    if not hits:
        return None
    hit = hits[0]
    return {"query": text, "name": hit.get("display_name", text), "lat": float(hit["lat"]), "lon": float(hit["lon"])}


def ask_photon(text):
    """backup geocoder (photon by komoot). same idea, different server"""
    try:
        resp = requests.get(
            settings.PHOTON_URL,
            params={"q": text, "limit": 1, "lang": "en"},
            headers={"User-Agent": settings.NOMINATIM_USER_AGENT},
            timeout=settings.HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
    except (requests.RequestException, ValueError) as exc:
        raise OutsideApiBroke(f"Geocoding services are unavailable right now ({exc}).") from exc
    if not features:
        return None
    feat = features[0]
    lon, lat = feat["geometry"]["coordinates"]
    props = feat.get("properties", {})
    name_bits = [props.get(k) for k in ("name", "city", "state", "country") if props.get(k)]
    name = ", ".join(dict.fromkeys(name_bits)) or text
    return {"query": text, "name": name, "lat": float(lat), "lon": float(lon)}
