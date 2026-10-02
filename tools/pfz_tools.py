"""
ORCA Fishing Zone Suitability Tool
Calculates deterministic fishing-zone suitability indices based on SST fronts, chlorophyll,
navigational distance, and sea state conditions.
Clearly marked as demonstration suitability; never claims to be official INCOIS PFZ.
"""

from typing import Any, Dict, Optional
from tools.base import build_evidence, EvidenceDict


def compute_pfz_suitability(
    location_name: str,
    sst_celsius: float = 28.4,
    sst_gradient: float = 0.08,
    chlorophyll_mg_m3: float = 0.85,
    distance_km: float = 18.0,
    wave_height_m: float = 0.8,
    wind_speed_kmh: float = 12.0,
) -> EvidenceDict:
    """
    Computes transparent multi-factor fishing zone suitability score (0-100).
    Pure deterministic calculation in Python.
    """
    # 1. Sea Surface Temperature Score (Weight: 30%)
    if 27.0 <= sst_celsius <= 29.5:
        sst_score = 90.0
    elif 26.0 <= sst_celsius < 27.0 or 29.5 < sst_celsius <= 30.5:
        sst_score = 70.0
    else:
        sst_score = 40.0

    # Frontal thermal gradient bonus (indicates nutrient upwelling)
    if sst_gradient >= 0.05:
        sst_score = min(100.0, sst_score + 10.0)

    # 2. Chlorophyll-a Primary Productivity Score (Weight: 35%)
    if 0.5 <= chlorophyll_mg_m3 <= 2.2:
        chloro_score = 95.0
    elif 0.3 <= chlorophyll_mg_m3 < 0.5:
        chloro_score = 70.0
    elif 2.2 < chlorophyll_mg_m3 <= 4.0:
        chloro_score = 65.0
    else:
        chloro_score = 35.0

    # 3. Navigational Distance Score (Weight: 15%)
    if 10.0 <= distance_km <= 35.0:
        dist_score = 90.0
    elif distance_km < 10.0:
        dist_score = 75.0
    elif 35.0 < distance_km <= 60.0:
        dist_score = 60.0
    else:
        dist_score = 35.0

    # 4. Sea State / Operational Safety Score (Weight: 20%)
    if wave_height_m <= 1.0 and wind_speed_kmh <= 18.0:
        sea_state_score = 100.0
    elif wave_height_m <= 1.8 and wind_speed_kmh <= 28.0:
        sea_state_score = 75.0
    elif wave_height_m <= 2.5:
        sea_state_score = 40.0
    else:
        sea_state_score = 10.0

    # Weighted Composite Score
    composite_score = (
        (sst_score * 0.30)
        + (chloro_score * 0.35)
        + (dist_score * 0.15)
        + (sea_state_score * 0.20)
    )
    composite_score = round(composite_score, 1)

    if composite_score >= 80.0:
        category = "High Suitability"
        recommendation = "Favorable thermal fronts and primary chlorophyll productivity."
    elif composite_score >= 60.0:
        category = "Moderate Suitability"
        recommendation = "Acceptable conditions; standard artisanal harvesting."
    elif composite_score >= 40.0:
        category = "Marginal Suitability"
        recommendation = "Suboptimal fronts or elevated sea roughness."
    else:
        category = "Unfavorable / Hazardous"
        recommendation = "Poor productivity indicators or adverse sea state."

    factors = {
        "sst": {
            "value_celsius": sst_celsius,
            "gradient_c_per_km": sst_gradient,
            "subscore": sst_score,
            "weight_pct": 30,
        },
        "chlorophyll": {
            "value_mg_m3": chlorophyll_mg_m3,
            "subscore": chloro_score,
            "weight_pct": 35,
        },
        "distance": {
            "distance_offshore_km": distance_km,
            "subscore": dist_score,
            "weight_pct": 15,
        },
        "sea_state": {
            "wave_height_m": wave_height_m,
            "wind_speed_kmh": wind_speed_kmh,
            "subscore": sea_state_score,
            "weight_pct": 20,
        },
    }

    result_data = {
        "model_name": "ORCA demonstration fishing-zone suitability",
        "composite_score": composite_score,
        "suitability_category": category,
        "operational_recommendation": recommendation,
        "factors_breakdown": factors,
        "disclaimer": (
            "Demonstration computational model only. Not an official INCOIS Potential Fishing "
            "Zone (PFZ) advisory. Always refer to official government bulletins."
        ),
    }

    return build_evidence(
        source="ORCA demonstration fishing-zone suitability",
        source_type="sample",
        location=location_name,
        variables=[
            "composite_score",
            "suitability_category",
            "sst_score",
            "chlorophyll_score",
            "sea_state_score",
        ],
        status="available",
        data=result_data,
    )
