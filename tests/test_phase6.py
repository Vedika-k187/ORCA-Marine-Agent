"""
Unit & Integration Tests for ORCA Phase 6
Covers:
1. Temporal parsing
2. Alert schema
3. Alert location matching
4. Alert time matching
5. Route generation
6. Restricted-zone route detection
7. Route distance calculation
8. Route hazard calculation
9. Evidence correlation
10. Multi-hazard risk rules
11. SQLite session persistence
12. Session recovery
13. Change detection
14. Missing advisory data
15. Missing ocean data
16. Route API/data failure
17. Graceful fallback
18. No fabricated alerts
19. No fabricated route conditions
"""

import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from agents.planner import PlannerAgent
from tools.advisory_tools import (
    fetch_marine_advisories,
    matches_location,
    matches_time_horizon,
    classify_advisory_severity,
)
from tools.geospatial_tools import (
    plan_candidate_marine_routes,
    evaluate_route_safety,
    haversine_distance,
)
from tools.ocean_tools import fetch_sst, fetch_chlorophyll, fetch_ocean_current
from agents.evidence_agent import evidence_agent
from agents.risk_agent import risk_agent, THRESHOLDS
from services.memory import (
    init_db,
    save_session,
    load_session,
    clear_session,
    append_message,
    get_session_context,
)
from services.monitor import detect_condition_change, generate_alert_event
from graph.workflow import run_workflow
from services.llm import Task


# ==============================================================================
# 1. Temporal Parsing Tests
# ==============================================================================

def test_temporal_parsing_scopes():
    planner = PlannerAgent()

    # Tomorrow morning
    p1 = planner.plan("What will conditions be tomorrow morning near Ratnagiri?")
    assert p1["temporal_scope"]["scope"] == "TOMORROW"
    assert p1["temporal_scope"]["sub_period"] == "morning"

    # Next 12 hours
    p2 = planner.plan("How will conditions change over the next 12 hours?")
    assert p2["temporal_scope"]["scope"] == "NEXT_N_HOURS"
    assert p2["temporal_scope"]["hours_ahead"] == 12

    # Historical
    p3 = planner.plan("Was the sea rough yesterday near Goa?")
    assert p3["temporal_scope"]["scope"] == "HISTORICAL"

    # Current / immediate
    p4 = planner.plan("What are the conditions right now off Mumbai?")
    assert p4["temporal_scope"]["scope"] == "CURRENT"

    # What-if
    p5 = planner.plan("What if wind speed increases to 30 km/h?")
    assert p5["temporal_scope"]["scope"] == "WHAT_IF"


# ==============================================================================
# 2. Alert Schema & Provenance
# ==============================================================================

def test_alert_schema_and_provenance():
    ev = fetch_marine_advisories(location="Ratnagiri")
    assert ev["source_type"] == "sample"
    assert ev["status"] == "available"
    data = ev["data"]
    assert "advisories" in data
    assert isinstance(data["advisories"], list)

    for adv in data["advisories"]:
        assert "advisory_id" in adv
        assert "source" in adv
        assert "source_type" in adv
        assert adv["source_type"] == "sample"
        assert "severity" in adv
        assert "headline" in adv
        assert "description" in adv
        assert "status" in adv
        assert adv["status"] in ["ACTIVE", "EXPIRED"]


# ==============================================================================
# 3. Alert Location Matching
# ==============================================================================

def test_alert_location_matching():
    adv_ratnagiri = {
        "affected_region": "Ratnagiri",
        "coastal_stretch": "South Maharashtra Coast",
        "headline": "Swell alert for Ratnagiri",
    }
    assert matches_location(adv_ratnagiri, "Ratnagiri")
    assert matches_location(adv_ratnagiri, "Maharashtra")

    adv_goa = {
        "affected_region": "Goa",
        "coastal_stretch": "Goa Coast",
        "headline": "Moderate sea advisory",
    }
    assert matches_location(adv_goa, "Goa")
    assert not matches_location(adv_goa, "Porbandar")


