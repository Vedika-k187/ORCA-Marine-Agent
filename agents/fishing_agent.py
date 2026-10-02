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
        """Calculates demonstration fishing suitability based on accumulated environmental evidence."""
        location = task.location
        if not location:
            target_locs = state.get("target_locations", [])
            location = target_locs[0].get("name") if target_locs and isinstance(target_locs[0], dict) else "Ratnagiri"

        # Read available ocean & weather inputs
        weather_payload = state.get("weather_data") or {}
        marine_inner = weather_payload.get("marine_data") or {}
        weather_inner = weather_payload.get("weather_data") or {}
        ocean_payload = state.get("ocean_data") or {}
        ocean_inner = ocean_payload.get("ocean_analytics") or {}

        wave_h = marine_inner.get("wave_height") or 0.8
        wind_spd = weather_inner.get("wind_speed") or 12.0
        sst_val = ocean_inner.get("sst_celsius") or 28.4
        sst_grad = ocean_inner.get("sst_gradient_c_per_km") or 0.08
        chloro_val = ocean_inner.get("chlorophyll_mg_m3") or 0.85

        # Check for what-if overrides
        if task.parameters.get("chlorophyll"):
            chloro_val = float(task.parameters["chlorophyll"])
        if task.parameters.get("wave_height"):
            wave_h = float(task.parameters["wave_height"])
        if task.parameters.get("wind_speed"):
            wind_spd = float(task.parameters["wind_speed"])

        pfz_ev = tool_registry.execute(
            "compute_pfz_suitability",
            location_name=location,
            sst_celsius=sst_val,
            sst_gradient=sst_grad,
            chlorophyll_mg_m3=chloro_val,
            wave_height_m=wave_h,
            wind_speed_kmh=wind_spd,
        )

        trace_event = {
            "node": "fishing_zone",
            "action": task.task or "evaluate_suitability",
            "status": "completed",
            "details": {
                "location": location,
                "composite_score": pfz_ev.get("data", {}).get("composite_score"),
                "category": pfz_ev.get("data", {}).get("suitability_category"),
            },
        }

        return {
            "pfz_data": pfz_ev.get("data", {}),
            "observations": {"pfz": pfz_ev.get("data", {})},
            "agent_results": {"pfz": pfz_ev.get("data", {})},
            "evidence_items": [pfz_ev],
            "execution_trace": [trace_event],
        }


fishing_agent = FishingAgent()
