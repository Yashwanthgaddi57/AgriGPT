"""Open-Meteo free weather + geocoding client (no API key required)."""
from typing import Any

import httpx

from app.core.exceptions import ExternalServiceError

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"

# WMO weather interpretation codes -> human labels
WMO = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain", 66: "Light freezing rain",
    67: "Heavy freezing rain", 71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Rain showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
    96: "Thunderstorm with hail", 99: "Severe thunderstorm with hail",
}


async def geocode(location: str) -> dict[str, Any]:
    """Resolve a place name to lat/lon. Defaults to Nashik, MH if not found."""
    async with httpx.AsyncClient(timeout=6) as client:
        resp = await client.get(GEOCODE, params={"name": location, "count": 1, "language": "en", "format": "json"})
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            return {"name": location, "latitude": 19.9975, "longitude": 73.7898}
        r = results[0]
        return {"name": r.get("name", location), "latitude": r["latitude"], "longitude": r["longitude"]}


async def get_forecast(lat: float, lon: float, days: int = 7) -> dict[str, Any]:
    """Fetch daily forecast: temperature, humidity, wind, precipitation."""
    async with httpx.AsyncClient(timeout=6) as client:
        resp = await client.get(
            OPEN_METEO,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,apparent_temperature_max,relative_humidity_2m_mean,wind_speed_10m_max,precipitation_sum,precipitation_probability_max,weathercode",
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
                "forecast_days": min(days, 16),
            },
        )
        if resp.status_code >= 400:
            raise ExternalServiceError("Weather provider unavailable")
        return resp.json()


def parse_forecast(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Open-Meteo payload into WeatherDay-shaped dicts."""
    daily = raw.get("daily", {})
    dates = daily.get("time", [])
    out: list[dict[str, Any]] = []
    for i, d in enumerate(dates):
        tmax = daily.get("temperature_2m_max", [None] * len(dates))[i]
        tmin = daily.get("temperature_2m_min", [None] * len(dates))[i]
        out.append(
            {
                "date": d,
                "temp_c": round((tmax + tmin) / 2, 1) if tmax is not None and tmin is not None else None,
                "temp_max_c": tmax,
                "temp_min_c": tmin,
                "feels_like_c": daily.get("apparent_temperature_max", [None] * len(dates))[i],
                "humidity": daily.get("relative_humidity_2m_mean", [None] * len(dates))[i],
                "wind_kph": daily.get("wind_speed_10m_max", [None] * len(dates))[i],
                "precip_mm": daily.get("precipitation_sum", [None] * len(dates))[i],
                "precip_probability": daily.get("precipitation_probability_max", [None] * len(dates))[i],
                "condition": WMO.get(daily.get("weathercode", [0])[i], "Unknown"),
            }
        )
    return out
