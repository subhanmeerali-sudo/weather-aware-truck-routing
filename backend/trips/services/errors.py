class TripPlanningError(Exception):
    """something went wrong that is the users fault (like a city that doesnt exist)"""

    status_code = 400


class OutsideApiBroke(TripPlanningError):
    """one of the free apis (OSRM, Nominatim, Open-Meteo) said no or timed out"""

    status_code = 502
