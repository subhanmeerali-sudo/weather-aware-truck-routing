"""
The weather risk rules from the take-home PDF.

this is the most important file honestly. it decides how scary the weather
is for the truck at one spot. bigger number = scarier.

    Condition | Low       | Moderate  | High      | Severe    | No Travel
    Wind      | <25 mph   | 25-34     | 35-44     | 45-54     | >=55 mph
    Rain      | <0.10 in/h| 0.10-0.25 | 0.25-0.50 | 0.50-1.00 | >1.00
    Snow      | <0.5 in/h | 0.5-1.0   | 1.0-2.0   | 2.0-3.0   | >3.0

    Load rules:
      >=55 mph                 -> No Travel for any load
      45-54 mph and >30,000 lb -> No Travel
      35-44 mph and >40,000 lb -> Severe

Edge choices (the PDF ranges touch at the ends, so we had to pick a side):
  * a value sitting exactly on a boundary goes to the higher (scarier) bucket,
    e.g. 0.25 in/hr rain = High, 35 mph = High. safer for the driver.
  * except the No Travel line for rain/snow, the PDF says ">", so exactly
    1.00 in/hr rain is still Severe and exactly 3.0 in/hr snow is still Severe.
"""

LOW = "Low"
MODERATE = "Moderate"
HIGH = "High"
SEVERE = "Severe"
NO_TRAVEL = "No Travel"

SCARY_LEVELS = [LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL]
SCARY_POINTS = {level: i + 1 for i, level in enumerate(SCARY_LEVELS)}  # Low=1 ... No Travel=5

HEAVY_FOR_NO_TRAVEL_LBS = 30_000
HEAVY_FOR_SEVERE_LBS = 40_000


def see_how_windy(wind_mph, load_lbs):
    """
    this checks if the wind is too strong for the big truck.
    heavy trucks get extra rules cuz the PDF says so (big tall trailers + wind = bad).
    returns (level, reason_or_None)
    """
    if wind_mph >= 55:
        return NO_TRAVEL, f"wind {wind_mph:.0f} mph is 55+ (no travel for any load)"
    if wind_mph >= 45:
        if load_lbs > HEAVY_FOR_NO_TRAVEL_LBS:
            return NO_TRAVEL, f"wind {wind_mph:.0f} mph with {load_lbs:,.0f} lb load (>30,000 lb)"
        return SEVERE, f"wind {wind_mph:.0f} mph"
    if wind_mph >= 35:
        if load_lbs > HEAVY_FOR_SEVERE_LBS:
            return SEVERE, f"wind {wind_mph:.0f} mph with {load_lbs:,.0f} lb load (>40,000 lb)"
        return HIGH, f"wind {wind_mph:.0f} mph"
    if wind_mph >= 25:
        return MODERATE, f"wind {wind_mph:.0f} mph"
    return LOW, None


def see_how_rainy(rain_in_hr):
    """this checks how hard its raining (inches per hour)"""
    if rain_in_hr > 1.00:
        return NO_TRAVEL, f"rain {rain_in_hr:.2f} in/hr"
    if rain_in_hr >= 0.50:
        return SEVERE, f"rain {rain_in_hr:.2f} in/hr"
    if rain_in_hr >= 0.25:
        return HIGH, f"rain {rain_in_hr:.2f} in/hr"
    if rain_in_hr >= 0.10:
        return MODERATE, f"rain {rain_in_hr:.2f} in/hr"
    return LOW, None


def see_how_snowy(snow_in_hr):
    """this checks how much snow is falling (inches per hour). snow is the worst for trucks"""
    if snow_in_hr > 3.0:
        return NO_TRAVEL, f"snow {snow_in_hr:.1f} in/hr"
    if snow_in_hr >= 2.0:
        return SEVERE, f"snow {snow_in_hr:.1f} in/hr"
    if snow_in_hr >= 1.0:
        return HIGH, f"snow {snow_in_hr:.1f} in/hr"
    if snow_in_hr >= 0.5:
        return MODERATE, f"snow {snow_in_hr:.1f} in/hr"
    return LOW, None


def scariest_one(*levels):
    """out of a bunch of levels, give back the scariest one"""
    return max(levels, key=lambda lvl: SCARY_POINTS[lvl])


def check_if_scary(weather, load_lbs):
    """
    looks at wind + rain + snow at one spot and says how scary it is overall.
    the overall level is just whichever one is the worst (one bad thing is enough to be bad).

    weather is a dict with wind_mph, rain_in_hr, snow_in_hr
    """
    wind_level, wind_why = see_how_windy(weather["wind_mph"], load_lbs)
    rain_level, rain_why = see_how_rainy(weather["rain_in_hr"])
    snow_level, snow_why = see_how_snowy(weather["snow_in_hr"])
    level = scariest_one(wind_level, rain_level, snow_level)
    reasons = [why for why in (wind_why, rain_why, snow_why) if why]
    return {
        "level": level,
        "score": SCARY_POINTS[level],
        "wind_level": wind_level,
        "rain_level": rain_level,
        "snow_level": snow_level,
        "reasons": reasons,
    }


def quick_scary_score(wind_mph, rain_in_hr, snow_in_hr, load_lbs):
    """same as check_if_scary but only the number. used a LOT for the heatmap so its lean"""
    return max(
        SCARY_POINTS[see_how_windy(wind_mph, load_lbs)[0]],
        SCARY_POINTS[see_how_rainy(rain_in_hr)[0]],
        SCARY_POINTS[see_how_snowy(snow_in_hr)[0]],
    )
