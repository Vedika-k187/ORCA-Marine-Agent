"""
Deterministic test suite for ORCA tools, data layer, schemas, calculations, and error handling.
"""

from unittest.mock import patch
import pytest
import requests

from tools.base import build_evidence
from tools.geospatial_tools import (
    lookup_coordinates,
    haversine_distance,
    find_nearest_location,
    check_point_in_zones,
    find_nearby_marine_zones,
    evaluate_geospatial_context,
)
from tools.weather_tools import fetch_marine_weather, decode_wmo_code
from tools.marine_tools import fetch_marine_conditions
from tools.tide_tools import fetch_tide_data
from tools.ocean_tools import fetch_ocean_analytics
from tools.pfz_tools import compute_pfz_suitability
from tools.comparison_tools import compare_coastal_locations


# ==============================================================================
# 1. Evidence Model Schema Tests
# ==============================================================================

def test_evidence_structure():
    ev = build_evidence(
        source="Test Source",
        source_type="live",
        location="Ratnagiri",
        variables=["wind_speed", "wave_height"],
        status="available",
        data={"wind_speed": 14.5},
    )
    assert ev["source"] == "Test Source"
    assert ev["source_type"] == "live"
    assert "timestamp" in ev
    assert ev["location"] == "Ratnagiri"
    assert ev["variables"] == ["wind_speed", "wave_height"]
    assert ev["status"] == "available"
    assert ev["data"]["wind_speed"] == 14.5


# ==============================================================================
# 2. Deterministic Geospatial Calculations
# ==============================================================================

def test_haversine_distance():
    # Distance to same point must be 0.0
    p1 = (18.9220, 72.8347)
    assert haversine_distance(p1, p1) == 0.0

    # Distance between Mumbai and Goa is approx 390 - 410 km
    goa = (15.4909, 73.8278)
    dist = haversine_distance(p1, goa)
    assert 385.0 <= dist <= 415.0


def test_coastal_coordinates_lookup():
    assert lookup_coordinates("Ratnagiri") == (16.9902, 73.3000)
    assert lookup_coordinates("mumbai") == (18.9220, 72.8347)  # Case insensitive
    assert lookup_coordinates("NonExistentIslandXYZ") is None


def test_nearest_location():
    # Near Ratnagiri
    res = find_nearest_location(16.95, 73.32)
    assert res["nearest_location"] == "Ratnagiri"
    assert res["distance_km"] < 15.0


def test_point_in_polygon_geofencing():
    # Malvan Marine Sanctuary coordinates: ~16.06N, 73.47E
    inside = check_point_in_zones(16.050, 73.470)
    assert len(inside) >= 1
    assert any(z["zone_id"] == "MZ-IN-W01" for z in inside)
    assert any(z["restriction_level"] == "Restricted" for z in inside)

    # Far offshore point outside any restricted sanctuary
    outside = check_point_in_zones(14.000, 70.000)
    assert len(outside) == 0


def test_nearby_marine_zones():
    # Coordinates in Ratnagiri coastal waters
    nearby = find_nearby_marine_zones(16.99, 73.30, radius_km=50.0)
    assert len(nearby) >= 1
    zone_names = [z["name"] for z in nearby]
    assert any("Ratnagiri" in name for name in zone_names)


def test_evaluate_geospatial_context():
    known_ev = evaluate_geospatial_context("Ratnagiri")
    assert known_ev["status"] == "available"
    assert known_ev["source_type"] == "sample"
    assert "inside_restricted_zones" in known_ev["data"]

    unknown_ev = evaluate_geospatial_context("AtlantisPort")
    assert unknown_ev["status"] == "unavailable"


# ==============================================================================
# 3. Deterministic PFZ Suitability Calculations
# ==============================================================================

