"""
ORCA Fishing Specialist Agent
Computes demonstration potential fishing zone (PFZ) suitability from multi-parameter evidence.
"""

from typing import Any, Dict, List
from graph.state import ORCAState
from services.llm import Task
from tools.registry import tool_registry


class FishingAgent:
    """Specialist agent responsible for commercial pelagic fishing zone suitability analysis."""

    def __init__(self):
        self.name = "fishing_agent"
        self.capability = "fishing_zone"

    def run(self, task: Task, state: ORCAState) -> Dict[str, Any]:
        """Calculates demonstration fishing suitability based on accumulated environmental evidence for all target locations."""
        locations: List[str] = []
        if task.location:
            locations = [task.location]
        else:
            raw_locs = state.get("target_locations", [])
            locations = [loc.get("name") if isinstance(loc, dict) else str(loc) for loc in raw_locs]

        if not locations:
            locations = ["Ratnagiri"]

        unique_locations = list(dict.fromkeys(locations))

        weather_payload = state.get("weather_data") or {}
        w_by_loc = weather_payload.get("by_location") or {}
        ocean_payload = state.get("ocean_data") or {}
        o_by_loc = ocean_payload.get("by_location") or {}

        evidence_items: List[Dict[str, Any]] = []
        trace_events: List[Dict[str, Any]] = []
        by_location: Dict[str, Any] = {}

        for loc in unique_locations:
            loc_weather = w_by_loc.get(loc, {}).get("weather_data") or weather_payload.get("weather_data") or {}
            loc_marine = (
                o_by_loc.get(loc, {}).get("marine_telemetry")
                or w_by_loc.get(loc, {}).get("marine_data")
                or weather_payload.get("marine_data")
                or {}
            )
            loc_ocean = o_by_loc.get(loc, {}).get("ocean_analytics") or ocean_payload.get("ocean_analytics") or {}

            wave_h = loc_marine.get("wave_height") or 0.8
            wind_spd = loc_weather.get("wind_speed") or 12.0
            sst_val = loc_ocean.get("sst_celsius") or 28.4
            sst_grad = loc_ocean.get("sst_gradient_c_per_km") or 0.08
            chloro_val = loc_ocean.get("chlorophyll_mg_m3") or 0.85

            # Check for what-if overrides
            if task.parameters.get("chlorophyll"):
                chloro_val = float(task.parameters["chlorophyll"])
            if task.parameters.get("wave_height"):
                wave_h = float(task.parameters["wave_height"])
            if task.parameters.get("wind_speed"):
                wind_spd = float(task.parameters["wind_speed"])

            pfz_ev = tool_registry.execute(
                "compute_pfz_suitability",
                location_name=loc,
                sst_celsius=sst_val,
                sst_gradient=sst_grad,
                chlorophyll_mg_m3=chloro_val,
                wave_height_m=wave_h,
                wind_speed_kmh=wind_spd,
            )
            evidence_items.append(pfz_ev)

            trace_event = {
                "node": "fishing_zone",
                "action": task.task or "evaluate_suitability",
                "status": "completed",
                "details": {
                    "location": loc,
                    "composite_score": pfz_ev.get("data", {}).get("composite_score"),
                    "category": pfz_ev.get("data", {}).get("suitability_category"),
                },
            }
            trace_events.append(trace_event)

            by_location[loc] = pfz_ev.get("data", {})

        primary_loc = unique_locations[0]
        primary_pfz = dict(by_location[primary_loc])
        primary_pfz["by_location"] = by_location

        return {
            "pfz_data": primary_pfz,
            "observations": {"pfz": primary_pfz},
            "agent_results": {"pfz": primary_pfz},
            "evidence_items": evidence_items,
            "execution_trace": trace_events,
        }


fishing_agent = FishingAgent()
