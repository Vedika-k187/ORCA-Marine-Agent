"""
LangGraph Workflow Orchestrator for ORCA
Phase 6: Integrates specialized marine agents (Weather, Ocean, Geospatial, Risk, Alert, Route),
multi-source evidence correlation, dynamic replanning, and persistent SQLite session memory.
"""

from typing import Any, Dict, List, Optional
from langgraph.graph import StateGraph, START, END

from graph.state import ORCAState
from graph.nodes import (
    planner_node,
    weather_node,
    ocean_node,
    geospatial_node,
    risk_node,
    alert_node,
    route_node,
    evaluator_node,
    replan_node,
    response_node,
)
from services.memory import save_session, get_session_context
from services.config import settings

MAX_REPLANS = settings.max_replans


def _get_required_capabilities(state: ORCAState) -> List[str]:
    """Helper to extract required capabilities from planner observation."""
    planner_res = state.get("agent_results", {}).get("planner") or {}
    return planner_res.get("required_capabilities", [])


def route_after_planner(state: ORCAState) -> str:
    """
    Conditional router after task decomposition by planner.
    Directs workflow to the appropriate first specialist node.
    """
    intent = state.get("intent", "general_marine_query")
    capabilities = _get_required_capabilities(state)

    if intent == "general_marine_query" or not capabilities:
        return "response"

    if intent == "advisory_check" or (capabilities and capabilities[0] == "alert"):
        return "alert"
    elif intent in ["location_comparison", "route_planning"] or "geospatial" in capabilities:
        return "geospatial"
    elif intent in ["environmental_analysis", "fishing_zone"]:
        return "ocean"
    elif "weather" in capabilities:
        return "weather"
    elif "ocean" in capabilities:
        return "ocean"
    elif "alert" in capabilities:
        return "alert"

    return "evaluator"


def route_after_alert(state: ORCAState) -> str:
    """Conditional router after alert ingestion."""
    capabilities = _get_required_capabilities(state)
    agent_results = state.get("agent_results", {})

    if "weather" in capabilities and "weather" not in agent_results:
        return "weather"
    elif "ocean" in capabilities and "ocean" not in agent_results:
        return "ocean"
    elif "geospatial" in capabilities and "geospatial" not in agent_results:
        return "geospatial"
    elif "risk" in capabilities and "risk" not in agent_results:
        return "risk"

    return "evaluator"


def route_after_geospatial(state: ORCAState) -> str:
    """Conditional router after geospatial reasoning."""
    capabilities = _get_required_capabilities(state)
    agent_results = state.get("agent_results", {})

    if "route" in capabilities and "route" not in agent_results:
        return "route"
    elif "weather" in capabilities and "weather" not in agent_results:
        return "weather"
    elif "ocean" in capabilities and "ocean" not in agent_results:
        return "ocean"
    elif "alert" in capabilities and "alert" not in agent_results:
        return "alert"
    elif "risk" in capabilities and "risk" not in agent_results:
        return "risk"

    return "evaluator"


def route_after_route(state: ORCAState) -> str:
    """Conditional router after candidate route generation and scoring."""
    capabilities = _get_required_capabilities(state)
    agent_results = state.get("agent_results", {})

    if "weather" in capabilities and "weather" not in agent_results:
        return "weather"
    elif "ocean" in capabilities and "ocean" not in agent_results:
        return "ocean"
    elif "alert" in capabilities and "alert" not in agent_results:
        return "alert"
    elif "risk" in capabilities and "risk" not in agent_results:
        return "risk"

    return "evaluator"


def route_after_weather(state: ORCAState) -> str:
    """Conditional router after weather assessment."""
    capabilities = _get_required_capabilities(state)
    agent_results = state.get("agent_results", {})

    if "ocean" in capabilities and "ocean" not in agent_results:
        return "ocean"
    elif "geospatial" in capabilities and "geospatial" not in agent_results:
        return "geospatial"
    elif "alert" in capabilities and "alert" not in agent_results:
        return "alert"
    elif "risk" in capabilities and "risk" not in agent_results:
        return "risk"

    return "evaluator"


def route_after_ocean(state: ORCAState) -> str:
    """Conditional router after ocean analytics."""
    capabilities = _get_required_capabilities(state)
    agent_results = state.get("agent_results", {})

    if "geospatial" in capabilities and "geospatial" not in agent_results:
        return "geospatial"
    elif "weather" in capabilities and "weather" not in agent_results:
        return "weather"
    elif "alert" in capabilities and "alert" not in agent_results:
        return "alert"
    elif "risk" in capabilities and "risk" not in agent_results:
        return "risk"

    return "evaluator"


def route_after_risk(state: ORCAState) -> str:
    """Routes to observation evaluation after risk evaluation."""
    return "evaluator"


