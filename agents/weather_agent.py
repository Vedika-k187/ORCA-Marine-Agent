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
        """Executes a weather task for the specified location and time horizon."""
        location = task.location
        if not location:
            target_locs = state.get("target_locations", [])
            location = target_locs[0].get("name") if target_locs and isinstance(target_locs[0], dict) else "Ratnagiri"

        time_horizon = task.time_horizon or state.get("time_horizon", "today")

        weather_ev = tool_registry.execute(
            "fetch_marine_weather",
            location_name=location,
            time_horizon=time_horizon,
        )

        trace_event = {
            "node": "weather",
            "action": task.task or "fetch_forecast",
            "status": "completed",
            "details": {
                "source": weather_ev.get("source"),
                "source_type": weather_ev.get("source_type"),
                "status": weather_ev.get("status"),
                "location": location,
                "variables": weather_ev.get("variables", []),
            },
        }

        combined_payload = {
            "source": weather_ev.get("source", "Open-Meteo Weather API"),
            "source_type": weather_ev.get("source_type", "live"),
            "status": weather_ev.get("status", "available"),
            "locations": [location],
            "time_horizon": time_horizon,
            "weather_data": weather_ev.get("data", {}),
            "marine_data": (state.get("weather_data") or {}).get("marine_data", {}),
        }

        return {
            "weather_data": combined_payload,
            "observations": {"weather": combined_payload},
            "agent_results": {"weather": combined_payload},
            "evidence_items": [weather_ev],
            "execution_trace": [trace_event],
        }


weather_agent = WeatherAgent()
