"""
ORCA Evidence Specialist Agent
Aggregates, categorizes, audits evidence provenance, and performs multi-source
cross-domain correlation across Weather, Marine, Ocean, Geospatial, Advisories, and Routes.
"""

from typing import Any, Dict, List, Optional
from graph.state import ORCAState
from services.llm import Task


class EvidenceAgent:
    """Specialist agent responsible for evidence provenance and multi-source correlation."""

    def __init__(self):
        self.name = "evidence_agent"
        self.capability = "evidence"

    def run(self, task: Task, state: ORCAState) -> Dict[str, Any]:
        """Correlates observations across meteorological, oceanographic, and geospatial domains."""
        evidence_items: List[Dict[str, Any]] = state.get("evidence_items", [])

        # Categorize evidence by provenance
        live_items = [e for e in evidence_items if e.get("source_type") == "live" and e.get("status") == "available"]
        sample_items = [e for e in evidence_items if e.get("source_type") == "sample" and e.get("status") == "available"]
        historical_items = [e for e in evidence_items if e.get("source_type") == "historical"]
        unavailable_items = [e for e in evidence_items if e.get("status") in ["unavailable", "error"]]

        summary = {
            "total_evidence_count": len(evidence_items),
            "live_count": len(live_items),
            "sample_count": len(sample_items),
            "historical_count": len(historical_items),
            "unavailable_count": len(unavailable_items),
            "is_evidence_sufficient": len(live_items) > 0,
        }

        # Multi-source cross-domain correlation
        weather_payload = state.get("weather_data") or {}
        weather_inner = weather_payload.get("weather_data") or {}
        marine_inner = weather_payload.get("marine_data") or state.get("ocean_data", {}).get("marine_telemetry") or {}
        ocean_inner = state.get("ocean_data", {}).get("ocean_analytics") or {}
        geo_payload = state.get("geospatial_data") or {}
        advisories = state.get("marine_advisories") or []
        route_payload = state.get("route_data") or {}

        wind_speed = weather_inner.get("wind_speed")
        wind_gusts = weather_inner.get("wind_gusts")
        wave_height = marine_inner.get("wave_height")
        swell_height = marine_inner.get("swell_height")

        raw_locs = state.get("target_locations", [])
        loc_names = [l.get("name") if isinstance(l, dict) else str(l) for l in raw_locs]
        primary_loc = loc_names[0] if loc_names else "Specified Marine Sector"
        time_horizon = state.get("time_horizon", "today")

        correlated_factors = []
        conflicting_signals = []

        # 1. Metocean Coherence: Wind vs Waves
        metocean_coherence = "NORMAL_SEASTATE"
        if wind_speed is not None and wave_height is not None:
            if wind_speed > 35.0 and wave_height > 2.0:
                metocean_coherence = "COHERENT_ELEVATED_STORM_STATE"
                correlated_factors.append(f"Strong wind ({wind_speed} km/h) strongly correlates with high wave action ({wave_height}m).")
            elif wind_speed < 15.0 and wave_height > 2.2:
                metocean_coherence = "DIVERGENT_DISTANT_SWELL"
                correlated_factors.append(f"Low local wind ({wind_speed} km/h) with elevated waves ({wave_height}m) indicates distant ocean swell propagation.")
            elif wind_speed < 20.0 and wave_height < 1.5:
                metocean_coherence = "COHERENT_CALM_STATE"
                correlated_factors.append("Low wind and modest wave height confirm tranquil coastal conditions.")

        # 2. Advisory Correlation: Weather/Waves vs Active Warnings
        active_advisories_count = len(advisories)
        if active_advisories_count > 0:
            top_adv = advisories[0]
            severity = top_adv.get("severity", "ADVISORY")
            correlated_factors.append(
                f"Active {severity} advisory for {top_adv.get('affected_region', primary_loc)}: '{top_adv.get('headline')}'"
            )
            if wave_height and wave_height > 2.0:
                correlated_factors.append(f"Measured wave height ({wave_height}m) aligns directly with active warning criteria.")

        # 3. Geospatial & Route Correlation
        if geo_payload.get("contexts"):
            for loc, ctx in geo_payload.get("contexts", {}).items():
                for z in ctx.get("inside_restricted_zones", []):
                    correlated_factors.append(f"Location {loc} intersects {z.get('name')} ({z.get('restriction_level')}).")

        if route_payload:
            rec_r = route_payload.get("recommended_route") or {}
            cands = route_payload.get("candidate_routes", [])
            for c in cands:
                if c.get("restricted_zone_intersections"):
                    correlated_factors.append(f"Candidate corridor '{c.get('route_name')}' passes through protected marine zones: {', '.join(c.get('restricted_zone_intersections'))}")

        # Check for potential data conflicts
        if wind_speed is not None and wind_speed > 45.0 and active_advisories_count == 0:
            conflicting_signals.append("High measured wind speed (>45 km/h) but no official sample warning bulletin logged.")

        correlation_assessment = {
            "primary_location": primary_loc,
            "time_horizon": time_horizon,
            "metocean_coherence": metocean_coherence,
            "cross_domain_risk_factors": correlated_factors,
            "conflicting_signals": conflicting_signals,
            "active_advisories_count": active_advisories_count,
            "correlation_summary": (
                f"Multi-source correlation for {primary_loc} ({time_horizon}): "
                f"Sea-state classified as {metocean_coherence}. "
                f"Identified {len(correlated_factors)} correlated risk indicators across metocean, spatial, and advisory feeds."
            ),
        }

        trace_event = {
            "node": "evidence",
            "action": task.task or "correlate_evidence",
            "status": "completed",
            "details": {
                "provenance_summary": summary,
                "correlation": correlation_assessment,
            },
        }

        return {
            "evidence_correlation": correlation_assessment,
            "observations": {
                "evidence_summary": summary,
                "evidence_correlation": correlation_assessment,
            },
            "agent_results": {
                "evidence_summary": summary,
                "evidence_correlation": correlation_assessment,
            },
            "execution_trace": [trace_event],
        }


evidence_agent = EvidenceAgent()
