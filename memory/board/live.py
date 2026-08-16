"""Live (non-persisted) board data — location/time and weather. Unlike
board.py, nothing here is written to SQLite: these are facts fetched fresh
(with a short cache) rather than points an agent asserts, so there's no
attribution to track.
"""

import time
from datetime import datetime

import httpx

from settings import settings

_WEATHER_CACHE_TTL_SECONDS = 300
_LOCATION_CACHE_TTL_SECONDS = 3600  # IP geolocation doesn't change minute to minute
_weather_cache: dict[str, tuple[float, dict]] = {}
_location_cache: dict[str, tuple[float, dict]] = {}

# WMO weather codes (Open-Meteo's `weather_code`) -> human condition text.
# Covers the common cases; anything unmapped falls back to a generic label.
_WEATHER_CODES = {
    0: "Clear",
    1: "Mostly Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing Rime Fog",
    51: "Light Drizzle",
    53: "Drizzle",
    55: "Dense Drizzle",
    61: "Light Rain",
    63: "Rain",
    65: "Heavy Rain",
    71: "Light Snow",
    73: "Snow",
    75: "Heavy Snow",
    80: "Rain Showers",
    81: "Rain Showers",
    82: "Violent Rain Showers",
    85: "Snow Showers",
    86: "Heavy Snow Showers",
    95: "Thunderstorm",
    96: "Thunderstorm w/ Hail",
    99: "Thunderstorm w/ Hail",
}


async def _resolve_location() -> dict:
    """settings.home_city/home_lat/home_lon are an explicit override (set in
    .env) — when unset (the default), detect from the network via IP
    geolocation instead of relying on hardcoded coordinates. Falls back to
    the last successful lookup (or an "Unknown" placeholder if there's never
    been one) rather than raising, so a transient network hiccup doesn't
    take down the location/weather notes."""
    if settings.home_city and settings.home_lat is not None and settings.home_lon is not None:
        return {"city": settings.home_city, "lat": settings.home_lat, "lon": settings.home_lon}

    cached = _location_cache.get("current")
    if cached and (time.monotonic() - cached[0]) < _LOCATION_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://ipwho.is/")
            response.raise_for_status()
            data = response.json()
        if not data.get("success", True):  # ipwho.is: 200 OK with success:false on failure
            raise ValueError(data.get("message", "IP geolocation lookup failed"))
        city = ", ".join(part for part in (data.get("city"), data.get("region_code")) if part)
        result = {
            "city": city or "Unknown location",
            "lat": data["latitude"],
            "lon": data["longitude"],
        }
    except Exception:
        if cached:
            return cached[1]
        result = {"city": "Unknown location", "lat": 0.0, "lon": 0.0}

    _location_cache["current"] = (time.monotonic(), result)
    return result


async def get_location_and_time() -> dict:
    location = await _resolve_location()
    now = datetime.now().astimezone()
    return {
        **location,
        "local_time": now.strftime("%-I:%M %p"),
        "local_date": now.strftime("%A, %B %-d"),
    }


async def get_weather() -> dict:
    cached = _weather_cache.get("current")
    if cached and (time.monotonic() - cached[0]) < _WEATHER_CACHE_TTL_SECONDS:
        return cached[1]

    location = await _resolve_location()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": location["lat"],
                "longitude": location["lon"],
                "current": "temperature_2m,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min",
                # temperature_unit/wind_speed_unit omitted — Open-Meteo
                # defaults to Celsius and km/h.
                "timezone": "auto",
            },
        )
        response.raise_for_status()
        data = response.json()

    current = data["current"]
    daily = data["daily"]
    code = current["weather_code"]
    result = {
        "temp_c": round(current["temperature_2m"]),
        "condition": _WEATHER_CODES.get(code, "Unknown"),
        "hi_c": round(daily["temperature_2m_max"][0]),
        "lo_c": round(daily["temperature_2m_min"][0]),
        "wind_kmh": round(current["wind_speed_10m"]),
    }
    _weather_cache["current"] = (time.monotonic(), result)
    return result
