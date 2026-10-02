"""
Test suite for ORCA LangGraph agentic core and workflow orchestration.
"""

import pytest
from graph.state import ORCAState
from agents.planner import PlannerAgent
from graph.workflow import run_workflow, run_workflow_dry, create_orca_workflow


# ==============================================================================
# Existing Baseline Sanity Tests (Preserved)
# ==============================================================================

def test_planner_initialization():
    planner = PlannerAgent()
    plan = planner.plan("Is it safe to fish tomorrow near Ratnagiri?")
    assert plan["intent"] == "safety_check"
    assert "Ratnagiri" in plan["locations"]
    assert len(plan["subtasks"]) >= 1


def test_orca_state_structure():
    state: ORCAState = {
        "query": "Test marine query",
        "language": "en",
        "intent": "safety_check",
    }
    assert state["query"] == "Test marine query"


def test_dry_workflow():
    result = run_workflow_dry("Test query")
    assert result["status"] == "ready"


# ==============================================================================
# Phase 2 Agentic Core & Routing Tests
# ==============================================================================

def test_workflow_compilation():
    """Verify that the StateGraph compiles cleanly into a runnable app."""
    app = create_orca_workflow()
    assert app is not None


def test_safety_query_routing():
    """
    Verify safety query conditionally routes through:
    planner -> weather -> ocean -> risk -> response
    """
    res = run_workflow("Is it safe to fish tomorrow near Ratnagiri?")
    executed_nodes = [e["node"] for e in res["execution_trace"]]

    assert executed_nodes == ["planner", "weather", "ocean", "risk", "response"]
    assert res["intent"] == "safety_check"
    assert any(loc.get("name") == "Ratnagiri" for loc in res["target_locations"])
    assert res["weather_data"] is not None
    assert res["ocean_data"] is not None
    assert res["risk_assessment"] is not None
    assert res["risk_assessment"]["risk_level"] == "UNKNOWN"


def test_location_comparison_routing():
    """
    Verify location comparison query routes through:
    planner -> geospatial -> weather -> ocean -> risk -> response
    """
    res = run_workflow("Compare fishing conditions between Goa and Karwar tomorrow")
    executed_nodes = [e["node"] for e in res["execution_trace"]]

    assert executed_nodes == ["planner", "geospatial", "weather", "ocean", "risk", "response"]
    assert res["intent"] == "location_comparison"
    loc_names = [loc["name"] for loc in res["target_locations"]]
    assert "Goa" in loc_names
    assert "Karwar" in loc_names
    assert res["geospatial_data"] is not None
    assert res["weather_data"] is not None
    assert res["ocean_data"] is not None


def test_route_planning_routing():
    """
    Verify route planning conditionally routes through:
    planner -> geospatial -> weather -> risk -> response (skipping ocean analytics)
    """
    res = run_workflow("Plan navigation route from Mumbai to Ratnagiri")
    executed_nodes = [e["node"] for e in res["execution_trace"]]

    assert executed_nodes == ["planner", "geospatial", "weather", "risk", "response"]
    assert res["intent"] == "route_planning"
    assert "geospatial" in res["agent_results"]
    assert "weather" in res["agent_results"]
    assert "ocean" not in res["agent_results"]


def test_general_query_bypasses_specialist_agents():
    """
    Verify general marine query routes directly:
    planner -> response
    Bypassing all specialist nodes.
    """
    res = run_workflow("What is the history of traditional dhows in the Indian Ocean?")
    executed_nodes = [e["node"] for e in res["execution_trace"]]

    assert executed_nodes == ["planner", "response"]
    assert res["intent"] == "general_marine_query"
    assert "weather_data" not in res or res["weather_data"] is None
    assert "ocean_data" not in res or res["ocean_data"] is None
    assert "geospatial_data" not in res or res["geospatial_data"] is None


def test_state_updates_and_agent_results():
    """
    Verify that each visited node updates both observations and agent_results.
    """
    res = run_workflow("Check wave heights and wind speed for Mumbai tomorrow")
    agent_results = res.get("agent_results", {})
    observations = res.get("observations", {})

    assert "planner" in agent_results
    assert "weather" in agent_results
    assert "planner" in observations
    assert "weather" in observations
    assert res.get("final_response") != ""


def test_execution_trace_structure():
    """
    Verify each trace event contains structured operational metadata without hidden thoughts.
    """
    res = run_workflow("Is it safe to fish tomorrow near Ratnagiri?")
    trace = res.get("execution_trace", [])
    assert len(trace) == 5

    for event in trace:
        assert "node" in event
        assert "action" in event
        assert "status" in event
        assert event["status"] == "completed"
        assert "details" in event


def test_risk_evaluation_does_not_claim_false_safety():
    """
    Verify risk assessment explicitly refuses to fabricate safety when real data is absent.
    """
    res = run_workflow("Is it safe to fish tomorrow near Ratnagiri?")
    risk = res.get("risk_assessment", {})

    assert risk["status"] == "pending_real_data"
    assert risk["risk_level"] == "UNKNOWN"
    assert "not connected yet" in risk["reason"]
    assert "UNKNOWN" in res["final_response"]
