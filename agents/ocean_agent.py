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
        """Executes oceanographic tools and collects structured evidence for all target locations."""
        locations: List[str] = []
        if task.location:
            locations = [task.location]
        else:
            raw_locs = state.get("target_locations", [])
            locations = [loc.get("name") if isinstance(loc, dict) else str(loc) for loc in raw_locs]

        if not locations:
            locations = ["Ratnagiri"]

        unique_locations = list(dict.fromkeys(locations))

        new_evidence: List[Dict[str, Any]] = []
        trace_events: List[Dict[str, Any]] = []
        by_location: Dict[str, Any] = {}

        for loc in unique_locations:
            marine_ev = tool_registry.execute("fetch_marine_conditions", location_name=loc)
            ocean_ev = tool_registry.execute("fetch_ocean_analytics", location_name=loc)
            tide_ev = tool_registry.execute("fetch_tide_data", location_name=loc)

            new_evidence.extend([marine_ev, ocean_ev, tide_ev])

            is_available = marine_ev.get("status") == "available"
            trace_event = {
                "node": "ocean",
                "action": task.task or "fetch_ocean_metrics",
                "status": "completed" if is_available else "failed",
                "details": {
                    "location": loc,
                    "wave_height": marine_ev.get("data", {}).get("wave_height"),
                    "swell_height": marine_ev.get("data", {}).get("swell_height"),
                    "sst_celsius": ocean_ev.get("data", {}).get("sst_celsius"),
                    "marine_status": marine_ev.get("status"),
                    "ocean_status": ocean_ev.get("status"),
                },
            }
            trace_events.append(trace_event)

            by_location[loc] = {
                "location": loc,
                "source": "Open-Meteo Marine, Satellite Ocean Fixtures, & Harmonic Tides",
                "source_type": "sample",
                "status": marine_ev.get("status", "available"),
                "marine_telemetry": marine_ev.get("data", {}),
                "ocean_analytics": ocean_ev.get("data", {}),
                "tide_predictions": [tide_ev.get("data", {})],
            }

        primary_loc = unique_locations[0]
        primary_ocean = by_location[primary_loc]

        ocean_payload = {
            "source": "Open-Meteo Marine, Satellite Ocean Fixtures, & Harmonic Tides",
            "source_type": "sample",
            "status": primary_ocean.get("status", "available"),
            "location": primary_loc,
            "locations": unique_locations,
            "marine_telemetry": primary_ocean.get("marine_telemetry", {}),
            "ocean_analytics": primary_ocean.get("ocean_analytics", {}),
            "tide_predictions": primary_ocean.get("tide_predictions", []),
            "by_location": by_location,
        }

        # Also update weather_data's marine_data sub-dict if weather_data is present
        weather_payload = state.get("weather_data") or {}
        if weather_payload:
            weather_payload["marine_data"] = primary_ocean.get("marine_telemetry", {})
            if "by_location" in weather_payload:
                for loc in unique_locations:
                    if loc in weather_payload["by_location"] and loc in by_location:
                        weather_payload["by_location"][loc]["marine_data"] = by_location[loc].get("marine_telemetry", {})

        ret_dict: Dict[str, Any] = {
            "ocean_data": ocean_payload,
            "observations": {"ocean": ocean_payload},
            "agent_results": {"ocean": ocean_payload},
            "evidence_items": new_evidence,
            "execution_trace": trace_events,
        }
        if weather_payload:
            ret_dict["weather_data"] = weather_payload

        return ret_dict


ocean_agent = OceanAgent()
