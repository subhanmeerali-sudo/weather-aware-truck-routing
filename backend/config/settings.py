"""
Settings for the weather truck routing backend.

basically all the knobs for the app live here. most of them come from
environment variables so we dont have to change code when we put it online.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

# grab stuff from the .env file if there is one (its ok if there isnt)
load_dotenv(BASE_DIR / ".env")


def env_says_yes(name, default="false"):
    """turns words like 'true' or '1' into an actual True. computers r picky."""
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    """splits a comma list from the env into a real python list"""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-not-secret-change-me")
DEBUG = env_says_yes("DJANGO_DEBUG", "true")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0") or ["*"]
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "trips",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",  # squishes the big JSON so it downloads faster
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# the built react app (npm run build) ends up here. django can serve it in prod
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", REPO_ROOT / "frontend" / "dist"))

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_DIST],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

# we dont save anything in a database. no users, no models, nothing. so no db!
DATABASES = {}

# cache lives in memory (each gunicorn worker has its own). thats fine on Render,
# it just means we remember weather for 20 min so we dont bug Open-Meteo again.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "truck-weather-cache",
        "TIMEOUT": 60 * 15,
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.exists() else None
WHITENOISE_INDEX_FILE = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": os.getenv("API_RATE_LIMIT", "30/min")},
}

# CORS: wide open while developing, locked down to a list when we go live
CORS_ALLOW_ALL_ORIGINS = env_says_yes("CORS_ALLOW_ALL", "true" if DEBUG else "false")
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")

# outside apis we talk to (all free, no keys needed)
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
NOMINATIM_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT", "SpotterWeatherTruckRouting/1.0 (take-home demo; set NOMINATIM_USER_AGENT to your contact)"
)
NOMINATIM_COUNTRY_CODES = os.getenv("NOMINATIM_COUNTRY_CODES", "")
# backup geocoder if nominatim blocks us (it happens on shared cloud IPs)
PHOTON_URL = os.getenv("PHOTON_URL", "https://photon.komoot.io/api/")
OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))

# OSRM's public server only does car routing. trucks are slower, so you can make
# the trip take longer with this number (1.0 = trust OSRM exactly, 1.1 = 10% slower)
TRUCK_DURATION_FACTOR = float(os.getenv("TRUCK_DURATION_FACTOR", "1.0"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
