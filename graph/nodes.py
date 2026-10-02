"""
ORCA LangGraph Nodes
Phase 4: Integrates specialized agents, observation evaluation, dynamic replanning,
session memory persistence, and what-if simulation reporting.
"""

from typing import Any, Dict, List
from graph.state import ORCAState
from agents.planner import PlannerAgent
from agents.weather_agent import weather_agent
from agents.ocean_agent import ocean_agent
from agents.geospatial_agent import geospatial_agent
from agents.fishing_agent import fishing_agent
from agents.comparison_agent import comparison_agent
from agents.risk_agent import risk_agent
from agents.alert_agent import alert_agent
from agents.route_agent import route_agent
from agents.evidence_agent import evidence_agent
from services.llm import Task
from services.evaluator import evaluate_observations, generate_replan_decision


def planner_node(state: ORCAState) -> Dict[str, Any]:
    """
    Decomposes natural language query into intents, locations, time horizons,
    and required capabilities, incorporating multi-turn session memory.
    """
    query = state.get("query", "")
    language = state.get("language", "en")

    session_context = {
        "context_locations": state.get("context_locations", []),
        "context_time_horizon": state.get("context_time_horizon", "today"),
        "conversation_history": state.get("conversation_history", []),
    }

    planner = PlannerAgent()
    plan = planner.plan(query, language=language, session_context=session_context)

    trace_event = {
        "node": "planner",
        "action": "task_decomposition",
        "status": "completed",
        "details": {
            "intent": plan["intent"],
            "locations": plan["locations"],
            "time_horizon": plan["time_horizon"],
            "required_capabilities": plan["required_capabilities"],
            "subtask_count": len(plan["subtasks"]),
            "is_what_if": plan.get("is_what_if", False),
        },
    }

    # Remember locations for session context
    context_locs = plan["locations"] if plan["locations"] else state.get("context_locations", [])

    return {
        "intent": plan["intent"],
        "target_locations": plan["target_locations"],
        "time_horizon": plan["time_horizon"],
        "temporal_scope": plan.get("temporal_scope"),
        "task_plan": plan["subtasks"],
        "context_locations": context_locs,
        "context_intent": plan["intent"],
        "context_time_horizon": plan["time_horizon"],
        "is_what_if": plan.get("is_what_if", False),
        "what_if_parameter": plan.get("what_if_parameter"),
        "what_if_value": plan.get("what_if_value"),
        "observations": {"planner": plan},
        "agent_results": {"planner": plan},
        "execution_trace": [trace_event],
    }


def weather_node(state: ORCAState) -> Dict[str, Any]:
    """Invokes WeatherAgent to collect meteorological forecast telemetry for target locations."""
    raw_locs = state.get("target_locations", [])
    locations = [
        loc.get("name") if isinstance(loc, dict) else str(loc)
        for loc in raw_locs
    ]
    # Execute for each location during multi-location comparisons; otherwise target primary location
    if state.get("intent") == "location_comparison" and len(locations) > 1:
        loc = None
    else:
        loc = locations[0] if locations else "Ratnagiri"

    task = Task(
        task="fetch_forecast",
        capability="weather",
        location=loc,
        time_horizon=state.get("time_horizon", "today"),
    )
    return weather_agent.run(task, state)


def ocean_node(state: ORCAState) -> Dict[str, Any]:
    """Invokes OceanAgent to collect wave telemetry, satellite SST, chlorophyll, and tides for target locations."""
    raw_locs = state.get("target_locations", [])
    locations = [
        loc.get("name") if isinstance(loc, dict) else str(loc)
        for loc in raw_locs
    ]
    # Execute for each location during multi-location comparisons; otherwise target primary location
    if state.get("intent") == "location_comparison" and len(locations) > 1:
        loc = None
    else:
        loc = locations[0] if locations else "Ratnagiri"

    task = Task(
        task="fetch_ocean_metrics",
        capability="ocean",
        location=loc,
    )
    res = ocean_agent.run(task, state)

    # Also calculate PFZ suitability if fishing_zone capability was requested or query is fishing-related
    if state.get("intent") in ["fishing_zone", "location_comparison"] or "fishing_zone" in state.get("task_plan", []):
        f_res = fishing_agent.run(task, state)
        res["pfz_data"] = f_res.get("pfz_data")
        res["observations"]["pfz"] = f_res.get("pfz_data")
        res["agent_results"]["pfz"] = f_res.get("pfz_data")
        res["evidence_items"].extend(f_res.get("evidence_items", []))
    else:
        # Include baseline demonstration PFZ suitability for consistency
        f_res = fishing_agent.run(task, state)
        res["pfz_data"] = f_res.get("pfz_data")

    return res


