"""
ORCA Marine Alert Specialist Agent
Ingests, filters, and ranks marine advisories, high swell bulletins,
and severe storm warnings for coastal areas and transit corridors.
"""

from typing import Any, Dict, List, Optional
from graph.state import ORCAState
from services.llm import Task
from tools.advisory_tools import fetch_marine_advisories, classify_advisory_severity, SEVERITY_WEIGHTS


class AlertAgent:
    """Specialist agent responsible for marine advisories and coastal weather warnings."""

    def __init__(self):
        self.name = "alert_agent"
        self.capability = "alert"

    def run(self, task: Task, state: ORCAState) -> Dict[str, Any]:
        """Queries and ranks active marine advisories relevant to the user query."""
        raw_locs = state.get("target_locations", [])
        locs = [l.get("name") if isinstance(l, dict) else str(l) for l in raw_locs]
        location_name = task.location or (locs[0] if locs else "Ratnagiri")
        time_horizon = task.time_horizon or state.get("time_horizon", "today")

        evidence = fetch_marine_advisories(location=location_name, time_horizon=time_horizon)
        adv_data = evidence.get("data", {})
        advisories: List[Dict[str, Any]] = adv_data.get("advisories", [])

        # Rank by severity
        advisories.sort(
            key=lambda a: SEVERITY_WEIGHTS.get(classify_advisory_severity(a), 0),
            reverse=True,
        )

        critical_count = sum(1 for a in advisories if classify_advisory_severity(a) in ["CRITICAL", "SEVERE"])
        warning_count = sum(1 for a in advisories if classify_advisory_severity(a) == "WARNING")
        advisory_count = sum(1 for a in advisories if classify_advisory_severity(a) == "ADVISORY")

        alert_summary = {
            "location": location_name,
            "time_horizon": time_horizon,
            "total_advisories": len(advisories),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "advisory_count": advisory_count,
            "max_severity": adv_data.get("max_severity", "NONE"),
            "has_active_warnings": (critical_count + warning_count) > 0,
            "top_headline": advisories[0].get("headline") if advisories else "No active marine warnings in this sector.",
        }

        trace_event = {
            "node": "alert",
            "action": task.task or "fetch_advisories",
            "status": "completed",
            "details": alert_summary,
        }

        return {
            "marine_advisories": advisories,
            "observations": {"alerts": alert_summary},
            "agent_results": {"alerts": alert_summary},
            "evidence_items": [evidence],
            "execution_trace": [trace_event],
        }


alert_agent = AlertAgent()
