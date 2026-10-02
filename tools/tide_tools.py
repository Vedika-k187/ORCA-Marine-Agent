"""
ORCA Tide Tool Adapter & Sample Data Provider
Provides structured astronomical tide table predictions for Indian coastal stations.
Explicitly labeled as sample demonstration data; does NOT pretend to be live gauge telemetry.
"""

from typing import Any, Dict, List, Optional
from tools.base import build_evidence, EvidenceDict


# Structured realistic sample harmonic tide predictions for key coastal hubs
SAMPLE_TIDE_TABLES: Dict[str, Dict[str, Any]] = {
    "Ratnagiri": {
        "tidal_type": "Semi-diurnal",
        "reference_datum": "Chart Datum (CD)",
        "high_tides": [
            {"time": "04:18 IST", "height_m": 2.45},
            {"time": "16:42 IST", "height_m": 2.68},
        ],
        "low_tides": [
            {"time": "10:35 IST", "height_m": 0.82},
            {"time": "23:05 IST", "height_m": 0.64},
        ],
        "tidal_range_m": 2.04,
        "phase": "Moderate Flood / Ebb",
    },
    "Mumbai": {
        "tidal_type": "Semi-diurnal Macro-tidal",
        "reference_datum": "Chart Datum (CD)",
        "high_tides": [
            {"time": "02:50 IST", "height_m": 4.12},
            {"time": "15:14 IST", "height_m": 4.35},
        ],
        "low_tides": [
            {"time": "09:10 IST", "height_m": 1.15},
            {"time": "21:30 IST", "height_m": 0.95},
        ],
        "tidal_range_m": 3.40,
        "phase": "High Spring Range",
    },
    "Goa": {
        "tidal_type": "Mixed Semi-diurnal",
        "reference_datum": "Chart Datum (CD)",
        "high_tides": [
            {"time": "05:10 IST", "height_m": 2.10},
            {"time": "17:35 IST", "height_m": 2.25},
        ],
        "low_tides": [
            {"time": "11:25 IST", "height_m": 0.70},
            {"time": "23:55 IST", "height_m": 0.55},
        ],
        "tidal_range_m": 1.70,
        "phase": "Normal Neap Range",
    },
    "Kochi": {
        "tidal_type": "Micro-tidal Mixed",
        "reference_datum": "Chart Datum (CD)",
        "high_tides": [
            {"time": "03:45 IST", "height_m": 1.05},
            {"time": "16:10 IST", "height_m": 1.12},
        ],
        "low_tides": [
            {"time": "10:00 IST", "height_m": 0.35},
            {"time": "22:20 IST", "height_m": 0.28},
        ],
        "tidal_range_m": 0.84,
        "phase": "Low Range",
    },
}


def fetch_tide_data(
    location_name: str,
    target_date: Optional[str] = "today",
) -> EvidenceDict:
    """
    Fetches astronomical tide predictions from the sample harmonic fixture dataset.
    Explicitly labeled as 'sample' data.
    """
    matched_loc = None
    for loc in SAMPLE_TIDE_TABLES.keys():
        if loc.lower() == location_name.strip().lower():
            matched_loc = loc
            break

    if not matched_loc:
        return build_evidence(
            source="INCOIS / Survey of India Harmonic Tide Model Sample Fixture",
            source_type="sample",
            location=location_name,
            variables=["high_tides", "low_tides", "tidal_range_m", "phase"],
            status="unavailable",
            data={
                "error": f"No harmonic tide fixture available for location '{location_name}'.",
                "data_classification": "demonstration_sample_fixture",
            },
        )

    tide_data = SAMPLE_TIDE_TABLES[matched_loc].copy()
    tide_data["target_date"] = target_date
    tide_data["data_classification"] = "demonstration_sample_fixture"
    tide_data["notice"] = "Sample astronomical prediction fixture. Not live sensor/gauge telemetry."

    return build_evidence(
        source="INCOIS / Survey of India Harmonic Tide Model Sample Fixture",
        source_type="sample",
        location=matched_loc,
        variables=["high_tides", "low_tides", "tidal_range_m", "phase"],
        status="available",
        data=tide_data,
    )
