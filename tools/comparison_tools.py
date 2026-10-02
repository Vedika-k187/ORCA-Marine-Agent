"""
ORCA Historical Comparison Tool
Enables multi-location and climatological comparisons using historical marine datasets.
Explicitly labeled with source_type = 'historical'.
"""

from typing import Any, Dict, Optional
from tools.base import build_evidence, EvidenceDict
from tools.geospatial_tools import lookup_coordinates, haversine_distance


HISTORICAL_LOCATION_PROFILES: Dict[str, Dict[str, Any]] = {
    "Ratnagiri": {
        "region": "Konkan Coast (Maharashtra)",
        "annual_avg_sst_celsius": 28.2,
        "monsoon_onset": "June 08 - 11",
        "avg_monsoon_wave_height_m": 3.4,
        "avg_post_monsoon_wave_height_m": 0.9,
        "primary_commercial_species": ["Indian Mackerel", "Ribbon Fish", "Squid", "Kingfish"],
        "tidal_classification": "Semi-diurnal (2.0 - 2.8m range)",
        "cyclone_vulnerability": "Low to Moderate",
    },
    "Goa": {
        "region": "Central West Coast",
        "annual_avg_sst_celsius": 28.6,
        "monsoon_onset": "June 05 - 08",
        "avg_monsoon_wave_height_m": 3.2,
        "avg_post_monsoon_wave_height_m": 0.8,
        "primary_commercial_species": ["Oil Sardine", "Mackerel", "Tuna", "Shrimp"],
        "tidal_classification": "Mixed Semi-diurnal (1.6 - 2.3m range)",
        "cyclone_vulnerability": "Low",
    },
    "Mumbai": {
        "region": "North Konkan Coast",
        "annual_avg_sst_celsius": 28.0,
        "monsoon_onset": "June 10 - 14",
        "avg_monsoon_wave_height_m": 3.8,
        "avg_post_monsoon_wave_height_m": 1.1,
        "primary_commercial_species": ["Bombay Duck", "Pomfret", "Prawns", "Lobster"],
        "tidal_classification": "Macro-tidal Semi-diurnal (3.5 - 4.5m range)",
        "cyclone_vulnerability": "Moderate",
    },
    "Karwar": {
        "region": "North Kanara Coast (Karnataka)",
        "annual_avg_sst_celsius": 28.5,
        "monsoon_onset": "June 04 - 07",
        "avg_monsoon_wave_height_m": 3.1,
        "avg_post_monsoon_wave_height_m": 0.8,
        "primary_commercial_species": ["Mackerel", "Sardine", "Seer Fish", "Crab"],
        "tidal_classification": "Mixed Semi-diurnal (1.5 - 2.2m range)",
        "cyclone_vulnerability": "Low",
    },
    "Kochi": {
        "region": "Malabar Coast (Kerala)",
        "annual_avg_sst_celsius": 29.0,
        "monsoon_onset": "June 01 - 03",
        "avg_monsoon_wave_height_m": 2.9,
        "avg_post_monsoon_wave_height_m": 0.9,
        "primary_commercial_species": ["Oil Sardine", "Tuna", "Anchovy", "Cephalopods"],
        "tidal_classification": "Micro-tidal (0.8 - 1.2m range)",
        "cyclone_vulnerability": "Low",
    },
}


def compare_coastal_locations(loc1: str, loc2: str) -> EvidenceDict:
    """
    Deterministically compares two coastal locations using historical baselines
    and geospatial distance calculations.
    """
    coords1 = lookup_coordinates(loc1)
    coords2 = lookup_coordinates(loc2)

    profile1 = None
    profile2 = None

    for name, p in HISTORICAL_LOCATION_PROFILES.items():
        if name.lower() == loc1.strip().lower():
            profile1 = p.copy()
            profile1["location_name"] = name
        if name.lower() == loc2.strip().lower():
            profile2 = p.copy()
            profile2["location_name"] = name

    if not profile1 or not profile2:
        return build_evidence(
            source="ORCA Historical Coastal Climatology Database",
            source_type="historical",
            location=f"{loc1} vs {loc2}",
            variables=["sst_comparison", "monsoon_wave_comparison", "spatial_distance"],
            status="unavailable",
            data={
                "error": f"One or both locations ('{loc1}', '{loc2}') lack historical profiles in the registry."
            },
        )

    distance_km = None
    if coords1 and coords2:
        distance_km = haversine_distance(coords1, coords2)

    comparison_data = {
        "location_a": profile1,
        "location_b": profile2,
        "geodesic_distance_km": distance_km,
        "sst_differential_c": round(
            profile1.get("annual_avg_sst_celsius", 0) - profile2.get("annual_avg_sst_celsius", 0), 2
        ),
        "data_classification": "historical_marine_climatology",
    }

    return build_evidence(
        source="ORCA Historical Coastal Climatology Database",
        source_type="historical",
        location=f"{loc1} vs {loc2}",
        variables=[
            "annual_avg_sst_celsius",
            "avg_monsoon_wave_height_m",
            "avg_post_monsoon_wave_height_m",
            "geodesic_distance_km",
        ],
        status="available",
        data=comparison_data,
    )
