"""
ORCA Ocean Analytics Specialist Agent
Executes oceanographic tasks (waves, swell, currents, SST, chlorophyll, tides).
"""

from typing import Any, Dict, List
from graph.state import ORCAState
from services.llm import Task
from tools.registry import tool_registry


class OceanAgent:
    """Specialist agent responsible for oceanographic wave, swell, and satellite parameters."""

    def __init__(self):
        self.name = "ocean_agent"
        self.capability = "ocean"

    def run(self, task: Task, state: ORCAState) -> Dict[str, Any]:
        """Executes oceanographic tools and collects structured evidence."""
        location = task.location
        if not location:
            target_locs = state.get("target_locations", [])
            location = target_locs[0].get("name") if target_locs and isinstance(target_locs[0], dict) else "Ratnagiri"

        marine_ev = tool_registry.execute("fetch_marine_conditions", location_name=location)
        ocean_ev = tool_registry.execute("fetch_ocean_analytics", location_name=location)
        tide_ev = tool_registry.execute("fetch_tide_data", location_name=location)

        new_evidence = [marine_ev, ocean_ev, tide_ev]

        ocean_payload = {
            "source": "Open-Meteo Marine, Satellite Ocean Fixtures, & Harmonic Tides",
            "source_type": "sample",
            "status": ocean_ev.get("status", "available"),
            "locations": [location],
            "marine_telemetry": marine_ev.get("data", {}),
            "ocean_analytics": ocean_ev.get("data", {}),
            "tide_predictions": [tide_ev.get("data", {})],
        }

        # Also update weather_data's marine_data sub-dict if weather_data is present
        weather_payload = state.get("weather_data") or {}
        if weather_payload:
            weather_payload["marine_data"] = marine_ev.get("data", {})

        trace_event = {
            "node": "ocean",
            "action": task.task or "fetch_ocean_metrics",
            "status": "completed",
            "details": {
                "location": location,
                "wave_height": marine_ev.get("data", {}).get("wave_height"),
                "sst_celsius": ocean_ev.get("data", {}).get("sst_celsius"),
                "marine_status": marine_ev.get("status"),
                "ocean_status": ocean_ev.get("status"),
            },
        }

        ret_dict: Dict[str, Any] = {
            "ocean_data": ocean_payload,
            "observations": {"ocean": ocean_payload},
            "agent_results": {"ocean": ocean_payload},
            "evidence_items": new_evidence,
            "execution_trace": [trace_event],
        }
        if weather_payload:
            ret_dict["weather_data"] = weather_payload

        return ret_dict


ocean_agent = OceanAgent()