def geospatial_node(state: ORCAState) -> Dict[str, Any]:
    """Invokes GeospatialAgent to resolve coordinates, geofencing, and proximity."""
    task = Task(
        task="resolve_boundaries",
        capability="geospatial",
    )
    return geospatial_agent.run(task, state)


def risk_node(state: ORCAState) -> Dict[str, Any]:
    """Invokes RiskAgent to perform multi-parameter risk evaluation and what-if simulation."""
    task = Task(
        task="risk_evaluation",
        capability="risk",
        parameters={
            "what_if_parameter": state.get("what_if_parameter"),
            "what_if_value": state.get("what_if_value"),
        },
    )
    return risk_agent.run(task, state)


def alert_node(state: ORCAState) -> Dict[str, Any]:
    """Invokes AlertAgent to query and rank marine advisories and coastal weather warnings."""
    raw_locs = state.get("target_locations", [])
    loc_name = (raw_locs[0].get("name") if raw_locs and isinstance(raw_locs[0], dict) else "Ratnagiri")
    task = Task(
        task="fetch_advisories",
        capability="alert",
        location=loc_name,
        time_horizon=state.get("time_horizon", "today"),
    )
    return alert_agent.run(task, state)


def route_node(state: ORCAState) -> Dict[str, Any]:
    """Invokes RouteAgent to plan candidate passages, calculate distances and evaluate safety."""
    task = Task(
        task="plan_candidate_routes",
        capability="route",
    )
    return route_agent.run(task, state)


def evaluator_node(state: ORCAState) -> Dict[str, Any]:
    """
    Evaluates accumulated evidence sufficiency, correlates observations across agents,
    and determines if replanning is needed.
    """
    evidence_items = state.get("evidence_items", [])
    required_caps = state.get("agent_results", {}).get("planner", {}).get("required_capabilities", [])
    replan_count = state.get("replan_count", 0)
    max_replans = state.get("max_replans", 3)

    eval_result = evaluate_observations(
        evidence_items=evidence_items,
        requested_capabilities=required_caps,
        replan_count=replan_count,
        max_replans=max_replans,
    )

    replan_decision = generate_replan_decision(
        evaluation_result=eval_result,
        state=state,
        replan_count=replan_count,
        max_replans=max_replans,
    )

    eval_result["decision"] = replan_decision.model_dump()

    # Correlate evidence across active agents deterministically
    corr_task = Task(task="correlate_evidence", capability="evidence")
    corr_res = evidence_agent.run(corr_task, state)
    corr_data = corr_res.get("evidence_correlation")

    return {
        "evaluation_summary": eval_result,
        "evidence_correlation": corr_data,
    }


def replan_node(state: ORCAState) -> Dict[str, Any]:
    """
    Executes replanning loop by injecting secondary/fallback tasks into task plan.
    """
    replan_count = state.get("replan_count", 0) + 1
    eval_summary = state.get("evaluation_summary") or {}
    decision_dict = eval_summary.get("decision") or {}
    new_tasks = decision_dict.get("new_tasks") or []

    replan_event = {
        "replan_iteration": replan_count,
        "reason": decision_dict.get("reason", "Missing evidence"),
        "injected_tasks": [t.get("task") if isinstance(t, dict) else t.task for t in new_tasks],
    }

    trace_event = {
        "node": "replan",
        "action": "replan_execution",
        "status": "completed",
        "details": replan_event,
    }

    # Add injected task capabilities to agent_results planner required_capabilities
    updated_plan = list(state.get("task_plan", []))
    for t in new_tasks:
        t_dict = t if isinstance(t, dict) else t.model_dump()
        updated_plan.append(t_dict)

    return {
        "replan_count": replan_count,
        "task_plan": updated_plan,
        "replan_history": [replan_event],
        "execution_trace": [trace_event],
    }


