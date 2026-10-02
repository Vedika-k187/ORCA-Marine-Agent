"""
ORCA Marine Weather Tool
Fetches live deterministic weather data from Open-Meteo Weather API.
Never falls back to fabricated data on failure; reports clearly labeled status.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

from tools.base import build_evidence, EvidenceDict
from tools.geospatial_tools import lookup_coordinates
from services.config import settings


WMO_WEATHER_CODES: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def decode_wmo_code(code: Optional[int]) -> str:
    """Translates WMO weather code into human-readable description."""
    if code is None:
        return "Unknown"
    return WMO_WEATHER_CODES.get(code, f"Weather code {code}")


def fetch_marine_weather(
    location_name: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    time_horizon: Optional[str] = "today",
    timeout: Optional[float] = None,
) -> EvidenceDict:
    """
    Fetches live weather conditions from Open-Meteo API.
    Returns standardized EvidenceDict.
    """
    effective_timeout = timeout if timeout is not None else settings.api_timeout
    # Resolve coordinates if not passed explicitly
    if lat is None or lon is None:
        coords = lookup_coordinates(location_name)
        if not coords:
            return build_evidence(
                source="Open-Meteo Weather API",
                source_type="live",
                location=location_name,
                variables=[
                    "wind_speed_10m",
                    "wind_gusts_10m",
                    "precipitation",
                    "temperature_2m",
                    "weather_condition",
                ],
                status="unavailable",
                data={
                    "error": f"Coordinates for location '{location_name}' could not be resolved.",
                    "requested_time": time_horizon,
                },
            )
        lat, lon = coords

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "current": "temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation,weather_code",
        "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation",
        "timezone": "auto",
    }

    try:
        response = requests.get(url, params=params, timeout=effective_timeout)
        if response.status_code != 200:
            return build_evidence(
                source="Open-Meteo Weather API",
                source_type="live",
                location=location_name,
                variables=[
                    "wind_speed_10m",
                    "wind_gusts_10m",
                    "precipitation",
                    "temperature_2m",
                    "weather_condition",
                ],
                status="error",
                data={
                    "error": f"HTTP error {response.status_code}: {response.text[:200]}",
                    "requested_time": time_horizon,
                    "latitude": lat,
                    "longitude": lon,
                },
            )

        json_data = response.json()
        current = json_data.get("current") or {}
        current_units = json_data.get("current_units") or {}

        wmo_code = current.get("weather_code")
        condition_desc = decode_wmo_code(wmo_code)

        result_data = {
            "latitude": lat,
            "longitude": lon,
            "requested_time": time_horizon,
            "retrieved_at": current.get("time") or datetime.now(timezone.utc).isoformat(),
            "temperature": current.get("temperature_2m"),
            "temperature_unit": current_units.get("temperature_2m", "°C"),
            "wind_speed": current.get("wind_speed_10m"),
            "wind_speed_unit": current_units.get("wind_speed_10m", "km/h"),
            "wind_gusts": current.get("wind_gusts_10m"),
            "wind_gusts_unit": current_units.get("wind_gusts_10m", "km/h"),
            "precipitation": current.get("precipitation"),
            "precipitation_unit": current_units.get("precipitation", "mm"),
            "weather_code": wmo_code,
            "weather_condition": condition_desc,
        }

        # Check if any requested key is missing
        missing_vars = [k for k, v in result_data.items() if v is None]
        if missing_vars:
            result_data["missing_variables"] = missing_vars

        return build_evidence(
            source="Open-Meteo Weather API",
            source_type="live",
            location=location_name,
            variables=[
                "wind_speed_10m",
                "wind_gusts_10m",
                "precipitation",
                "temperature_2m",
                "weather_condition",
            ],
            status="available",
            data=result_data,
        )

    except requests.exceptions.Timeout:
        return build_evidence(
            source="Open-Meteo Weather API",
            source_type="live",
            location=location_name,
            variables=["wind_speed_10m", "wind_gusts_10m", "precipitation"],
            status="unavailable",
            data={
                "error": "Request timed out connecting to Open-Meteo Weather API.",
                "requested_time": time_horizon,
            },
        )
    except requests.exceptions.RequestException as e:
        return build_evidence(
            source="Open-Meteo Weather API",
            source_type="live",
            location=location_name,
            variables=["wind_speed_10m", "wind_gusts_10m", "precipitation"],
            status="error",
            data={
                "error": f"Network/Connection error: {str(e)}",
                "requested_time": time_horizon,
            },
        )
    except Exception as e:
        return build_evidence(
            source="Open-Meteo Weather API",
            source_type="live",
            location=location_name,
            variables=["wind_speed_10m", "wind_gusts_10m", "precipitation"],
            status="error",
            data={"error": f"Unexpected error parsing response: {str(e)}"},
        )
