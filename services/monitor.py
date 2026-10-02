"""
ORCA Proactive Monitoring & Change Detection Architecture
Provides condition surveillance, advisory polling, deterministic delta comparisons,
and change detection events without requiring expensive continuous cloud infrastructure.
Can be triggered on-demand or by a lightweight scheduler.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from tools.weather_tools import fetch_marine_weather
from tools.marine_tools import fetch_marine_conditions
from tools.advisory_tools import fetch_marine_advisories


def check_location_conditions(location_name: str) -> Dict[str, Any]:
    """
    Performs a point-in-time multi-source observation snapshot for a coastal location.
    Collects weather, wave telemetry, and active advisories.
    """
    weather_ev = fetch_marine_weather(location_name)
    marine_ev = fetch_marine_conditions(location_name)
    advisory_ev = fetch_marine_advisories(location=location_name)

    w_data = weather_ev.get("data", {})
    m_data = marine_ev.get("data", {})
    adv_data = advisory_ev.get("data", {})

    return {
        "location": location_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "weather": {
            "wind_speed": w_data.get("wind_speed"),
            "wind_gusts": w_data.get("wind_gusts"),
            "temperature": w_data.get("temperature"),
            "weather_condition": w_data.get("weather_condition"),
        },
        "marine": {
            "wave_height": m_data.get("wave_height"),
            "swell_height": m_data.get("swell_height"),
            "swell_period": m_data.get("swell_period"),
            "ocean_current_velocity": m_data.get("ocean_current_velocity"),
        },
        "advisories": {
            "advisory_count": adv_data.get("advisory_count", 0),
            "max_severity": adv_data.get("max_severity", "NONE"),
            "active_items": adv_data.get("advisories", []),
        },
        "provenance": {
            "weather": weather_ev.get("source_type"),
            "marine": marine_ev.get("source_type"),
            "advisories": advisory_ev.get("source_type"),
        },
    }


def check_alerts(location_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches active marine advisories and warnings for a location or coastal stretch."""
    ev = fetch_marine_advisories(location=location_name)
    return ev.get("data", {}).get("advisories", [])


def detect_condition_change(
    previous_obs: Optional[Dict[str, Any]],
    current_obs: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Deterministic comparative evaluation between previous and current observations.
    Flags meaningful variations:
    - Wind speed delta >= 5.0 km/h
    - Wave height delta >= 0.3 m
    - Weather condition changes (e.g., Clear -> Rain)
    - New advisory issued or advisory expired
    """
    if not previous_obs or not current_obs:
        return {
            "changed": False,
            "change_count": 0,
            "changes": [],
            "summary": "Baseline established. Insufficient historical points for delta comparison.",
        }

    changes: List[Dict[str, Any]] = []

    # 1. Compare Wind Speed
    p_w = (previous_obs.get("weather") or {}).get("wind_speed")
    c_w = (current_obs.get("weather") or {}).get("wind_speed")
    if p_w is not None and c_w is not None:
        delta = round(c_w - p_w, 2)
        if abs(delta) >= 5.0:
            direction = "increased" if delta > 0 else "decreased"
            changes.append({
                "variable": "wind_speed",
                "previous": p_w,
                "current": c_w,
                "delta": delta,
                "unit": "km/h",
                "direction": direction,
                "description": f"Wind speed {direction} by {abs(delta):.1f} km/h ({p_w} -> {c_w} km/h)",
            })

    # 2. Compare Wave Height
    p_wave = (previous_obs.get("marine") or {}).get("wave_height")
    c_wave = (current_obs.get("marine") or {}).get("wave_height")
    if p_wave is not None and c_wave is not None:
        delta = round(c_wave - p_wave, 2)
        if abs(delta) >= 0.3:
            direction = "increased" if delta > 0 else "decreased"
            changes.append({
                "variable": "wave_height",
                "previous": p_wave,
                "current": c_wave,
                "delta": delta,
                "unit": "m",
                "direction": direction,
                "description": f"Wave height {direction} by {abs(delta):.2f}m ({p_wave}m -> {c_wave}m)",
            })

    # 3. Compare Weather Condition
    p_cond = (previous_obs.get("weather") or {}).get("weather_condition")
    c_cond = (current_obs.get("weather") or {}).get("weather_condition")
    if p_cond and c_cond and p_cond != c_cond:
        changes.append({
            "variable": "weather_condition",
            "previous": p_cond,
            "current": c_cond,
            "delta": None,
            "direction": "shifted",
            "description": f"Atmospheric condition shifted from '{p_cond}' to '{c_cond}'",
        })

    # 4. Compare Advisories
    p_adv = (previous_obs.get("advisories") or {}).get("advisory_count", 0)
    c_adv = (current_obs.get("advisories") or {}).get("advisory_count", 0)
    p_sev = (previous_obs.get("advisories") or {}).get("max_severity", "NONE")
    c_sev = (current_obs.get("advisories") or {}).get("max_severity", "NONE")

    if c_adv > p_adv or (c_sev in ["CRITICAL", "WARNING"] and p_sev not in ["CRITICAL", "WARNING"]):
        changes.append({
            "variable": "marine_advisories",
            "previous": f"{p_adv} ({p_sev})",
            "current": f"{c_adv} ({c_sev})",
            "delta": c_adv - p_adv,
            "direction": "escalated" if c_adv > p_adv else "severity_shift",
            "description": f"New marine weather advisory logged (Active: {c_adv}, Max Severity: {c_sev})",
        })
    elif c_adv < p_adv:
        changes.append({
            "variable": "marine_advisories",
            "previous": f"{p_adv} ({p_sev})",
            "current": f"{c_adv} ({c_sev})",
            "delta": c_adv - p_adv,
            "direction": "cleared",
            "description": f"Advisory status cleared/expired ({p_adv} -> {c_adv} active)",
        })

    has_changed = len(changes) > 0
    loc_name = current_obs.get("location", "Marine Location")
    summary = (
        f"Detected {len(changes)} meaningful environmental change(s) for {loc_name}."
        if has_changed
        else f"Conditions for {loc_name} remain stable within operational thresholds."
    )

    return {
        "changed": has_changed,
        "change_count": len(changes),
        "changes": changes,
        "summary": summary,
        "location": loc_name,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_alert_event(location_name: str, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Constructs a structured notification event packet from detected changes.
    Does not broadcast or spam; suitable for UI notifications or dashboard banner.
    """
    urgent_changes = [
        c for c in changes
        if c.get("variable") in ["marine_advisories", "wave_height"] and c.get("direction") in ["escalated", "increased"]
    ]

    event_type = "URGENT_CHANGE_ALERT" if urgent_changes else "ROUTINE_CONDITION_UPDATE"

    return {
        "event_id": f"EVT-{int(datetime.now(timezone.utc).timestamp())}",
        "event_type": event_type,
        "location": location_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "change_count": len(changes),
        "highlight": urgent_changes[0]["description"] if urgent_changes else (changes[0]["description"] if changes else "Stable conditions"),
        "all_changes": changes,
    }
