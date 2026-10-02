"""
Planner Agent for ORCA
Upgraded for Phase 4: Produces structured task plans, supports LLM-backed planning
with safe Pydantic models, deterministic fallback, session memory context, and what-if simulation.
"""

import re
from typing import Any, Dict, List, Optional
from services.llm import llm_service, PlannerDecision, Task
from agents.registry import capability_registry


class PlannerAgent:
    """
    Decomposes natural language marine queries into structured intents, locations,
    time horizons, required capabilities, and structured subtasks.
    """

    KNOWN_LOCATIONS = [
        "Ratnagiri", "Mumbai", "Goa", "Panaji", "Kochi", "Cochin",
        "Chennai", "Visakhapatnam", "Vizag", "Mangalore", "Porbandar",
        "Veraval", "Kolkata", "Paradip", "Karwar", "Alibaug", "Malvan",
        "Daman", "Diu", "Kandla", "Puri", "Haldia", "Kavaratti",
        "Port Blair", "Tuticorin", "Thoothukudi", "Bhavnagar", "Gopalpur",
    ]

    TEMPORAL_KEYWORDS = {
        "tomorrow morning and evening": "compare_morning_evening",
        "tomorrow morning": "tomorrow_morning",
        "tomorrow evening": "tomorrow_evening",
        "tomorrow": "tomorrow",
        "next 12 hours": "next_12h",
        "12 hours": "next_12h",
        "next 6 hours": "next_6h",
        "next 24 hours": "next_24h",
        "24 hours": "next_24h",
        "next 48 hours": "next_48h",
        "48 hours": "next_48h",
        "next week": "next_week",
        "this weekend": "this_weekend",
        "today": "today",
        "tonight": "tonight",
        "now": "immediate",
        "immediate": "immediate",
        "was the sea rough": "historical_yesterday",
        "yesterday": "historical_yesterday",
        "historical": "historical",
        "past": "historical",
    }

    def parse_temporal_scope(self, lower_query: str, time_horizon: str) -> Dict[str, Any]:
        """
        Parses granular temporal scopes distinguishing:
        CURRENT, TODAY, TOMORROW, NEXT_N_HOURS, NEXT_N_DAYS, HISTORICAL, WHAT_IF.
        """
        scope = "TODAY"
        sub_period = None
        hours_ahead = None

        if "what if" in lower_query:
            scope = "WHAT_IF"
        elif any(k in lower_query for k in ["yesterday", "was ", "past", "historical"]) or "historical" in time_horizon:
            scope = "HISTORICAL"
            sub_period = "yesterday"
        elif "tomorrow" in time_horizon or "tomorrow" in lower_query:
            scope = "TOMORROW"
            if "morning and evening" in lower_query or "morning vs evening" in lower_query:
                sub_period = "morning_and_evening"
            elif "morning" in lower_query:
                sub_period = "morning"
            elif "evening" in lower_query:
                sub_period = "evening"
            elif "afternoon" in lower_query:
                sub_period = "afternoon"
        elif "12h" in time_horizon or "12 hours" in lower_query:
            scope = "NEXT_N_HOURS"
            hours_ahead = 12
        elif "6h" in time_horizon or "6 hours" in lower_query:
            scope = "NEXT_N_HOURS"
            hours_ahead = 6
        elif "24h" in time_horizon or "24 hours" in lower_query:
            scope = "NEXT_N_HOURS"
            hours_ahead = 24
        elif "48h" in time_horizon or "48 hours" in lower_query or "weekend" in lower_query or "week" in lower_query:
            scope = "NEXT_N_DAYS"
        elif "now" in lower_query or "immediate" in time_horizon:
            scope = "CURRENT"

        return {
            "scope": scope,
            "sub_period": sub_period,
            "hours_ahead": hours_ahead,
            "normalized_tag": time_horizon,
        }

    def __init__(self, model_name: str = "offline"):
        self.model_name = model_name

    def plan(
        self,
        query: str,
        language: str = "en",
        session_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main planning interface.
        If an LLM backend is configured and enabled, attempts structured LLM planning.
        Always safely falls back to deterministic rule-based planning.
        """
        fallback_factory = lambda: self._plan_heuristically(query, language, session_context)

        if llm_service.is_enabled():
            prompt = (
                f"Analyze the marine query: '{query}'. "
                f"Identify intent, locations, time horizon, and necessary capabilities."
            )
            try:
                decision = llm_service.generate_structured_output(
                    prompt=prompt,
                    response_model=PlannerDecision,
                    fallback_factory=fallback_factory,
                )
                return self._decision_to_dict(decision, query, language)
            except Exception:
                return fallback_factory()

        return fallback_factory()

    def _plan_heuristically(
        self,
        query: str,
        language: str,
        session_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deterministic rule-based query parser and task planner."""
        lower_query = query.lower()

        # 1. Detect locations in the current query
        detected_locations: List[str] = []
        for loc in self.KNOWN_LOCATIONS:
            if re.search(r"\b" + re.escape(loc.lower()) + r"\b", lower_query):
                if loc not in detected_locations:
                    detected_locations.append(loc)

        # Regex fallback for "near <Location>", "off <Location>", "at <Location>", "around <Location>"
        pattern = r"\b(?:near|off|at|around|port of|coast of)\s+([A-Z][a-zA-Z]+)"
        for match in re.finditer(pattern, query):
            loc_candidate = match.group(1)
            if loc_candidate not in detected_locations:
                detected_locations.append(loc_candidate)

        # Session memory resolution: if query has anaphoric references ("which one", "what if", "there")
        session_locs = (session_context or {}).get("context_locations") or []
        if not detected_locations and session_locs:
            if any(w in lower_query for w in ["which", "what if", "there", "both", "either", "between"]):
                detected_locations = list(session_locs)

        # 2. Detect temporal horizon
        time_horizon = "today"
        for kw, normalized in self.TEMPORAL_KEYWORDS.items():
            if kw in lower_query:
                time_horizon = normalized
                break
        if time_horizon == "today" and (session_context or {}).get("context_time_horizon"):
            if "tomorrow" in (session_context.get("context_time_horizon") or ""):
                time_horizon = session_context.get("context_time_horizon")

        # 3. Detect What-If hypothetical parameter and value
        is_what_if = False
        what_if_param = None
        what_if_val = None

        what_if_match = re.search(r"what if\s+([a-zA-Z\s]+?)\s+(?:increases to|reaches|is|becomes|drops to)\s+([\d.]+)", lower_query)
        if what_if_match:
            is_what_if = True
            raw_param = what_if_match.group(1).strip()
            what_if_val = float(what_if_match.group(2).strip())
            if "wind" in raw_param:
                what_if_param = "wind_speed"
            elif "wave" in raw_param:
                what_if_param = "wave_height"
            elif "chlorophyll" in raw_param:
                what_if_param = "chlorophyll"
        elif "what if" in lower_query:
            is_what_if = True
            if "wind" in lower_query:
                what_if_param = "wind_speed"
                num_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:km/h|knots|mps)?", lower_query)
                what_if_val = float(num_match.group(1)) if num_match else 30.0

        # 4. Detect Intent
        intent = self._detect_intent(lower_query, detected_locations)

        # 5. Granular temporal scope
        temporal_scope = self.parse_temporal_scope(lower_query, time_horizon)

        # 6. Determine required capabilities and subtasks
        capabilities, subtasks = self._build_capabilities_and_subtasks(
            intent, detected_locations, time_horizon, lower_query, is_what_if, what_if_param, what_if_val
        )

        return {
            "query": query,
            "language": language,
            "intent": intent,
            "locations": detected_locations,
            "target_locations": [{"name": loc} for loc in detected_locations],
            "time_horizon": time_horizon,
            "temporal_scope": temporal_scope,
            "required_capabilities": capabilities,
            "subtasks": subtasks,
            "is_what_if": is_what_if,
            "what_if_parameter": what_if_param,
            "what_if_value": what_if_val,
            "reasoning_summary": f"Decomposed into intent '{intent}' targeting {detected_locations or 'general coast'} ({temporal_scope.get('scope')})",
        }

    def _detect_intent(self, lower_query: str, locations: List[str]) -> str:
        """Classifies intent using hierarchical keyword heuristics."""
        is_comparison = any(
            w in lower_query for w in ["compare", " vs ", "versus", "better than", "which is safer", "which has", "which one", "between "]
        ) or (len(locations) >= 2 and any(w in lower_query for w in [" or ", "and"]))

        if is_comparison:
            return "location_comparison"

        # Marine advisories & alerts
        if any(w in lower_query for w in ["marine warning", "marine warnings", "weather warning", "weather warnings", "cyclone", "advisories", "advisory", "bulletin", "high wave alert"]) or \
           ("warning" in lower_query and "safe" not in lower_query):
            return "advisory_check"

        # Route planning
        if any(w in lower_query for w in ["route", "waypoint", "navigation", "navigate", "voyage", "course", "passage"]):
            return "route_planning"

        # Safety & restriction queries (including what-if scenario simulations)
        if any(w in lower_query for w in ["safe", "safety", "danger", "dangerous", "warning", "caution", "risk", "can i fish", "is it safe", "restricted", "sanctuary", "exclusion", "prohibited", "geofence", "boundary", "what if"]):
            return "safety_check"

        # Fishing zone / PFZ queries
        if any(w in lower_query for w in ["fishing zone", "fishing zones", "fish zone", "pfz", "potential fishing zone", "catch fish", "best catch", "fishing spot", "where to fish", "find fishing", "nearby fishing", "favourable fishing"]):
            return "fishing_zone"

        # Environmental / oceanographic analysis
        if any(w in lower_query for w in ["temperature", "sst", "chlorophyll", "current", "salinity", "swell", "wave height", "tide"]):
            return "environmental_analysis"

        # Fallback general query
        return "general_marine_query"

    def _build_capabilities_and_subtasks(
        self,
        intent: str,
        locations: List[str],
        time_horizon: str,
        lower_query: str = "",
        is_what_if: bool = False,
        what_if_param: Optional[str] = None,
        what_if_val: Optional[float] = None,
    ) -> tuple[List[str], List[Dict[str, Any]]]:
        """Constructs list of capabilities and structured subtasks for LangGraph routing."""
        loc_desc = ", ".join(locations) if locations else "specified marine zone"

        if intent == "safety_check":
            is_zone_inquiry = any(
                w in lower_query for w in ["restricted", "sanctuary", "exclusion", "prohibited", "geofence", "boundary"]
            )
            if is_zone_inquiry:
                capabilities = ["geospatial", "weather", "risk"]
                subtasks = [
                    {
                        "agent": "geospatial",
                        "action": "check_marine_zones",
                        "description": f"Query marine zone boundaries, MPA restrictions, and exclusion corridors for {loc_desc}",
                    },
                    {
                        "agent": "weather",
                        "action": "fetch_forecast",
                        "description": f"Fetch meteorological conditions for {loc_desc}",
                    },
                    {
                        "agent": "risk_assessment",
                        "action": "regulatory_safety_audit",
                        "description": f"Audit regulatory and environmental compliance for {loc_desc}",
                    },
                ]
            else:
                capabilities = ["weather", "ocean", "risk"]
                subtasks = [
                    {
                        "agent": "weather",
                        "action": "fetch_forecast",
                        "description": f"Fetch wind, wind gusts, and precipitation forecast for {loc_desc} ({time_horizon})",
                    },
                    {
                        "agent": "ocean_analytics",
                        "action": "fetch_wave_data",
                        "description": f"Fetch wave height, swell period, and sea currents for {loc_desc}",
                    },
                    {
                        "agent": "risk_assessment",
                        "action": "compute_risk_index",
                        "description": f"Synthesize weather and oceanographic factors to determine safety index for {loc_desc}",
                        "what_if_active": is_what_if,
                        "what_if_parameter": what_if_param,
                        "what_if_value": what_if_val,
                    },
                ]
        elif intent == "location_comparison":
            capabilities = ["geospatial", "weather", "ocean", "risk"]
            subtasks = [
                {
                    "agent": "geospatial",
                    "action": "resolve_boundaries",
                    "description": f"Resolve coastal coordinates and bounding areas for {loc_desc}",
                },
                {
                    "agent": "weather",
                    "action": "compare_weather",
                    "description": f"Compare meteorological conditions across target locations ({time_horizon})",
                },
                {
                    "agent": "ocean_analytics",
                    "action": "compare_ocean_metrics",
                    "description": f"Compare sea surface temperature, currents, and wave metrics",
                },
                {
                    "agent": "risk_assessment",
                    "action": "comparative_risk",
                    "description": f"Compute comparative safety rating between locations",
                },
            ]
        elif intent == "advisory_check":
            capabilities = ["alert", "weather", "ocean", "geospatial"]
            subtasks = [
                {
                    "agent": "alert",
                    "action": "fetch_advisories",
                    "description": f"Query active marine bulletins, squall alerts, and high swell warnings for {loc_desc} ({time_horizon})",
                },
                {
                    "agent": "weather",
                    "action": "fetch_forecast",
                    "description": f"Fetch live wind and gust telemetry for {loc_desc}",
                },
                {
                    "agent": "ocean_analytics",
                    "action": "fetch_wave_data",
                    "description": f"Fetch live wave height and swell metrics for {loc_desc}",
                },
                {
                    "agent": "geospatial",
                    "action": "check_marine_zones",
                    "description": f"Check affected coastal zones and boundary buffers for {loc_desc}",
                },
            ]
        elif intent == "route_planning":
            capabilities = ["geospatial", "weather", "risk"]
            subtasks = [
                {
                    "agent": "geospatial",
                    "action": "plan_waypoints",
                    "description": f"Calculate route waypoints, bathymetry clearance, and maritime hazard zones for {loc_desc}",
                },
                {
                    "agent": "weather",
                    "action": "fetch_route_weather",
                    "description": f"Assess wind, wave, and visibility conditions along route corridor",
                },
                {
                    "agent": "risk_assessment",
                    "action": "route_safety_audit",
                    "description": f"Perform navigational hazard and safety audit for planned route",
                },
            ]
        elif intent == "fishing_zone":
            capabilities = ["ocean", "weather", "risk"]
            subtasks = [
                {
                    "agent": "ocean_analytics",
                    "action": "fetch_pfz_advisories",
                    "description": f"Locate thermal fronts and potential fishing zones for {loc_desc}",
                },
                {
                    "agent": "weather",
                    "action": "verify_sea_conditions",
                    "description": f"Verify wind and wave safety for harvesting in fishing zones",
                },
                {
                    "agent": "risk_assessment",
                    "action": "harvest_risk_assessment",
                    "description": f"Evaluate navigational and operational risk for fishing expedition",
                },
            ]
        elif intent == "environmental_analysis":
            capabilities = ["ocean", "weather"]
            subtasks = [
                {
                    "agent": "ocean_analytics",
                    "action": "fetch_oceanographic_indices",
                    "description": f"Extract SST, chlorophyll concentration, and surface currents for {loc_desc}",
                },
                {
                    "agent": "weather",
                    "action": "fetch_atmospheric_context",
                    "description": f"Retrieve atmospheric conditions influencing marine parameters",
                },
            ]
        else:  # general_marine_query
            capabilities = []
            subtasks = [
                {
                    "agent": "general_knowledge",
                    "action": "synthesize_informational_response",
                    "description": "Formulate informational response for marine domain inquiry",
                }
            ]

        return capabilities, subtasks

    def _decision_to_dict(self, decision: PlannerDecision, query: str, language: str) -> Dict[str, Any]:
        """Converts structured Pydantic PlannerDecision into workflow state dict."""
        return {
            "query": query,
            "language": language,
            "intent": decision.intent,
            "locations": decision.locations,
            "target_locations": [{"name": loc} for loc in decision.locations],
            "time_horizon": decision.time_horizon,
            "required_capabilities": decision.required_capabilities,
            "subtasks": [t.model_dump() for t in decision.tasks],
            "is_what_if": decision.is_what_if,
            "what_if_parameter": decision.what_if_parameter,
            "what_if_value": decision.what_if_value,
            "reasoning_summary": decision.reasoning_summary,
        }
