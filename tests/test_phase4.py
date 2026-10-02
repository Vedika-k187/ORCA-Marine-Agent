"""
Unit and integration tests for Phase 4:
LLM abstraction, dynamic capability/tool registries, replanning,
session memory, what-if reasoning, error resilience, and evidence synthesis.
"""

from unittest.mock import patch
import pytest

from services.llm import (
    llm_service,
    PlannerDecision,
    Task,
    AgentRequest,
    AgentObservation,
    ReplanDecision,
)
from agents.registry import capability_registry
from tools.registry import tool_registry
from services.evaluator import evaluate_observations, generate_replan_decision
from agents.planner import PlannerAgent
from graph.workflow import run_workflow


# ==============================================================================
# 1. LLM Abstraction & Provider Tests
# ==============================================================================

def test_llm_service_offline_fallback():
    status = llm_service.get_status_info()
    assert "provider" in status
    assert "message" in status
    assert not llm_service.is_enabled() or status["provider"] == "offline_deterministic_fallback"


def test_pydantic_structured_schemas():
    task = Task(
        task="fetch_forecast",
        capability="weather",
        location="Ratnagiri",
        time_horizon="tomorrow",
        description="Fetch forecast",
    )
    assert task.capability == "weather"
    assert task.location == "Ratnagiri"

    decision = PlannerDecision(
        intent="safety_check",
        locations=["Ratnagiri"],
        time_horizon="tomorrow",
        required_capabilities=["weather", "ocean", "risk"],
        tasks=[task],
        reasoning_summary="Standard safety decomposition",
        is_what_if=False,
    )
    assert decision.intent == "safety_check"
    assert len(decision.tasks) == 1

    replan = ReplanDecision(
        should_replan=True,
        reason="Missing marine telemetry",
        new_tasks=[task],
        explanation="Fallback to sanctuary audit",
    )
    assert replan.should_replan is True
    assert replan.reason == "Missing marine telemetry"


# ==============================================================================
# 2. Capability & Tool Registries
# ==============================================================================

def test_capability_registry():
    caps = capability_registry.get_supported_capabilities()
    assert "weather" in caps
    assert "ocean" in caps
    assert "geospatial" in caps
    assert "fishing_zone" in caps
    assert "risk" in caps
    assert "comparison" in caps

    w_def = capability_registry.get("weather")
    assert "fetch_marine_weather" in w_def.available_tools


def test_tool_registry_execution():
    # Valid tool execution
    coords = tool_registry.execute("lookup_coordinates", location_name="Ratnagiri")
    assert coords == (16.9902, 73.3000)

    # Unregistered tool returns error evidence without throwing
    res = tool_registry.execute("arbitrary_malicious_eval_script", command="rm -rf /")
    assert res["status"] == "error"
    assert "not registered" in res["data"]["error"]


# ==============================================================================
# 3. Observation Evaluator & Replanning Logic
# ==============================================================================

def test_observation_evaluator_sufficient():
    mock_evidence = [
        {
            "source": "Open-Meteo Weather API",
            "source_type": "live",
            "status": "available",
            "variables": ["wind_speed_10m", "wind_gusts_10m"],
            "data": {},
        },
        {
            "source": "Open-Meteo Marine API",
            "source_type": "live",
            "status": "available",
            "variables": ["wave_height"],
            "data": {},
        },
    ]
    eval_res = evaluate_observations(mock_evidence, requested_capabilities=["weather"])
    assert eval_res["status"] == "sufficient"
    assert eval_res["confidence"] > 0.0
    assert eval_res["can_replan"] is False


