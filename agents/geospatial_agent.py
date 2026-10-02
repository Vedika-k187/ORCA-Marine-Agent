"""
ORCA Geospatial Specialist Agent
Executes coordinate resolution, geofence boundary checks, and marine zone spatial queries.
"""

from typing import Any, Dict, List
from graph.state import ORCAState
from services.llm import Task
from tools.registry import tool_registry


class GeospatialAgent:
    """Specialist agent responsible for spatial reasoning, geofencing, and proximity checks."""

    def __init__(self):
        self.name = "geospatial_agent"
        self.capability = "geospatial"

    def run(self, task: Task, state: ORCAState) -> Dict[str, Any]:
        """Executes geospatial tools using Shapely and GeoPandas."""
        locations: List[str] = []
        if task.location:
            locations = [task.location]
        else:
            raw_locs = state.get("target_locations", [])
            locations = [loc.get("name") if isinstance(loc, dict) else str(loc) for loc in raw_locs]

        if not locations:
            locations = ["Ratnagiri"]

        new_evidence: List[Dict[str, Any]] = []
        geo_results: Dict[str, Any] = {}

        for loc in locations:
            g_ev = tool_registry.execute("evaluate_geospatial_context", location_name=loc)
            new_evidence.append(g_ev)
            geo_results[loc] = g_ev.get("data", {})

        # If comparison between locations is needed
        comparison_result = None
        if len(locations) >= 2:
            comp_ev = tool_registry.execute("compare_coastal_locations", loc1=locations[0], loc2=locations[1])
            new_evidence.append(comp_ev)
            comparison_result = comp_ev.get("data", {})

        # If route planning is requested
        route_result = None
        if state.get("intent") == "route_planning" or any("route" in str(t.get("action", "")) for t in state.get("task_plan", [])):
            from agents.route_agent import route_agent
            r_out = route_agent.run(task, state)
            route_result = r_out.get("route_data")

        geo_payload = {
            "source": "ORCA Geospatial Engine (Shapely/GeoPandas) & Sample Marine Zones",
            "source_type": "sample",
            "status": "available",
            "locations": locations,
            "contexts": geo_results,
            "comparison": comparison_result,
            "route_data": route_result,
        }

        trace_event = {
            "node": "geospatial",
            "action": task.task or "resolve_boundaries",
            "status": "completed",
            "details": {
                "source_type": "sample",
                "locations": locations,
                "has_comparison": comparison_result is not None,
                "has_route": route_result is not None,
            },
        }

        ret = {
            "geospatial_data": geo_payload,
            "observations": {"geospatial": geo_payload},
            "agent_results": {"geospatial": geo_payload},
            "evidence_items": new_evidence,
            "execution_trace": [trace_event],
        }
        if route_result:
            ret["route_data"] = route_result
            ret["observations"]["route"] = route_result
            ret["agent_results"]["route"] = route_result
        return ret


geospatial_agent = GeospatialAgent()
