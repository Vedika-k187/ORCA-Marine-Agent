"""
ORCA Ocean Analytics Tool
Provides deterministic oceanographic parameter fixtures (SST, Chlorophyll-a, currents).
Explicitly labeled as 'sample' data derived from satellite observation fixtures.
"""

from typing import Any, Dict, List, Optional
from tools.base import build_evidence, EvidenceDict
from tools.geospatial_tools import lookup_coordinates


SAMPLE_OCEAN_FIXTURES: Dict[str, Dict[str, Any]] = {
    "Ratnagiri": {
        "sst_celsius": 28.4,
        "sst_anomaly_celsius": +0.3,
        "sst_gradient_c_per_km": 0.08,
        "chlorophyll_mg_m3": 0.88,
        "chlorophyll_front_detected": True,
        "salinity_psu": 35.2,
        "dissolved_oxygen_ml_l": 4.6,
        "current_velocity_kmh": 0.75,
        "current_direction_deg": 315,
        "upwelling_index": "Moderate Coastal Upwelling",
    },
    "Mumbai": {
        "sst_celsius": 28.1,
        "sst_anomaly_celsius": +0.1,
        "sst_gradient_c_per_km": 0.05,
        "chlorophyll_mg_m3": 1.15,
        "chlorophyll_front_detected": True,
        "salinity_psu": 34.8,
        "dissolved_oxygen_ml_l": 4.2,
        "current_velocity_kmh": 1.10,
        "current_direction_deg": 330,
        "upwelling_index": "Low Upwelling",
    },
    "Goa": {
        "sst_celsius": 28.9,
        "sst_anomaly_celsius": +0.4,
        "sst_gradient_c_per_km": 0.06,
        "chlorophyll_mg_m3": 0.65,
        "chlorophyll_front_detected": False,
        "salinity_psu": 35.5,
        "dissolved_oxygen_ml_l": 4.8,
        "current_velocity_kmh": 0.60,
        "current_direction_deg": 300,
        "upwelling_index": "Mild Coastal Front",
    },
    "Karwar": {
        "sst_celsius": 28.7,
        "sst_anomaly_celsius": +0.3,
        "sst_gradient_c_per_km": 0.07,
        "chlorophyll_mg_m3": 0.78,
        "chlorophyll_front_detected": True,
        "salinity_psu": 35.4,
        "dissolved_oxygen_ml_l": 4.7,
        "current_velocity_kmh": 0.70,
        "current_direction_deg": 310,
        "upwelling_index": "Moderate Upwelling",
    },
    "Kochi": {
        "sst_celsius": 29.2,
        "sst_anomaly_celsius": +0.5,
        "sst_gradient_c_per_km": 0.09,
        "chlorophyll_mg_m3": 1.45,
        "chlorophyll_front_detected": True,
        "salinity_psu": 34.5,
        "dissolved_oxygen_ml_l": 4.3,
        "current_velocity_kmh": 0.95,
        "current_direction_deg": 340,
        "upwelling_index": "Active Coastal Upwelling",
    },
}