def test_observation_evaluator_missing_and_replan():
    mock_evidence = [
        {
            "source": "Open-Meteo Marine API",
            "source_type": "live",
            "status": "unavailable",
            "variables": ["wave_height"],
            "data": {"error": "Connection timed out"},
        }
    ]
    eval_res = evaluate_observations(mock_evidence, requested_capabilities=["ocean"], replan_count=0)
    assert eval_res["status"] == "insufficient"
    assert eval_res["can_replan"] is True
    assert len(eval_res["recommended_next_tasks"]) >= 1

    decision = generate_replan_decision(eval_res, state={}, replan_count=0, max_replans=3)
    assert decision.should_replan is True
    assert "Missing vital telemetry" in decision.reason


def test_max_replanning_limit():
    eval_res = {
        "status": "insufficient",
        "can_replan": True,
        "recommended_next_tasks": [Task(task="check_marine_zones", capability="geospatial")],
        "missing_information": ["Open-Meteo Marine API: Timed out"],
    }
    decision = generate_replan_decision(eval_res, state={}, replan_count=3, max_replans=3)
    assert decision.should_replan is False
    assert "maximum allowed replanning" in decision.reason


# ==============================================================================
# 4. Session Context & Multi-Turn Memory
# ==============================================================================

def test_session_context_anaphoric_resolution():
    planner = PlannerAgent()

    # Turn 1: Establish context
    plan1 = planner.plan("Compare Ratnagiri and Goa.")
    assert "Ratnagiri" in plan1["locations"]
    assert "Goa" in plan1["locations"]

    session_state = {
        "context_locations": plan1["locations"],
        "context_time_horizon": "today",
        "conversation_history": [{"user": "Compare Ratnagiri and Goa.", "assistant": "..."}],
    }

    # Turn 2: Anaphoric query referencing previous turn
    plan2 = planner.plan(
        "Which one has lower wave conditions?",
        session_context=session_state,
    )
    assert "Ratnagiri" in plan2["locations"]
    assert "Goa" in plan2["locations"]
    assert plan2["intent"] == "location_comparison"


# ==============================================================================
# 5. What-If Hypothetical Reasoning
# ==============================================================================

def test_what_if_reasoning_parsing():
    planner = PlannerAgent()
    plan = planner.plan("What if wind speed increases to 30 km/h near Ratnagiri?")
    assert plan["is_what_if"] is True
    assert plan["what_if_parameter"] == "wind_speed"
    assert plan["what_if_value"] == 30.0
    assert "Ratnagiri" in plan["locations"]


def test_what_if_workflow_execution():
    res = run_workflow("What if wind speed increases to 30 km/h near Ratnagiri?")
    assert res["is_what_if"] is True
    assert res["what_if_parameter"] == "wind_speed"
    assert res["what_if_value"] == 30.0
    assert "What-If Hypothetical Scenario Analysis" in res["final_response"]
    assert "30.0" in res["final_response"]


# ==============================================================================
# 6. Graceful Handling of API Failure During Workflow
# ==============================================================================

def test_marine_api_failure_handled_safely():
    # Simulate Open-Meteo Marine API failing with 503 Service Unavailable
    class Mock503:
        status_code = 503
        text = "Service Temporarily Unavailable"
        def json(self):
            return {}

    with patch("requests.get", return_value=Mock503()):
        res = run_workflow("Is it safe to fish tomorrow near Ratnagiri?")
        # Workflow must not crash
        assert res is not None
        assert res.get("final_response") != ""
        # Risk assessment must refuse to declare safe
        risk = res.get("risk_assessment", {})
        assert risk.get("risk_level") == "UNKNOWN"
        assert "not connected yet" in risk.get("reason", "").lower() or "telemetry" in risk.get("reason", "").lower()


# ==============================================================================
# 7. Evidence Integrity & Provenance
# ==============================================================================

def test_evidence_provenance_distinction():
    res = run_workflow("Compare Ratnagiri and Goa.")
    resp = res["final_response"]

    assert "LIVE Telemetry Sources" in resp
    assert "SAMPLE Data Sources" in resp
    assert "HISTORICAL Baselines" in resp
    assert "ORCA Historical Coastal Climatology Database" in resp
