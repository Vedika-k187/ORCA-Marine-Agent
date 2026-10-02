"""
Regression Tests for Multi-Location Comparison Queries in ORCA.
Verifies that multi-location comparison queries (e.g. Ratnagiri + Goa)
retrieve independent weather and ocean observations for each location,
preserve provenance, handle partial API failures without data duplication,
and prevent duplicate redundant calls.
"""

from unittest.mock import patch
from graph.workflow import run_workflow
from tools.base import build_evidence


# ==============================================================================
# A. Two-Location Comparison
# ==============================================================================

def test_two_location_comparison():
    """
    Verify two-location comparison query:
    - Planner extracts 2 locations (Ratnagiri and Goa)
    - Weather executes for both locations
    - Ocean executes for both locations
    - Observations contain both locations with location tags
    """
    res = run_workflow("Compare Ratnagiri and Goa for fishing conditions tomorrow.")

    assert res["intent"] == "location_comparison"
    loc_names = [l["name"] for l in res["target_locations"]]
    assert "Ratnagiri" in loc_names
    assert "Goa" in loc_names

    # Check weather execution trace for both locations
    w_traces = [e for e in res["execution_trace"] if e.get("node") == "weather"]
    w_locs = [e.get("details", {}).get("location") for e in w_traces]
    assert "Ratnagiri" in w_locs
    assert "Goa" in w_locs

    # Check ocean execution trace for both locations
    o_traces = [e for e in res["execution_trace"] if e.get("node") == "ocean"]
    o_locs = [e.get("details", {}).get("location") for e in o_traces]
    assert "Ratnagiri" in o_locs
    assert "Goa" in o_locs

    # Check observations contain both locations
    w_by_loc = res["weather_data"]["by_location"]
    assert "Ratnagiri" in w_by_loc
    assert "Goa" in w_by_loc
    assert w_by_loc["Ratnagiri"]["location"] == "Ratnagiri"
    assert w_by_loc["Goa"]["location"] == "Goa"

    o_by_loc = res["ocean_data"]["by_location"]
    assert "Ratnagiri" in o_by_loc
    assert "Goa" in o_by_loc
    assert o_by_loc["Ratnagiri"]["location"] == "Ratnagiri"
    assert o_by_loc["Goa"]["location"] == "Goa"

    # Verify both locations have distinct data in final response
    assert "Observations for Ratnagiri" in res["final_response"]
    assert "Observations for Goa" in res["final_response"]


# ==============================================================================
# B. Three-Location Comparison
# ==============================================================================

def test_three_location_comparison():
    """
    Verify three-location comparison query:
    All three locations receive required weather and ocean observations.
    """
    res = run_workflow("Compare Ratnagiri, Goa and Mumbai")

    assert res["intent"] == "location_comparison"
    loc_names = [l["name"] for l in res["target_locations"]]
    assert "Ratnagiri" in loc_names
    assert "Goa" in loc_names
    assert "Mumbai" in loc_names

    w_by_loc = res["weather_data"]["by_location"]
    for loc in ["Ratnagiri", "Goa", "Mumbai"]:
        assert loc in w_by_loc
        assert w_by_loc[loc]["location"] == loc

    o_by_loc = res["ocean_data"]["by_location"]
    for loc in ["Ratnagiri", "Goa", "Mumbai"]:
        assert loc in o_by_loc
        assert o_by_loc[loc]["location"] == loc

    # Check execution trace has all 3 locations
    w_locs = [e.get("details", {}).get("location") for e in res["execution_trace"] if e.get("node") == "weather"]
    assert set(w_locs) == {"Ratnagiri", "Goa", "Mumbai"}

    o_locs = [e.get("details", {}).get("location") for e in res["execution_trace"] if e.get("node") == "ocean"]
    assert set(o_locs) == {"Ratnagiri", "Goa", "Mumbai"}


# ==============================================================================
# C. Partial API Failure in Multi-Location Comparison
# ==============================================================================

def test_partial_api_failure_in_comparison():
    """
    Verify that when one location's API call fails:
    - One location fails while the other succeeds
    - Final response clearly indicates incomplete / partial evidence
    - No data from one location is copied to another
    """
    from tools.weather_tools import fetch_marine_weather

    real_fetch_weather = fetch_marine_weather

    def mock_weather_selective(location_name, **kwargs):
        if location_name == "Goa":
            return build_evidence(
                source="Open-Meteo Weather API",
                source_type="live",
                location=location_name,
                variables=["wind_speed_10m"],
                status="unavailable",
                data={"error": "Simulated station outage for Goa"},
            )
        return real_fetch_weather(location_name=location_name, **kwargs)

    with patch("tools.weather_tools.fetch_marine_weather", side_effect=mock_weather_selective):
        with patch.dict("tools.registry.tool_registry._tools"):
            # Update tool registry with mocked tool
            from tools.registry import tool_registry
            tool_registry._tools["fetch_marine_weather"].func = mock_weather_selective

            res = run_workflow("Compare Ratnagiri and Goa for fishing conditions tomorrow.")

            w_by_loc = res["weather_data"]["by_location"]

            # Ratnagiri succeeded
            assert w_by_loc["Ratnagiri"]["status"] == "available"
            # Goa failed
            assert w_by_loc["Goa"]["status"] == "unavailable"

            # Verify no data was copied from Ratnagiri to Goa
            ratnagiri_wind = w_by_loc["Ratnagiri"]["weather_data"].get("wind_speed")
            goa_wind = w_by_loc["Goa"]["weather_data"].get("wind_speed")
            assert goa_wind is None or goa_wind != ratnagiri_wind

            # Final response clearly indicates incomplete/partial evidence
            assert "PARTIAL COMPARISON NOTICE" in res["final_response"] or "UNAVAILABLE" in res["final_response"]
            assert "Goa" in res["final_response"]


# ==============================================================================
# D. No Duplicate Unnecessary Calls
# ==============================================================================

def test_no_duplicate_unnecessary_calls():
    """
    Verify that for a 2-location query:
    - Weather executes exactly once per location (no duplicate calls)
    - Ocean executes exactly once per location (no duplicate calls)
    """
    res = run_workflow("Compare Ratnagiri and Goa for fishing conditions tomorrow.")

    w_locs = [e.get("details", {}).get("location") for e in res["execution_trace"] if e.get("node") == "weather"]
    assert len(w_locs) == 2
    assert len(w_locs) == len(set(w_locs))  # No duplicates

    o_locs = [e.get("details", {}).get("location") for e in res["execution_trace"] if e.get("node") == "ocean"]
    assert len(o_locs) == 2
    assert len(o_locs) == len(set(o_locs))  # No duplicates