# ==============================================================================
# 4. Alert Time Matching
# ==============================================================================

def test_alert_time_matching():
    active_adv = {"status": "ACTIVE", "valid_until": "2026-10-03T18:00:00Z"}
    expired_adv = {"status": "EXPIRED", "valid_until": "2026-09-25T18:00:00Z"}

    # Normal horizon matches ACTIVE only
    assert matches_time_horizon(active_adv, "today")
    assert matches_time_horizon(active_adv, "tomorrow")
    assert not matches_time_horizon(expired_adv, "today")

    # Historical horizon matches EXPIRED
    assert matches_time_horizon(expired_adv, "historical")
    assert matches_time_horizon(expired_adv, "yesterday")


# ==============================================================================
# 5. Route Generation & Candidate Corridors
# ==============================================================================

def test_route_generation_candidates():
    res = plan_candidate_marine_routes("Ratnagiri", "Goa")
    assert "candidate_routes" in res
    candidates = res["candidate_routes"]
    assert len(candidates) >= 2

    # Check candidate names
    ids = [c["route_id"] for c in candidates]
    assert "direct_inshore" in ids
    assert "recommended_offshore" in ids

    # Check waypoints exist
    for c in candidates:
        assert len(c["waypoints"]) >= 3
        assert "lat" in c["waypoints"][0]
        assert "lon" in c["waypoints"][0]


# ==============================================================================
# 6. Restricted-Zone Route Detection
# ==============================================================================

def test_restricted_zone_route_detection():
    routes = plan_candidate_marine_routes("Ratnagiri", "Goa")
    eval_res = evaluate_route_safety(routes)
    candidates = eval_res["candidate_routes"]

    inshore = next(c for c in candidates if c["route_id"] == "direct_inshore")
    offshore = next(c for c in candidates if c["route_id"] == "recommended_offshore")

    # Direct inshore route intersects Malvan Marine Sanctuary (MPA)
    inshore_sanctuaries = [z for z in inshore["restricted_zone_intersections"] if "Sanctuary" in z or "Restricted" in z]
    assert len(inshore_sanctuaries) >= 1

    # Recommended offshore passage clears all restricted marine sanctuaries
    offshore_sanctuaries = [z for z in offshore["restricted_zone_intersections"] if "Sanctuary" in z or "Restricted" in z]
    assert len(offshore_sanctuaries) == 0


# ==============================================================================
# 7. Route Distance Calculation
# ==============================================================================

def test_route_distance_calculation():
    routes = plan_candidate_marine_routes("Ratnagiri", "Goa")
    gc_dist = routes["great_circle_distance_km"]
    assert 160.0 < gc_dist < 220.0

    inshore_dist = routes["candidate_routes"][0]["total_distance_km"]
    offshore_dist = routes["candidate_routes"][1]["total_distance_km"]
    assert inshore_dist > 150.0
    assert offshore_dist > inshore_dist  # Offshore stand-off adds slight distance


# ==============================================================================
# 8. Route Hazard & Safety Scoring Formula
# ==============================================================================

def test_route_hazard_scoring_formula():
    routes = plan_candidate_marine_routes("Ratnagiri", "Goa")
    eval_res = evaluate_route_safety(
        routes,
        weather_data={"wind_speed": 18.0},
        marine_data={"wave_height": 1.2},
    )

    inshore = next(c for c in eval_res["candidate_routes"] if c["route_id"] == "direct_inshore")
    offshore = next(c for c in eval_res["candidate_routes"] if c["route_id"] == "recommended_offshore")

    # Recommended offshore route should have lower (better) score because it avoids MPA penalties
    assert offshore["route_score"] < inshore["route_score"]
    assert offshore["recommendation"] == "RECOMMENDED"
    assert "ORCA Informational Route" in eval_res["route_disclaimer"]