def fetch_ocean_analytics(
    location_name: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> EvidenceDict:
    """
    Retrieves satellite oceanographic analytics (SST, Chlorophyll-a, currents).
    Explicitly marked as sample data.
    """
    matched_loc = None
    for loc in SAMPLE_OCEAN_FIXTURES.keys():
        if loc.lower() == location_name.strip().lower():
            matched_loc = loc
            break

    if not matched_loc:
        coords = (lat, lon) if (lat and lon) else lookup_coordinates(location_name)
        if not coords:
            return build_evidence(
                source="Copernicus Marine / MODIS Aqua Sample Fixture",
                source_type="sample",
                location=location_name,
                variables=["sst_celsius", "chlorophyll_mg_m3", "ocean_currents"],
                status="unavailable",
                data={
                    "error": f"Oceanographic fixture unavailable for location '{location_name}'.",
                    "data_classification": "demonstration_sample_fixture",
                },
            )
        # Use regional baseline if specific port fixture is missing
        fixture_data = {
            "latitude": coords[0],
            "longitude": coords[1],
            "sst_celsius": 28.5,
            "sst_gradient_c_per_km": 0.05,
            "chlorophyll_mg_m3": 0.70,
            "chlorophyll_front_detected": False,
            "salinity_psu": 35.0,
            "current_velocity_kmh": 0.8,
            "current_direction_deg": 315,
            "upwelling_index": "Regional Arabian Sea Baseline",
            "data_classification": "demonstration_sample_fixture",
            "notice": "Sample satellite oceanographic fixture. Not live satellite ingest.",
        }
    else:
        fixture_data = SAMPLE_OCEAN_FIXTURES[matched_loc].copy()
        fixture_data["data_classification"] = "demonstration_sample_fixture"
        fixture_data["notice"] = "Sample satellite oceanographic fixture. Not live satellite ingest."

    return build_evidence(
        source="Copernicus Marine / MODIS Aqua Ocean Color Sample Fixture",
        source_type="sample",
        location=matched_loc or location_name,
        variables=[
            "sst_celsius",
            "chlorophyll_mg_m3",
            "sst_gradient_c_per_km",
            "current_velocity_kmh",
            "upwelling_index",
        ],
        status="available",
        data=fixture_data,
    )


def fetch_sst(
    location_name: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> EvidenceDict:
    """
    Dedicated clean adapter for Sea Surface Temperature (SST).
    Returns standardized EvidenceDict with explicit sample provenance.
    """
    analytics = fetch_ocean_analytics(location_name, lat=lat, lon=lon)
    if analytics.get("status") != "available":
        return analytics

    data = analytics.get("data", {})
    sst_val = data.get("sst_celsius")
    anomaly = data.get("sst_anomaly_celsius", 0.0)
    gradient = data.get("sst_gradient_c_per_km", 0.0)

    return build_evidence(
        source="Copernicus Marine Satellite SST Adapter (Sample Fixture)",
        source_type="sample",
        location=location_name,
        variables=["sst_celsius", "sst_anomaly_celsius", "sst_gradient_c_per_km"],
        status="available",
        data={
            "sst_celsius": sst_val,
            "sst_anomaly_celsius": anomaly,
            "sst_gradient_c_per_km": gradient,
            "data_classification": "demonstration_sample_fixture",
            "notice": "Sample satellite SST fixture. Not live satellite ingest.",
        },
    )


def fetch_chlorophyll(
    location_name: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> EvidenceDict:
    """
    Dedicated clean adapter for Ocean Chlorophyll-a concentration.
    Returns standardized EvidenceDict with explicit sample provenance.
    """
    analytics = fetch_ocean_analytics(location_name, lat=lat, lon=lon)
    if analytics.get("status") != "available":
        return analytics

    data = analytics.get("data", {})
    chlo_val = data.get("chlorophyll_mg_m3")
    front_det = data.get("chlorophyll_front_detected", False)

    return build_evidence(
        source="MODIS-Aqua Ocean Color Chlorophyll Adapter (Sample Fixture)",
        source_type="sample",
        location=location_name,
        variables=["chlorophyll_mg_m3", "chlorophyll_front_detected"],
        status="available",
        data={
            "chlorophyll_mg_m3": chlo_val,
            "chlorophyll_front_detected": front_det,
            "upwelling_index": data.get("upwelling_index", "Regional Baseline"),
            "data_classification": "demonstration_sample_fixture",
            "notice": "Sample satellite ocean color fixture. Not live satellite ingest.",
        },
    )


def fetch_ocean_current(
    location_name: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> EvidenceDict:
    """
    Dedicated clean adapter for Surface Ocean Current velocity and direction.
    Returns standardized EvidenceDict with explicit sample provenance.
    """
    analytics = fetch_ocean_analytics(location_name, lat=lat, lon=lon)
    if analytics.get("status") != "available":
        return analytics

    data = analytics.get("data", {})
    velocity = data.get("current_velocity_kmh")
    direction = data.get("current_direction_deg")

    return build_evidence(
        source="INCOIS Ocean Surface Currents Adapter (Sample Fixture)",
        source_type="sample",
        location=location_name,
        variables=["current_velocity_kmh", "current_direction_deg"],
        status="available",
        data={
            "current_velocity_kmh": velocity,
            "current_direction_deg": direction,
            "data_classification": "demonstration_sample_fixture",
            "notice": "Sample ocean currents model fixture. Not live sensor/drifter telemetry.",
        },
    )

