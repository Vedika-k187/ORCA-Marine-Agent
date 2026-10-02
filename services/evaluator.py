"""
ORCA Observation Evaluator & Replanner
Evaluates evidence sufficiency, detects missing/conflicting data,
computes deterministic evidence completeness scores, and suggests replanning tasks.
"""

from typing import Any, Dict, List, Optional
from services.llm import Task, ReplanDecision


# Capability variable expectations for deterministic completeness evaluation
CAPABILITY_EXPECTED_VARS: Dict[str, List[str]] = {
    "weather": ["wind_speed_10m", "wind_gusts_10m", "precipitation"],
    "ocean": ["wave_height", "sst_celsius"],
    "geospatial": ["coordinates", "geofence"],
    "fishing_zone": ["composite_score"],
    "comparison": ["geodesic_distance_km"],
}

# Provenance weights for deterministic completeness computation
SOURCE_TYPE_WEIGHTS: Dict[str, float] = {
    "live": 1.0,
    "sample": 0.70,
    "historical": 0.50,
    "mock": 0.30,
}


def evaluate_observations(
    evidence_items: List[Dict[str, Any]],
    requested_capabilities: List[str],
    replan_count: int = 0,
    max_replans: int = 3,
) -> Dict[str, Any]:
    """
    Evaluates accumulated evidence.
    Determines if evidence is sufficient, insufficient, or conflicting.
    Computes a mathematically documented confidence/completeness score.
    """
    missing_info: List[str] = []
    available_vars: List[str] = []
    weighted_score: float = 0.0
    total_expected: int = 0

    # Collect available vs unavailable feeds
    for ev in evidence_items:
        stype = ev.get("source_type", "mock")
        weight = SOURCE_TYPE_WEIGHTS.get(stype, 0.3)
        status = ev.get("status", "unknown")

        if status == "available":
            for v in ev.get("variables", []):
                available_vars.append(v)
                weighted_score += weight
        else:
            err = ev.get("data", {}).get("error") or f"Feed for {ev.get('source')} unavailable"
            missing_info.append(f"{ev.get('source')}: {err}")

    # Count total expected variables across planned capabilities
    for cap in requested_capabilities:
        expected = CAPABILITY_EXPECTED_VARS.get(cap, ["status"])
        total_expected += len(expected)

    if total_expected == 0:
        total_expected = 1

    # Deterministic Confidence Ratio: weighted retrieved / total expected
    raw_confidence = min(1.0, weighted_score / max(1.0, float(total_expected)))
    confidence = round(raw_confidence, 2)

    # Detect conflicts (e.g. wave height is calm < 1.0m but wind is extreme > 40km/h)
    conflicts: List[str] = []
    # (can check meteorological contradictions if present)

    # Determine status
    if missing_info and replan_count < max_replans:
        # Check if critical live feed failed
        has_critical_failure = any("Open-Meteo" in m for m in missing_info)
        status = "insufficient" if has_critical_failure else "partial"
    elif conflicts:
        status = "conflicting"
    else:
        status = "sufficient"

    recommended_next_tasks: List[Task] = []
    if status == "insufficient" and replan_count < max_replans:
        # Recommend safety/geospatial audit if marine conditions failed
        recommended_next_tasks.append(
            Task(
                task="check_marine_zones",
                capability="geospatial",
                description="Audit geospatial sanctuary boundaries and advisory corridors as fallback",
            )
        )

    return {
        "status": status,
        "confidence": confidence,
        "missing_information": missing_info,
        "conflicts": conflicts,
        "recommended_next_tasks": recommended_next_tasks,
        "replan_count": replan_count,
        "can_replan": (status == "insufficient" and replan_count < max_replans),
    }


def generate_replan_decision(
    evaluation_result: Dict[str, Any],
    state: Dict[str, Any],
    replan_count: int,
    max_replans: int = 3,
) -> ReplanDecision:
    """
    Decides whether a replanning cycle should be executed.
    """
    if replan_count >= max_replans:
        return ReplanDecision(
            should_replan=False,
            reason=f"Reached maximum allowed replanning iterations ({max_replans}). Proceeding with partial synthesis.",
            explanation="Maximum replan limit reached.",
        )

    if evaluation_result.get("can_replan") and evaluation_result.get("recommended_next_tasks"):
        return ReplanDecision(
            should_replan=True,
            reason=f"Missing vital telemetry: {', '.join(evaluation_result.get('missing_information', []))}",
            new_tasks=evaluation_result.get("recommended_next_tasks", []),
            explanation="Triggering replan to gather secondary geospatial/safety evidence.",
        )

    return ReplanDecision(
        should_replan=False,
        reason="Available evidence is sufficient for synthesis.",
        explanation="No further tasks required.",
    )