# ==============================================================================
# 9. Multi-Source Evidence Correlation
# ==============================================================================

def test_multi_source_evidence_correlation():
    state = {
        "weather_data": {"weather_data": {"wind_speed": 40.0, "wind_gusts": 50.0}},
        "ocean_data": {"marine_telemetry": {"wave_height": 2.6}},
        "marine_advisories": [{"severity": "WARNING", "headline": "High Swell Alert"}],
        "target_locations": [{"name": "Ratnagiri"}],
        "evidence_items": [
            {"source": "Open-Meteo", "source_type": "live", "status": "available"},
            {"source": "INCOIS Bulletin", "source_type": "sample", "status": "available"},
        ],
    }
    task = Task(task="correlate_evidence", capability="evidence")
    res = evidence_agent.run(task, state)

    corr = res["observations"]["evidence_correlation"]
    assert corr["metocean_coherence"] == "COHERENT_ELEVATED_STORM_STATE"
    assert len(corr["cross_domain_risk_factors"]) >= 2
    assert "Ratnagiri" in corr["correlation_summary"]


# ==============================================================================
# 10. Multi-Hazard Deterministic Risk Rules
# ==============================================================================

def test_risk_rules_severe_advisory():
    state = {
        "weather_data": {"weather_data": {"wind_speed": 20.0}},
        "ocean_data": {"marine_telemetry": {"wave_height": 1.5}},
        "marine_advisories": [
            {"severity": "CRITICAL", "headline": "Deep Depression Severe Cyclone Warning"}
        ],
    }
    task = Task(task="risk_evaluation", capability="risk", parameters={})
    res = risk_agent.run(task, state)
    risk = res["risk_assessment"]

    assert risk["risk_level"] == "HIGH_RISK"
    assert risk["status"] == "HIGH_RISK"
    assert "SEVERE_ADVISORY" == risk["deterministic_rule_fired"]


def test_risk_rules_extreme_metocean():
    state = {
        "weather_data": {"weather_data": {"wind_speed": 50.0}},
        "ocean_data": {"marine_telemetry": {"wave_height": 3.0}},
        "marine_advisories": [],
    }
    task = Task(task="risk_evaluation", capability="risk", parameters={})
    res = risk_agent.run(task, state)
    risk = res["risk_assessment"]

    assert risk["risk_level"] == "HIGH_RISK"
    assert risk["status"] == "HIGH_RISK"


def test_risk_rules_insufficient_evidence():
    state = {
        "weather_data": {},
        "ocean_data": {},
        "marine_advisories": [],
    }
    task = Task(task="risk_evaluation", capability="risk", parameters={})
    res = risk_agent.run(task, state)
    risk = res["risk_assessment"]

    assert risk["risk_level"] == "UNKNOWN"
    assert "not connected yet" in risk["reason"].lower() or "unavailable" in risk["reason"].lower()


# ==============================================================================
# 11 & 12. SQLite Session Persistence & Recovery
# ==============================================================================

def test_sqlite_session_persistence_and_recovery(tmp_path):
    db_file = tmp_path / "test_sessions.db"

    # Save session
    session_id = "test_sess_001"
    state_to_save = {
        "target_locations": [{"name": "Ratnagiri"}, {"name": "Goa"}],
        "intent": "location_comparison",
        "time_horizon": "tomorrow",
        "query": "Compare Ratnagiri and Goa.",
        "final_response": "Comparative report generated.",
    }
    assert save_session(session_id, state_to_save, db_path=db_file)

    # Recover session
    loaded = load_session(session_id, db_path=db_file)
    assert loaded is not None
    assert loaded["session_id"] == session_id
    assert loaded["context_locations"] == ["Ratnagiri", "Goa"]
    assert loaded["context_intent"] == "location_comparison"

    # Append turn
    assert append_message(session_id, "user", "Which has lower waves?", intent="location_comparison", db_path=db_file)

    # Clear session
    assert clear_session(session_id, db_path=db_file)
    assert load_session(session_id, db_path=db_file) is None