def route_after_evaluator(state: ORCAState) -> str:
    """
    Evaluator conditional edge: loops to replan if critical data is missing
    and replan limit has not been reached; otherwise routes to response.
    """
    eval_summary = state.get("evaluation_summary") or {}
    decision = eval_summary.get("decision") or {}
    replan_count = state.get("replan_count", 0)

    if decision.get("should_replan") and replan_count < MAX_REPLANS:
        return "replan"

    return "response"


def route_after_replan(state: ORCAState) -> str:
    """Routes to the next injected task capability after replan."""
    agent_results = state.get("agent_results", {})
    if "geospatial" not in agent_results:
        return "geospatial"
    elif "weather" not in agent_results:
        return "weather"
    return "response"


def create_orca_workflow():
    """
    Constructs and compiles the dynamic LangGraph StateGraph for ORCA.
    """
    workflow = StateGraph(ORCAState)

    # Register nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("alert", alert_node)
    workflow.add_node("geospatial", geospatial_node)
    workflow.add_node("route", route_node)
    workflow.add_node("weather", weather_node)
    workflow.add_node("ocean", ocean_node)
    workflow.add_node("risk", risk_node)
    workflow.add_node("evaluator", evaluator_node)
    workflow.add_node("replan", replan_node)
    workflow.add_node("response", response_node)

    # Entry point
    workflow.add_edge(START, "planner")

    # Conditional branching edges
    workflow.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "alert": "alert",
            "geospatial": "geospatial",
            "weather": "weather",
            "ocean": "ocean",
            "evaluator": "evaluator",
            "response": "response",
        },
    )

    workflow.add_conditional_edges(
        "alert",
        route_after_alert,
        {
            "weather": "weather",
            "ocean": "ocean",
            "geospatial": "geospatial",
            "risk": "risk",
            "evaluator": "evaluator",
        },
    )

    workflow.add_conditional_edges(
        "geospatial",
        route_after_geospatial,
        {
            "route": "route",
            "weather": "weather",
            "ocean": "ocean",
            "alert": "alert",
            "risk": "risk",
            "evaluator": "evaluator",
            "response": "response",
        },
    )

    workflow.add_conditional_edges(
        "route",
        route_after_route,
        {
            "weather": "weather",
            "ocean": "ocean",
            "alert": "alert",
            "risk": "risk",
            "evaluator": "evaluator",
        },
    )

    workflow.add_conditional_edges(
        "weather",
        route_after_weather,
        {
            "ocean": "ocean",
            "geospatial": "geospatial",
            "alert": "alert",
            "risk": "risk",
            "evaluator": "evaluator",
            "response": "response",
        },
    )

    workflow.add_conditional_edges(
        "ocean",
        route_after_ocean,
        {
            "geospatial": "geospatial",
            "weather": "weather",
            "alert": "alert",
            "risk": "risk",
            "evaluator": "evaluator",
            "response": "response",
        },
    )

    workflow.add_edge("risk", "evaluator")

    workflow.add_conditional_edges(
        "evaluator",
        route_after_evaluator,
        {
            "replan": "replan",
            "response": "response",
        },
    )

    workflow.add_conditional_edges(
        "replan",
        route_after_replan,
        {
            "geospatial": "geospatial",
            "weather": "weather",
            "response": "response",
        },
    )

    # Terminal edge
    workflow.add_edge("response", END)

    return workflow.compile()


def run_workflow(
    query: str,
    language: str = "en",
    session_id: str = "default_session",
    session_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes the full ORCA LangGraph orchestration on a user query.
    Preserves session state across multiple turns using SQLite persistent memory.
    """
    app = create_orca_workflow()

    initial_state: ORCAState = {
        "query": query,
        "language": language,
        "session_id": session_id,
        "observations": {},
        "agent_results": {},
        "evidence_items": [],
        "errors": [],
        "execution_trace": [],
        "conversation_history": [],
        "replan_history": [],
        "replan_count": 0,
        "max_replans": MAX_REPLANS,
    }

    # Recover stored SQLite session context if not explicitly provided
    if session_state is None and session_id:
        session_state = get_session_context(session_id)

    # Pass in previous session context if present
    if session_state:
        if session_state.get("context_locations"):
            initial_state["context_locations"] = session_state["context_locations"]
        if session_state.get("context_time_horizon"):
            initial_state["context_time_horizon"] = session_state["context_time_horizon"]
        if session_state.get("conversation_history"):
            initial_state["conversation_history"] = session_state["conversation_history"]

    result_state = app.invoke(initial_state)

    # Persist session update to SQLite
    try:
        save_session(session_id, result_state)
    except Exception:
        pass

    return result_state


def run_workflow_dry(query: str, language: str = "en") -> Dict[str, Any]:
    """Dry-run helper for backward compatibility with initial tests."""
    return {
        "query": query,
        "language": language,
        "status": "ready",
    }