def test_pfz_suitability_optimal_conditions():
    ev = compute_pfz_suitability(
        location_name="Ratnagiri",
        sst_celsius=28.4,
        sst_gradient=0.08,
        chlorophyll_mg_m3=1.2,
        distance_km=20.0,
        wave_height_m=0.7,
        wind_speed_kmh=12.0,
    )
    assert ev["status"] == "available"
    data = ev["data"]
    assert data["composite_score"] >= 80.0
    assert data["suitability_category"] == "High Suitability"
    assert "factors_breakdown" in data
    assert data["factors_breakdown"]["sst"]["weight_pct"] == 30
    assert data["factors_breakdown"]["chlorophyll"]["weight_pct"] == 35


def test_pfz_suitability_hazardous_sea_state():
    ev = compute_pfz_suitability(
        location_name="Ratnagiri",
        sst_celsius=28.4,
        sst_gradient=0.01,
        chlorophyll_mg_m3=0.1,  # poor chlorophyll
        distance_km=70.0,        # too far
        wave_height_m=3.5,       # severe waves
        wind_speed_kmh=45.0,     # gale force
    )
    data = ev["data"]
    assert data["composite_score"] < 50.0
    assert "Unfavorable" in data["suitability_category"] or "Marginal" in data["suitability_category"]


# ==============================================================================
# 4. Deterministic Comparison Tool
# ==============================================================================

def test_historical_comparison_tool():
    ev = compare_coastal_locations("Ratnagiri", "Goa")
    assert ev["status"] == "available"
    assert ev["source_type"] == "historical"
    data = ev["data"]
    assert "location_a" in data
    assert "location_b" in data
    assert data["geodesic_distance_km"] > 0
    assert "annual_avg_sst_celsius" in data["location_a"]

    # Unknown location fails gracefully
    ev_unknown = compare_coastal_locations("Ratnagiri", "UnknownFictionalPort")
    assert ev_unknown["status"] == "unavailable"


# ==============================================================================
# 5. Tide and Ocean Analytics Tools
# ==============================================================================

def test_tide_data_tool():
    ev = fetch_tide_data("Ratnagiri")
    assert ev["status"] == "available"
    assert ev["source_type"] == "sample"
    data = ev["data"]
    assert "high_tides" in data
    assert "low_tides" in data
    assert data["tidal_range_m"] > 0
    assert "demonstration_sample_fixture" in data["data_classification"]

    ev_missing = fetch_tide_data("UnknownCove")
    assert ev_missing["status"] == "unavailable"


def test_ocean_analytics_tool():
    ev = fetch_ocean_analytics("Ratnagiri")
    assert ev["status"] == "available"
    assert ev["source_type"] == "sample"
    data = ev["data"]
    assert "sst_celsius" in data
    assert "chlorophyll_mg_m3" in data
    assert "upwelling_index" in data


# ==============================================================================
# 6. Error Handling & API Failure Resilience
# ==============================================================================

def test_weather_tool_timeout_handling():
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out")):
        ev = fetch_marine_weather("Ratnagiri")
        assert ev["status"] == "unavailable"
        assert ev["source_type"] == "live"
        assert "timed out" in ev["data"]["error"]


def test_weather_tool_http_error_handling():
    class MockResponse:
        status_code = 500
        text = "Internal Server Error"
        def json(self):
            return {}

    with patch("requests.get", return_value=MockResponse()):
        ev = fetch_marine_weather("Ratnagiri")
        assert ev["status"] == "error"
        assert "HTTP error 500" in ev["data"]["error"]


def test_weather_tool_unresolved_location():
    ev = fetch_marine_weather("UnregisteredLocationName999")
    assert ev["status"] == "unavailable"
    assert "could not be resolved" in ev["data"]["error"]


def test_marine_tool_http_error_handling():
    class MockResponse:
        status_code = 503
        text = "Service Unavailable"
        def json(self):
            return {}

    with patch("requests.get", return_value=MockResponse()):
        ev = fetch_marine_conditions("Ratnagiri")
        assert ev["status"] == "error"
        assert "HTTP error 503" in ev["data"]["error"]


def test_decode_wmo_code():
    assert decode_wmo_code(0) == "Clear sky"
    assert decode_wmo_code(95) == "Thunderstorm"
    assert decode_wmo_code(None) == "Unknown"
    assert "Weather code 999" in decode_wmo_code(999)