# ==============================================================================
# 13. Deterministic Change Detection
# ==============================================================================

def test_change_detection():
    prev_obs = {
        "location": "Ratnagiri",
        "weather": {"wind_speed": 15.0, "weather_condition": "Clear sky"},
        "marine": {"wave_height": 1.1},
        "advisories": {"advisory_count": 0, "max_severity": "NONE"},
    }
    curr_obs = {
        "location": "Ratnagiri",
        "weather": {"wind_speed": 26.0, "weather_condition": "Moderate rain"},
        "marine": {"wave_height": 1.9},
        "advisories": {"advisory_count": 1, "max_severity": "WARNING"},
    }

    result = detect_condition_change(prev_obs, curr_obs)
    assert result["changed"] is True
    assert result["change_count"] >= 3

    variables = [c["variable"] for c in result["changes"]]
    assert "wind_speed" in variables
    assert "wave_height" in variables
    assert "marine_advisories" in variables

    event = generate_alert_event("Ratnagiri", result["changes"])
    assert event["event_type"] == "URGENT_CHANGE_ALERT"


# ==============================================================================
# 14. Missing Advisory Data Handling
# ==============================================================================

def test_missing_advisory_data_graceful():
    # Query for a location with zero sample advisories
    ev = fetch_marine_advisories(location="NonExistentPortXYZ")
    assert ev["status"] == "available"
    assert ev["data"]["advisory_count"] == 0
    assert ev["data"]["max_severity"] == "NONE"


# ==============================================================================
# 15. Clean Ocean Data Adapters
# ==============================================================================

def test_clean_ocean_adapters():
    sst_ev = fetch_sst("Ratnagiri")
    assert sst_ev["source_type"] == "sample"
    assert "sst_celsius" in sst_ev["data"]

    chlo_ev = fetch_chlorophyll("Ratnagiri")
    assert chlo_ev["source_type"] == "sample"
    assert "chlorophyll_mg_m3" in chlo_ev["data"]

    curr_ev = fetch_ocean_current("Ratnagiri")
    assert curr_ev["source_type"] == "sample"
    assert "current_velocity_kmh" in curr_ev["data"]


# ==============================================================================
# 16. Route Data Failure Handling
# ==============================================================================

def test_route_failure_unknown_ports():
    routes = plan_candidate_marine_routes("UnknownPortA", "UnknownPortB")
    assert "error" in routes
    assert routes["status"] == "unavailable"
    assert routes["candidate_routes"] == []


# ==============================================================================
# 17. Graceful SQLite Fallback
# ==============================================================================

def test_sqlite_graceful_fallback(monkeypatch):
    # Simulate SQLite crash
    def broken_connect(*args, **kwargs):
        raise RuntimeError("Disk I/O error simulated")

    monkeypatch.setattr("sqlite3.connect", broken_connect)

    sess_id = "mem_fallback_001"
    # Should not crash; gracefully saves to in-memory fallback
    assert save_session(sess_id, {"target_locations": [{"name": "Ratnagiri"}]})
    loaded = load_session(sess_id)
    assert loaded is not None
    assert loaded["context_locations"] == ["Ratnagiri"]


# ==============================================================================
# 18. No Fabricated Alerts
# ==============================================================================

def test_no_fabricated_alerts():
    ev = fetch_marine_advisories(location="Ratnagiri")
    assert ev["source_type"] == "sample"
    # Ensure notice explicitly clarifies it is a sample fixture
    assert "sample" in ev["data"]["notice"].lower()


# ==============================================================================
# 19. No Fabricated Route Conditions
# ==============================================================================

def test_no_fabricated_route_conditions():
    res = plan_candidate_marine_routes("Ratnagiri", "Goa")
    assert "ORCA Informational Route" in res["route_disclaimer"]
    assert "Not Certified for Official Navigation" in res["route_disclaimer"]
