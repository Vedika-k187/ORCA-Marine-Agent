"""
ORCA Comparison Specialist Agent
Performs dual-location comparative analytics across climatology, sea state, and distances.
"""

from typing import Any, Dict, List
from graph.state import ORCAState
from services.llm import Task
from tools.registry import tool_registry


class ComparisonAgent:
    """Specialist agent responsible for comparative location profiling."""

    def __init__(self):
        self.name = "comparison_agent"
        self.capability = "comparison"

    def run(self, task: Task, state: ORCAState) -> Dict[str, Any]:
        """Executes multi-location comparative tool."""
        raw_locs = state.get("target_locations", [])
        locs = [l.get("name") if isinstance(l, dict) else str(l) for l in raw_locs]

        if len(locs) < 2:
            loc1, loc2 = "Ratnagiri", "Goa"
        else:
            loc1, loc2 = locs[0], locs[1]

        comp_ev = tool_registry.execute("compare_coastal_locations", loc1=loc1, loc2=loc2)

        trace_event = {
            "node": "comparison",
            "action": task.task or "compare_locations",
            "status": "completed",
            "details": {
                "location_a": loc1,
                "location_b": loc2,
                "geodesic_distance_km": comp_ev.get("data", {}).get("geodesic_distance_km"),
            },
        }

        return {
            "observations": {"comparison": comp_ev.get("data", {})},
            "agent_results": {"comparison": comp_ev.get("data", {})},
            "evidence_items": [comp_ev],
            "execution_trace": [trace_event],
        }


comparison_agent = ComparisonAgent()
