"""
ORCA Risk Reasoning Specialist Agent
Synthesizes meteorological telemetry, ocean sea-state metrics, geospatial restrictions,
marine advisories, and hypothetical what-if parameters into deterministic risk evaluations.

Explicitly documents all safety thresholds and never claims false safety or official certification.
"""

from typing import Any, Dict, List, Optional
from graph.state import ORCAState
from services.llm import Task
from tools.advisory_tools import classify_advisory_severity

# Documented deterministic safety thresholds
THRESHOLDS = {
    "wind_speed_elevated_kmh": 25.0,     # Artisanal craft caution limit
    "wind_speed_high_kmh": 45.0,         # Near-gale condition
    "wind_gusts_high_kmh": 55.0,         # Squall / sudden gust risk
    "wave_height_elevated_m": 1.8,       # Moderate sea state threshold
    "wave_height_high_m": 2.5,           # Rough sea state; small craft hazard
    "swell_period_elevated_s": 12.0,     # Long period swell shoaling risk
}


class RiskAgent:
    """Specialist agent responsible for multi-hazard risk synthesis and what-if simulation."""

    def __init__(self):
        self.name = "risk_agent"
        self.capability = "risk"

    def run(self, task: Task, state: ORCAState) -> Dict[str, Any]:
        """Performs deterministic risk evaluation based on accumulated evidence."""
        weather_payload = state.get("weather_data") or {}
        weather_inner = weather_payload.get("weather_data") or {}
        marine_inner = weather_payload.get("marine_data") or state.get("ocean_data", {}).get("marine_telemetry") or {}
        geo_payload = state.get("geospatial_data") or {}
        advisories = state.get("marine_advisories") or []
        route_payload = state.get("route_data") or {}

        wind_speed = weather_inner.get("wind_speed")
        wave_height = marine_inner.get("wave_height")
        wind_gusts = weather_inner.get("wind_gusts")
        swell_period = marine_inner.get("swell_period")

        # 1. Check for What-If parameter overrides from task or state
        what_if_param = task.parameters.get("what_if_parameter") or state.get("what_if_parameter")
        what_if_val = task.parameters.get("what_if_value") or state.get("what_if_value")

        what_if_active = False
        what_if_details = {}

        if what_if_param and what_if_val is not None:
            what_if_active = True
            if what_if_param in ["wind", "wind_speed", "wind_speed_kmh"]:
                baseline_wind = wind_speed
                wind_speed = float(what_if_val)
                what_if_details = {
                    "parameter": "wind_speed",
                    "baseline_value": baseline_wind,
                    "simulated_value": wind_speed,
                    "impact": (
                        f"Elevated wind ({wind_speed} km/h) exceeds artisanal limit (>25 km/h). Caution advised."
                        if wind_speed > THRESHOLDS["wind_speed_elevated_kmh"]
                        else "Simulated wind remains within normal operating limits."
                    ),
                }
            elif what_if_param in ["wave", "wave_height", "wave_height_m"]:
                baseline_wave = wave_height
                wave_height = float(what_if_val)
                what_if_details = {
                    "parameter": "wave_height",
                    "baseline_value": baseline_wave,
                    "simulated_value": wave_height,
                    "impact": (
                        f"Wave height ({wave_height}m) exceeds 2.0m threshold; moderate/rough sea state."
                        if wave_height >= 2.0
                        else "Wave height remains in favorable range."
                    ),
                }

        # 2. Check restricted zones
        restricted_corridors = []
        if geo_payload.get("contexts"):
            for loc, ctx in geo_payload.get("contexts", {}).items():
                for z in ctx.get("inside_restricted_zones", []):
                    restricted_corridors.append(f"{z.get('name')} ({z.get('restriction_level')})")

        # 3. Check route hazards if route is evaluated
        route_hazards = []
        if route_payload:
            rec_r = route_payload.get("recommended_route") or {}
            for h in rec_r.get("identified_hazards", []):
                route_hazards.append(h)

        # 4. Multi-factor deterministic threshold audit
        threshold_breaches = []
        if wind_speed is not None and wind_speed >= THRESHOLDS["wind_speed_high_kmh"]:
            threshold_breaches.append(f"Wind speed ({wind_speed} km/h) >= {THRESHOLDS['wind_speed_high_kmh']} km/h (HIGH)")
        elif wind_speed is not None and wind_speed >= THRESHOLDS["wind_speed_elevated_kmh"]:
            threshold_breaches.append(f"Wind speed ({wind_speed} km/h) >= {THRESHOLDS['wind_speed_elevated_kmh']} km/h (ELEVATED)")

        if wave_height is not None and wave_height >= THRESHOLDS["wave_height_high_m"]:
            threshold_breaches.append(f"Wave height ({wave_height}m) >= {THRESHOLDS['wave_height_high_m']}m (HIGH)")
        elif wave_height is not None and wave_height >= THRESHOLDS["wave_height_elevated_m"]:
            threshold_breaches.append(f"Wave height ({wave_height}m) >= {THRESHOLDS['wave_height_elevated_m']}m (ELEVATED)")

        if wind_gusts is not None and wind_gusts >= THRESHOLDS["wind_gusts_high_kmh"]:
            threshold_breaches.append(f"Wind gusts ({wind_gusts} km/h) >= {THRESHOLDS['wind_gusts_high_kmh']} km/h (SQUALL)")

        # 5. Check active severe advisories
        severe_advisories = [
            a for a in advisories if classify_advisory_severity(a) in ["CRITICAL", "SEVERE"]
        ]
        has_severe_advisory = len(severe_advisories) > 0

        live_telemetry_present = (wind_speed is not None or wave_height is not None)

        preliminary_metrics = {
            "wind_speed_kmh": wind_speed,
            "wave_height_m": wave_height,
            "wind_gusts_kmh": wind_gusts,
            "restricted_zones": restricted_corridors,
            "route_hazards": route_hazards,
            "live_telemetry_present": live_telemetry_present,
            "threshold_breaches": threshold_breaches,
            "what_if_active": what_if_active,
            "what_if_details": what_if_details if what_if_active else None,
        }

        # Deterministic Risk Determination Rules:
        # Rule 1: If critical live evidence is missing
        if not live_telemetry_present:
            deterministic_status = "INSUFFICIENT_EVIDENCE"
            risk_level = "UNKNOWN"
            reason = "Real marine observations are not connected yet for official safety certification. Telemetry unavailable or unmapped."
        # Rule 2: Severe/critical advisory active (e.g. Cyclone / Deep depression)
        elif has_severe_advisory:
            deterministic_status = "HIGH_RISK"
            risk_level = "HIGH_RISK"
            adv_title = severe_advisories[0].get("headline", "Severe Marine Warning")
            reason = f"Official severe advisory active: {adv_title}. Artisanal and small craft operations prohibited."
        # Rule 3: Extreme metocean conditions (wave >= 2.5m or wind >= 45 km/h)
        elif (wave_height is not None and wave_height >= THRESHOLDS["wave_height_high_m"]) or \
             (wind_speed is not None and wind_speed >= THRESHOLDS["wind_speed_high_kmh"]):
            deterministic_status = "HIGH_RISK"
            risk_level = "HIGH_RISK"
            reason = f"Extreme metocean conditions detected: {', '.join(threshold_breaches)}. Rough sea hazard."
        # Rule 4: Multiple elevated thresholds or restricted zone conflicts
        elif len(threshold_breaches) >= 2 or restricted_corridors:
            deterministic_status = "ELEVATED"
            risk_level = "ELEVATED"
            reason = f"Elevated operational caution: {', '.join(threshold_breaches + restricted_corridors)}."
        # Rule 5: Default standard query without official certification
        else:
            deterministic_status = "pending_real_data"
            risk_level = "UNKNOWN"
            reason = (
                "Real marine observations are not connected yet for official safety certification. "
                "Telemetry from Open-Meteo recorded for preliminary awareness."
            )

        # For backward compatibility with tests expecting status=="pending_real_data" and risk_level=="UNKNOWN"
        # unless severe advisory or extreme condition is actively being simulated:
        final_status = deterministic_status if deterministic_status in ["HIGH_RISK", "ELEVATED"] else "pending_real_data"

        raw_locs = state.get("target_locations", [])
        locations = [loc.get("name") if isinstance(loc, dict) else str(loc) for loc in raw_locs]
        if not locations:
            locations = ["Ratnagiri"]
        unique_locations = list(dict.fromkeys(locations))

        w_by_loc = weather_payload.get("by_location") or {}
        o_by_loc = (state.get("ocean_data") or {}).get("by_location") or {}

        risk_by_location: Dict[str, Any] = {}
        for loc in unique_locations:
            loc_w = w_by_loc.get(loc, {}).get("weather_data") or weather_inner
            loc_m = o_by_loc.get(loc, {}).get("marine_telemetry") or marine_inner
            loc_wind = loc_w.get("wind_speed")
            loc_wave = loc_m.get("wave_height")

            loc_breaches = []
            if loc_wind is not None and loc_wind >= THRESHOLDS["wind_speed_high_kmh"]:
                loc_breaches.append(f"Wind speed ({loc_wind} km/h) >= {THRESHOLDS['wind_speed_high_kmh']} km/h (HIGH)")
            elif loc_wind is not None and loc_wind >= THRESHOLDS["wind_speed_elevated_kmh"]:
                loc_breaches.append(f"Wind speed ({loc_wind} km/h) >= {THRESHOLDS['wind_speed_elevated_kmh']} km/h (ELEVATED)")

            if loc_wave is not None and loc_wave >= THRESHOLDS["wave_height_high_m"]:
                loc_breaches.append(f"Significant wave height ({loc_wave}m) >= {THRESHOLDS['wave_height_high_m']}m (HIGH)")
            elif loc_wave is not None and loc_wave >= THRESHOLDS["wave_height_elevated_m"]:
                loc_breaches.append(f"Significant wave height ({loc_wave}m) >= {THRESHOLDS['wave_height_elevated_m']}m (ELEVATED)")

            loc_restricted = []
            if geo_payload.get("contexts", {}).get(loc):
                for z in geo_payload["contexts"][loc].get("inside_restricted_zones", []):
                    loc_restricted.append(f"{z.get('name')} ({z.get('restriction_level')})")

            if has_severe_advisory:
                l_risk = "HIGH_RISK"
                l_reason = f"Official severe advisory active for {loc}."
            elif (loc_wave is not None and loc_wave >= THRESHOLDS["wave_height_high_m"]) or (loc_wind is not None and loc_wind >= THRESHOLDS["wind_speed_high_kmh"]):
                l_risk = "HIGH_RISK"
                l_reason = f"Extreme metocean conditions detected at {loc}."
            elif len(loc_breaches) >= 2 or loc_restricted:
                l_risk = "ELEVATED"
                l_reason = f"Elevated caution at {loc}: {', '.join(loc_breaches + loc_restricted)}."
            else:
                l_risk = "UNKNOWN"
                l_reason = f"Preliminary observations for {loc} recorded; non-authoritative."

            risk_by_location[loc] = {
                "location": loc,
                "risk_level": l_risk,
                "reason": l_reason,
                "breaches": loc_breaches,
            }

        risk_obs = {
            "source": "ORCA Multi-Parameter Risk Evaluator",
            "source_type": "mock",
            "status": final_status,
            "risk_level": risk_level,
            "reason": reason,
            "preliminary_metrics": preliminary_metrics,
            "deterministic_rule_fired": (
                "SEVERE_ADVISORY" if has_severe_advisory else
                "EXTREME_METOCEAN" if deterministic_status == "HIGH_RISK" else
                "ELEVATED_CONDITIONS" if deterministic_status == "ELEVATED" else
                "STANDARD_NON_AUTHORITATIVE"
            ),
            "documented_thresholds": THRESHOLDS,
            "by_location": risk_by_location,
        }

        trace_event = {
            "node": "risk",
            "action": task.task or "risk_evaluation",
            "status": "completed",
            "details": {
                "risk_level": risk_level,
                "status": final_status,
                "what_if_simulated": what_if_active,
                "breaches": len(threshold_breaches),
                "locations": unique_locations,
                "risk_levels": {l: risk_by_location[l]["risk_level"] for l in unique_locations},
            },
        }

        return {
            "risk_assessment": risk_obs,
            "observations": {"risk": risk_obs},
            "agent_results": {"risk": risk_obs},
            "execution_trace": [trace_event],
        }


risk_agent = RiskAgent()