def response_node(state: ORCAState) -> Dict[str, Any]:
    """
    Synthesizes the final evidence-aware marine dossier.
    Distinguishes LIVE, SAMPLE, and HISTORICAL data. Reports what-if impacts and replanning actions.
    """
    query = state.get("query", "")
    intent = state.get("intent", "general_marine_query")
    raw_locs = state.get("target_locations", [])
    locations = [
        loc.get("name") if isinstance(loc, dict) else str(loc)
        for loc in raw_locs
    ]
    loc_str = ", ".join(locations) if locations else "General Coastal Zone"
    time_horizon = state.get("time_horizon", "today")

    evidence_items: List[Dict[str, Any]] = state.get("evidence_items", [])
    weather_payload = state.get("weather_data") or {}
    weather_inner = weather_payload.get("weather_data") or {}
    marine_inner = weather_payload.get("marine_data") or state.get("ocean_data", {}).get("marine_telemetry") or {}
    ocean_payload = state.get("ocean_data") or {}
    ocean_inner = ocean_payload.get("ocean_analytics") or {}
    pfz_inner = state.get("pfz_data") or ocean_payload.get("pfz_suitability") or {}
    geo_payload = state.get("geospatial_data") or {}

    risk = state.get("risk_assessment") or {}
    risk_level = risk.get("risk_level", "UNKNOWN")
    risk_reason = risk.get("reason", "Real marine observations are not connected yet.")

    # Inventory evidence items by classification with location attribution
    live_sources = []
    sample_sources = []
    historical_sources = []
    unavailable_items = []

    for e in evidence_items:
        src = e.get("source", "Unknown Source")
        e_loc = e.get("location")
        src_label = f"{src} ({e_loc})" if e_loc else src
        stype = e.get("source_type")
        status = e.get("status")

        if status in ["unavailable", "error"]:
            err_msg = e.get("data", {}).get("error", "feed offline")
            unavailable_items.append(f"{src_label} [{err_msg}]")
        elif stype == "live" and status == "available":
            live_sources.append(src_label)
        elif stype == "sample" and status == "available":
            sample_sources.append(src_label)
        elif stype == "historical":
            historical_sources.append(src_label)

    lines = [
        "### ORCA Marine Intelligence Report",
        f"**User Query:** {query}",
        f"**Detected Intent:** `{intent}`",
        f"**Target Location(s):** {loc_str}",
        f"**Time Horizon:** {time_horizon}",
        "",
        "#### 1. Data Provenance & Evidence Classification",
    ]

    if live_sources:
        lines.append(f"- **LIVE Telemetry Sources:** {', '.join(sorted(set(live_sources)))}")
    else:
        lines.append("- **LIVE Telemetry Sources:** *None engaged for this query.*")

    if sample_sources:
        lines.append(f"- **SAMPLE Data Sources:** {', '.join(sorted(set(sample_sources)))}")

    if historical_sources:
        lines.append(f"- **HISTORICAL Baselines:** {', '.join(sorted(set(historical_sources)))}")

    if unavailable_items:
        lines.append(f"- **UNAVAILABLE / Failed Sources:** {', '.join(sorted(set(unavailable_items)))}")

    # Section 2: Sensor & Tool Observations
    lines.extend([
        "",
        "#### 2. Deterministic Observations",
    ])

    w_by_loc = weather_payload.get("by_location") or {}
    o_by_loc = ocean_payload.get("by_location") or {}
    pfz_by_loc = (state.get("pfz_data") or {}).get("by_location") or {}

    is_multi_location = len(locations) >= 2 or len(w_by_loc) >= 2

    if is_multi_location:
        failed_locs = []
        successful_locs = []

        for loc in locations:
            loc_w = w_by_loc.get(loc, {})
            loc_o = o_by_loc.get(loc, {})
            w_avail = loc_w.get("status") == "available"
            m_avail = loc_o.get("status") == "available"

            if w_avail and m_avail:
                successful_locs.append(loc)
            else:
                failed_locs.append(loc)

            lines.extend([
                "",
                f"##### Observations for {loc}:",
            ])

            if w_avail:
                w_dat = loc_w.get("weather_data", {})
                w_temp = w_dat.get("temperature", "N/A")
                w_spd = w_dat.get("wind_speed", "N/A")
                w_gst = w_dat.get("wind_gusts", "N/A")
                w_cond = w_dat.get("weather_condition", "N/A")
                lines.append(f"- **Wind & Atmosphere (LIVE):** {w_spd} km/h (Gusts: {w_gst} km/h) | Temp: {w_temp}°C | Condition: {w_cond}")
            else:
                lines.append(f"- **Wind & Atmosphere:** `[UNAVAILABLE]` Live weather telemetry unavailable for {loc}.")

            if m_avail:
                m_dat = loc_o.get("marine_telemetry", {})
                m_wave = m_dat.get("wave_height", "N/A")
                m_swell = m_dat.get("swell_height", "N/A")
                m_curr = m_dat.get("ocean_current_velocity", "N/A")
                lines.append(f"- **Sea State (LIVE):** Significant Wave Height: {m_wave} m | Swell: {m_swell} m | Surface Current: {m_curr} km/h")
            else:
                lines.append(f"- **Sea State:** `[UNAVAILABLE]` Live marine telemetry unavailable for {loc}.")

            oc_dat = loc_o.get("ocean_analytics", {})
            if oc_dat:
                sst = oc_dat.get("sst_celsius", "N/A")
                chloro = oc_dat.get("chlorophyll_mg_m3", "N/A")
                upwell = oc_dat.get("upwelling_index", "N/A")
                lines.append(f"- **Oceanography (SAMPLE):** SST: {sst}°C | Chlorophyll-a: {chloro} mg/m³ | {upwell}")

            loc_pfz = pfz_by_loc.get(loc, {})
            if loc_pfz:
                p_score = loc_pfz.get("composite_score", "N/A")
                p_cat = loc_pfz.get("suitability_category", "N/A")
                lines.append(f"- **Fishing Zone Suitability (DEMO):** Index {p_score}/100 ({p_cat})")

        if failed_locs:
            lines.extend([
                "",
                f"> **[PARTIAL COMPARISON NOTICE]**: Live marine telemetry could not be retrieved for **{', '.join(failed_locs)}** (feed status: UNAVAILABLE). The comparative analysis is partial and restricted to available data ({', '.join(successful_locs)}). Data from one location was strictly not copied or imputed for another.",
            ])
    else:
        if weather_inner or marine_inner:
            w_temp = weather_inner.get("temperature", "N/A")
            w_spd = weather_inner.get("wind_speed", "N/A")
            w_gst = weather_inner.get("wind_gusts", "N/A")
            w_cond = weather_inner.get("weather_condition", "N/A")
            m_wave = marine_inner.get("wave_height", "N/A")
            m_swell = marine_inner.get("swell_height", "N/A")
            m_curr = marine_inner.get("ocean_current_velocity", "N/A")

            lines.extend([
                f"- **Wind & Atmosphere (LIVE):** {w_spd} km/h (Gusts: {w_gst} km/h) | Temp: {w_temp}°C | Condition: {w_cond}",
                f"- **Sea State (LIVE):** Significant Wave Height: {m_wave} m | Swell: {m_swell} m | Surface Current: {m_curr} km/h",
            ])

        if ocean_inner:
            sst = ocean_inner.get("sst_celsius", "N/A")
            chloro = ocean_inner.get("chlorophyll_mg_m3", "N/A")
            upwell = ocean_inner.get("upwelling_index", "N/A")
            lines.append(f"- **Oceanography (SAMPLE):** SST: {sst}°C | Chlorophyll-a: {chloro} mg/m³ | {upwell}")

        if pfz_inner:
            pfz_score = pfz_inner.get("composite_score", "N/A")
            pfz_cat = pfz_inner.get("suitability_category", "N/A")
            lines.append(f"- **Fishing Zone Suitability (DEMO):** Index {pfz_score}/100 ({pfz_cat})")

    # Geospatial restrictions
    if geo_payload.get("contexts"):
        for loc, ctx in geo_payload.get("contexts", {}).items():
            zones = ctx.get("inside_restricted_zones", [])
            if zones:
                z_names = [z.get("name") for z in zones]
                lines.append(f"- **Geospatial Zones for {loc}:** Inside restricted corridor: {', '.join(z_names)}")
            else:
                lines.append(f"- **Geospatial Zones for {loc}:** Clear of sample exclusion zones.")

    # Comparison summary if present
    if geo_payload.get("comparison"):
        comp = geo_payload["comparison"]
        dist = comp.get("geodesic_distance_km", "N/A")
        lines.append(f"- **Spatial Comparison (HISTORICAL):** Geodesic distance: {dist} km | Climatology profiles loaded.")

    # Route Reasoning (if route_planning)
    route_payload = state.get("route_data") or {}
    if route_payload:
        origin = route_payload.get("origin")
        dest = route_payload.get("destination")
        rec_r = route_payload.get("recommended_route") or {}
        r_dist = rec_r.get("total_distance_km", route_payload.get("total_distance_km", "N/A"))
        r_score = rec_r.get("route_score", "N/A")
        cands = route_payload.get("candidate_routes", [])

        lines.extend([
            "",
            "#### 3. ORCA Informational Route Analysis",
            f"> *Disclaimer: {route_payload.get('route_disclaimer', 'ORCA Informational Route — Not Certified for Official Navigation.')}*",
            f"- **Passage:** `{origin}` ➔ `{dest}`",
            f"- **Recommended Corridor:** {rec_r.get('route_name', 'Safe Passage')} ({r_dist} km, Safety Score: {r_score})",
            f"- **Hazard Clearance:** {route_payload.get('hazard_clearance', 'Clear')}",
        ])
        if len(cands) > 1:
            lines.append("- **Candidate Routes Evaluated:**")
            for c in cands:
                intersections = f" | MPA cross: {', '.join(c.get('restricted_zone_intersections'))}" if c.get("restricted_zone_intersections") else ""
                lines.append(f"  - `{c.get('route_name')}`: {c.get('total_distance_km')} km | Score: {c.get('route_score')} ({c.get('risk_category')}){intersections}")

    # Active Marine Advisories
    advisories = state.get("marine_advisories") or []
    if advisories:
        lines.extend([
            "",
            "#### 4. Active Marine Weather Advisories & Warnings (SAMPLE Feed)",
        ])
        for adv in advisories:
            sev = adv.get("severity", "ADVISORY")
            reg = adv.get("affected_region", "Coastal Sector")
            hd = adv.get("headline", "Advisory")
            lines.append(f"- **[{sev}] {reg}:** {hd}")
            if adv.get("description"):
                lines.append(f"  *Detail:* {adv.get('description')[:180]}...")

    # Cross-Domain Evidence Correlation
    corr = state.get("evidence_correlation") or {}
    if corr.get("cross_domain_risk_factors"):
        lines.extend([
            "",
            "#### 5. Cross-Domain Evidence Correlation",
            f"- **Metocean Coherence:** `{corr.get('metocean_coherence', 'NORMAL')}`",
        ])
        for factor in corr.get("cross_domain_risk_factors", []):
            lines.append(f"- {factor}")

    # Section: What-If Simulation (if applicable)
    if state.get("is_what_if"):
        param = state.get("what_if_parameter", "variable")
        val = state.get("what_if_value", "simulated")
        risk_prelim = risk.get("preliminary_metrics", {})
        details = risk_prelim.get("what_if_details", {})
        impact = details.get("impact", "Simulated scenario evaluated against artisanal safety thresholds.")

        lines.extend([
            "",
            "#### 6. What-If Hypothetical Scenario Analysis",
            f"- **Simulated Parameter:** `{param}` = {val}",
            f"- **Scenario Evaluation:** {impact}",
        ])

    # Section: Dynamic Replanning Log (if any replans occurred)
    if state.get("replan_history"):
        lines.extend([
            "",
            "#### 7. Dynamic Replanning Audit",
        ])
        for r_event in state.get("replan_history", []):
            iter_no = r_event.get("replan_iteration")
            reason = r_event.get("reason")
            lines.append(f"- **Iteration {iter_no}:** Replan triggered due to: *{reason}*")

    # Section: Risk Assessment & Advisory Notice
    lines.extend([
        "",
        "#### Maritime Safety & Risk Assessment",
        f"- **Safety Status:** **{risk_level}**",
        f"- **Assessment Rationale:** {risk_reason}",
        "",
        "> **[SAFETY ADVISORY NOTICE]**: Because live satellite feeds, radar, and official government advisories (INCOIS / IMD) are not fully integrated, ORCA cannot certify navigational or fishing safety at this stage. Always consult official local maritime port authorities before venturing out to sea.",
    ])

    final_response = "\n".join(lines)

    trace_event = {
        "node": "response",
        "action": "response_synthesis",
        "status": "completed",
        "details": {
            "evidence_count": len(evidence_items),
            "live_sources_count": len(live_sources),
            "sample_sources_count": len(sample_sources),
            "risk_level": risk_level,
            "is_what_if": state.get("is_what_if", False),
            "replan_count": state.get("replan_count", 0),
            "output_length": len(final_response),
        },
    }

    conversation_entry = {"user": query, "assistant": final_response}

    return {
        "final_response": final_response,
        "conversation_history": [conversation_entry],
        "execution_trace": [trace_event],
    }
