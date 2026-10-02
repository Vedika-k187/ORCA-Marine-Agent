"""
ORCA Weather Specialist Agent
Executes meteorological tasks by invoking approved deterministic weather tools.
"""

from typing import Any, Dict, List
from graph.state import ORCAState
from services.llm import Task
from tools.registry import tool_registry


class WeatherAgent:
    """Specialist agent responsible for atmospheric and wind forecast tasks."""

    def __init__(self):
        self.name = "weather_agent"
        self.capability = "weather"

    def run(self, task: Task, state: ORCAState) -> Dict[str, Any]:
        """Executes a weather task for the specified location(s) and time horizon."""
        time_horizon = task.time_horizon or state.get("time_horizon", "today")

        locations: List[str] = []
        if task.location:
            locations = [task.location]
        else:
            raw_locs = state.get("target_locations", [])
            locations = [loc.get("name") if isinstance(loc, dict) else str(loc) for loc in raw_locs]

        if not locations:
            locations = ["Ratnagiri"]

        # Ensure no duplicates while preserving order
        unique_locations = list(dict.fromkeys(locations))

        evidence_items: List[Dict[str, Any]] = []
        trace_events: List[Dict[str, Any]] = []
        by_location: Dict[str, Any] = {}

        for loc in unique_locations:
            weather_ev = tool_registry.execute(
                "fetch_marine_weather",
                location_name=loc,
                time_horizon=time_horizon,
            )
            evidence_items.append(weather_ev)

            is_available = weather_ev.get("status") == "available"
            trace_event = {
                "node": "weather",
                "action": task.task or "fetch_forecast",
                "status": "completed" if is_available else "failed",
                "details": {
                    "source": weather_ev.get("source"),
                    "source_type": weather_ev.get("source_type"),
                    "status": weather_ev.get("status"),
                    "location": loc,
                    "variables": weather_ev.get("variables", []),
                    "wind_speed": weather_ev.get("data", {}).get("wind_speed"),
                    "wind_gusts": weather_ev.get("data", {}).get("wind_gusts"),
                },
            }
            trace_events.append(trace_event)

            by_location[loc] = {
                "location": loc,
                "source": weather_ev.get("source", "Open-Meteo Weather API"),
                "source_type": weather_ev.get("source_type", "live"),
                "status": weather_ev.get("status", "available"),
                "time_horizon": time_horizon,
                "weather_data": weather_ev.get("data", {}),
            }

        primary_loc = unique_locations[0]
        primary_obs = by_location[primary_loc]

        combined_payload = {
            "source": primary_obs.get("source", "Open-Meteo Weather API"),
            "source_type": primary_obs.get("source_type", "live"),
            "status": primary_obs.get("status", "available"),
            "location": primary_loc,
            "locations": unique_locations,
            "time_horizon": time_horizon,
            "weather_data": primary_obs.get("weather_data", {}),
            "marine_data": (state.get("weather_data") or {}).get("marine_data", {}),
            "by_location": by_location,
        }

        return {
            "weather_data": combined_payload,
            "observations": {"weather": combined_payload},
            "agent_results": {"weather": combined_payload},
            "evidence_items": evidence_items,
            "execution_trace": trace_events,
        }


weather_agent = WeatherAgent()
