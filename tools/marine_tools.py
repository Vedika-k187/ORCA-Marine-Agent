"""
ORCA Marine Conditions Tool
Fetches live oceanographic wave, swell, and surface currents data from Open-Meteo Marine API.
Marks any unavailable parameters explicitly instead of fabricating values.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

from tools.base import build_evidence, EvidenceDict
from tools.geospatial_tools import lookup_coordinates
from services.config import settings


def fetch_marine_conditions(
    location_name: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    timeout: Optional[float] = None,
) -> EvidenceDict:
    """
    Fetches real-time marine wave, swell, and ocean current metrics.
    """
    effective_timeout = timeout if timeout is not None else settings.api_timeout
    if lat is None or lon is None:
        coords = lookup_coordinates(location_name)
        if not coords:
            return build_evidence(
                source="Open-Meteo Marine API",
                source_type="live",
                location=location_name,
                variables=[
                    "wave_height",
                    "wave_direction",
                    "swell_height",
                    "swell_period",
                    "ocean_current_velocity",
                    "ocean_current_direction",
                ],
                status="unavailable",
                data={
                    "error": f"Coordinates for location '{location_name}' could not be resolved."
                },
            )
        lat, lon = coords

    url = "https://marine-api.open-meteo.com/v1/marine"
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "current": "wave_height,wave_direction,swell_wave_height,swell_wave_period,ocean_current_velocity,ocean_current_direction",
        "timezone": "auto",
    }

    try:
        response = requests.get(url, params=params, timeout=effective_timeout)
        if response.status_code != 200:
            return build_evidence(
                source="Open-Meteo Marine API",
                source_type="live",
                location=location_name,
                variables=[
                    "wave_height",
                    "wave_direction",
                    "swell_height",
                    "swell_period",
                    "ocean_current_velocity",
                ],
                status="error",
                data={"error": f"HTTP error {response.status_code}: {response.text[:200]}"},
            )

        json_data = response.json()
        current = json_data.get("current") or {}
        units = json_data.get("current_units") or {}

        wave_h = current.get("wave_height")
        wave_dir = current.get("wave_direction")
        swell_h = current.get("swell_wave_height")
        swell_p = current.get("swell_wave_period")
        curr_vel = current.get("ocean_current_velocity")
        curr_dir = current.get("ocean_current_direction")

        data: Dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "retrieved_at": current.get("time") or datetime.now(timezone.utc).isoformat(),
            "wave_height": wave_h,
            "wave_height_unit": units.get("wave_height", "m"),
            "wave_direction": wave_dir,
            "wave_direction_unit": units.get("wave_direction", "degrees"),
            "swell_height": swell_h,
            "swell_height_unit": units.get("swell_wave_height", "m"),
            "swell_period": swell_p,
            "swell_period_unit": units.get("swell_wave_period", "s"),
            "ocean_current_velocity": curr_vel,
            "ocean_current_velocity_unit": units.get("ocean_current_velocity", "km/h"),
            "ocean_current_direction": curr_dir,
            "ocean_current_direction_unit": units.get("ocean_current_direction", "degrees"),
        }

        # Check for unavailable variables
        unavailable_vars = [k for k in ["wave_height", "swell_height", "swell_period", "ocean_current_velocity"] if data[k] is None]
        if unavailable_vars:
            data["unavailable_variables"] = unavailable_vars

        return build_evidence(
            source="Open-Meteo Marine API",
            source_type="live",
            location=location_name,
            variables=[
                "wave_height",
                "wave_direction",
                "swell_height",
                "swell_period",
                "ocean_current_velocity",
                "ocean_current_direction",
            ],
            status="available",
            data=data,
        )

    except requests.exceptions.Timeout:
        return build_evidence(
            source="Open-Meteo Marine API",
            source_type="live",
            location=location_name,
            variables=["wave_height", "swell_height", "ocean_current_velocity"],
            status="unavailable",
            data={"error": "Request timed out connecting to Open-Meteo Marine API."},
        )
    except requests.exceptions.RequestException as e:
        return build_evidence(
            source="Open-Meteo Marine API",
            source_type="live",
            location=location_name,
            variables=["wave_height", "swell_height", "ocean_current_velocity"],
            status="error",
            data={"error": f"Network/Connection error: {str(e)}"},
        )
    except Exception as e:
        return build_evidence(
            source="Open-Meteo Marine API",
            source_type="live",
            location=location_name,
            variables=["wave_height", "swell_height", "ocean_current_velocity"],
            status="error",
            data={"error": f"Unexpected error processing response: {str(e)}"},
        )
