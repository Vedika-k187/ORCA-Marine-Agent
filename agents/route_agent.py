"""
ORCA Route Specialist Agent
Evaluates navigational passages, waypoint clearance, candidate routes,
and deterministic safety scoring.
Explicitly labels all routes as 'ORCA Informational Route — Not Certified for Official Navigation'.
"""

from typing import Any, Dict, List
from graph.state import ORCAState
from services.llm import Task
from tools.geospatial_tools import (
    lookup_coordinates,
    haversine_distance,
    plan_candidate_marine_routes,
    evaluate_route_safety,
)
from tools.advisory_tools import fetch_marine_advisories


class RouteAgent:
    """Specialist agent responsible for navigational waypoints and transit safety."""

    def __init__(self):
        self.name = "route_agent"
        self.capability = "route"

    def run(self, task: Task, state: ORCAState) -> Dict[str, Any]:
        """Calculates candidate route waypoints, distances, hazards, and safety scores."""
        raw_locs = state.get("target_locations", [])
        locs = [l.get("name") if isinstance(l, dict) else str(l) for l in raw_locs]

        # Extract origin and destination
        origin = locs[0] if len(locs) >= 1 else "Ratnagiri"
        destination = locs[1] if len(locs) >= 2 else ("Goa" if origin != "Goa" else "Mumbai")

        # 1. Generate candidate routes
        route_plan = plan_candidate_marine_routes(origin, destination)

        # 2. Collect environmental context for route safety evaluation
        weather_payload = state.get("weather_data") or {}
        weather_inner = weather_payload.get("weather_data") or {}
        marine_inner = weather_payload.get("marine_data") or state.get("ocean_data", {}).get("marine_telemetry") or {}
        advisories = state.get("marine_advisories") or []

        if not advisories:
            adv_res = fetch_marine_advisories(location=origin)
            advisories = adv_res.get("data", {}).get("advisories", [])

        # 3. Evaluate deterministic route safety
        evaluated_route = evaluate_route_safety(
            route=route_plan,
            weather_data=weather_inner,
            marine_data=marine_inner,
            advisories=advisories,
        )

        rec_route = evaluated_route.get("recommended_route") or {}
        dist_km = rec_route.get("total_distance_km") or route_plan.get("great_circle_distance_km", 0.0)

        # Build backward-compatible fields as well
        route_payload = {
            "origin": origin,
            "destination": destination,
            "origin_coordinates": route_plan.get("origin_coordinates"),
            "destination_coordinates": route_plan.get("destination_coordinates"),
            "total_distance_km": dist_km,
            "waypoints": [
                {"name": wp["name"], "coords": (wp["lat"], wp["lon"])}
                for wp in (rec_route.get("waypoints") or [])
            ] or [
                {"name": f"Departure: {origin}", "coords": route_plan.get("origin_coordinates")},
                {"name": f"Arrival: {destination}", "coords": route_plan.get("destination_coordinates")},
            ],
            "candidate_routes": evaluated_route.get("candidate_routes", []),
            "recommended_route": rec_route,
            "hazard_clearance": (
                "Safe offshore corridor avoids coastal shallow shoals and designated Marine Protected Areas."
                if rec_route.get("route_id") == "recommended_offshore"
                else "Caution: Route intersects coastal shallows or regulated marine corridors."
            ),
            "scoring_formula": evaluated_route.get("scoring_formula"),
            "data_classification": "demonstration_sample_route",
            "route_disclaimer": "ORCA Informational Route — Not Certified for Official Navigation.",
        }

        trace_event = {
            "node": "route",
            "action": task.task or "plan_waypoints",
            "status": "completed",
            "details": {
                "origin": origin,
                "destination": destination,
                "distance_km": dist_km,
                "candidate_routes_count": len(evaluated_route.get("candidate_routes", [])),
                "recommended_route_score": rec_route.get("route_score"),
            },
        }

        return {
            "route_data": route_payload,
            "observations": {"route": route_payload},
            "agent_results": {"route": route_payload},
            "execution_trace": [trace_event],
        }


route_agent = RouteAgent()
