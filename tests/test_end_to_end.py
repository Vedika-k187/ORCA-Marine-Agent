"""
ORCA End-to-End Integration Tests
Validates the complete LangGraph agentic loop across all primary marine user workflows:
1. Safety query ("Is it safe to fish tomorrow near Ratnagiri?")
2. Location comparison ("Compare Ratnagiri and Goa.")
3. Fishing zone ("Find nearby favourable fishing zones.")
4. Restricted zone ("Are there restricted zones near Ratnagiri?")
5. What-if scenario ("What if wind speed increases to 30 km/h near Ratnagiri?")
6. Route planning ("Find an informational route from Ratnagiri to Goa.")
7. Marine advisory check ("Are there marine warnings near Ratnagiri tomorrow?")
8. Multi-turn session continuity ("Compare Ratnagiri and Goa." -> "Which has lower waves?")
9. API failure & dynamic replanning (Simulated 503 outage triggering replanner)
10. Missing LLM key (Verifies full deterministic fallback execution)
"""

from unittest.mock import patch
import pytest

from graph.workflow import run_workflow
from services.memory import clear_session
from services.llm import llm_service


# 1. End-to-End Safety Query
def test_e2e_safety_query():
    res = run_workflow("Is it safe to fish tomorrow near Ratnagiri?")
    assert res is not None
    assert res["intent"] == "safety_check"
    assert res["weather_data"] is not None
    assert res["ocean_data"] is not None
    assert res["risk_assessment"] is not None
    assert len(res["evidence_items"]) > 0
    assert "ORCA Marine Intelligence Report" in res["final_response"]
    nodes = [e["node"] for e in res["execution_trace"]]
    assert "planner" in nodes and "weather" in nodes and "response" in nodes


# 2. End-to-End Location Comparison
def test_e2e_location_comparison():
    res = run_workflow("Compare fishing conditions between Ratnagiri and Goa")
    assert res["intent"] == "location_comparison"
    locs = [l.get("name") for l in res["target_locations"]]
    assert "Ratnagiri" in locs and "Goa" in locs
    assert res.get("geospatial_data") is not None
    assert "geospatial" in res["agent_results"]
    assert "weather" in res["agent_results"]
    assert "distance" in res["final_response"].lower() or "climatology" in res["final_response"].lower()


# 3. End-to-End Fishing Zone Inquiry
def test_e2e_fishing_zone_inquiry():
    res = run_workflow("Find nearby favourable fishing zones near Ratnagiri")
    assert res["intent"] == "fishing_zone"
    assert res["pfz_data"] is not None
    assert "composite_score" in res["pfz_data"]
    assert "Fishing Zone Suitability" in res["final_response"]


# 4. End-to-End Restricted Zone Inquiry
def test_e2e_restricted_zone_inquiry():
    res = run_workflow("Are there restricted zones near Ratnagiri?")
    assert res["intent"] == "safety_check"
    assert res["geospatial_data"] is not None
    geo_ctx = res["geospatial_data"].get("contexts", {}).get("Ratnagiri", {})
    assert "inside_restricted_zones" in geo_ctx
    assert "Geospatial Zones for Ratnagiri" in res["final_response"]


# 5. End-to-End What-If Simulation
def test_e2e_what_if_simulation():
    res = run_workflow("What if wind speed increases to 30 km/h near Ratnagiri?")
    assert res["is_what_if"] is True
    assert res["what_if_parameter"] == "wind_speed"
    assert res["what_if_value"] == 30.0
    assert "What-If" in res["final_response"]
    risk = res["risk_assessment"]
    assert risk["preliminary_metrics"]["what_if_active"] is True


# 6. End-to-End Route Planning
def test_e2e_route_planning():
    res = run_workflow("Find an informational route from Ratnagiri to Goa.")
    assert res["intent"] == "route_planning"
    route = res.get("route_data")
    assert route is not None
    assert route["origin"] == "Ratnagiri"
    assert route["destination"] == "Goa"
    assert len(route["candidate_routes"]) >= 2
    assert "ORCA Informational Route Analysis" in res["final_response"]
    assert "Not Certified for Official Navigation" in res["final_response"]


# 7. End-to-End Marine Advisory Check
def test_e2e_marine_advisory_check():
    res = run_workflow("Are there marine warnings near Ratnagiri tomorrow?")
    assert res["intent"] == "advisory_check"
    advisories = res.get("marine_advisories")
    assert advisories is not None
    assert len(advisories) >= 1
    assert "Active Marine Weather Advisories" in res["final_response"]
    nodes = [e["node"] for e in res["execution_trace"]]
    assert "alert" in nodes


# 8. End-to-End Multi-Turn Session Continuity
def test_e2e_multi_turn_continuity():
    sess_id = "e2e_test_session"
    clear_session(sess_id)

    # Turn 1: Establish locations
    t1 = run_workflow("Compare Ratnagiri and Goa.", session_id=sess_id)
    assert t1["context_locations"] == ["Ratnagiri", "Goa"]

    # Turn 2: Follow-up query without explicit location names
    t2 = run_workflow("Which has lower waves?", session_id=sess_id)
    assert any(l.get("name") == "Ratnagiri" for l in t2["target_locations"])
    assert any(l.get("name") == "Goa" for l in t2["target_locations"])
    assert t2["intent"] == "location_comparison"

    clear_session(sess_id)


# 9. End-to-End API Failure & Dynamic Replanning
def test_e2e_api_failure_and_replanning():
    class Mock503:
        status_code = 503
        text = "Buoy Gateway Unavailable"
        def json(self): return {}

    real_requests_get = getattr(__import__("requests"), "get")
    def mock_marine_failure(url, *args, **kwargs):
        if "marine" in url:
            return Mock503()
        return real_requests_get(url, *args, **kwargs)

    with patch("requests.get", side_effect=mock_marine_failure):
        res = run_workflow("Is it safe to fish tomorrow near Ratnagiri?")
        # Workflow must not crash
        assert res is not None
        assert res["final_response"] != ""
        # Risk assessment must refuse to declare safe
        risk = res.get("risk_assessment", {})
        assert risk.get("risk_level") == "UNKNOWN"


# 10. End-to-End Missing LLM Key (Deterministic Fallback)
def test_e2e_missing_llm_key_deterministic_fallback():
    with patch.object(llm_service, "is_enabled", return_value=False):
        res = run_workflow("Is it safe to fish tomorrow near Ratnagiri?")
        assert res is not None
        assert res["intent"] == "safety_check"
        assert res["final_response"] != ""
        assert "ORCA Marine Intelligence Report" in res["final_response"]
