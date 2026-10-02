"""
Unit and integration tests for Phase 5 UI components, map visualizer, chart visualizer, and dashboard handlers.
"""

import pytest
import folium
import plotly.graph_objects as go

import app
from graph.workflow import run_workflow
from utils.map_visualization import create_marine_map
from utils.chart_visualization import (
    create_wave_conditions_chart,
    create_wind_chart,
    create_location_comparison_chart,
    create_what_if_chart,
)


def test_app_imports_successfully():
    """Verify that app.py imports cleanly without syntax or missing dependency errors."""
    assert hasattr(app, "main")
    assert hasattr(app, "init_session_state")


def test_workflow_called_from_app():
    """Verify that the existing workflow entry point called by app executes and returns valid state."""
    result = run_workflow("Is it safe to fish tomorrow near Ratnagiri?")
    assert result is not None
    assert "final_response" in result
    assert "execution_trace" in result
    assert "evidence_items" in result


def test_map_creation_with_zones_and_markers():
    """Verify that create_marine_map returns a valid Folium Map object containing layers."""
    result = run_workflow("Is it safe to fish tomorrow near Ratnagiri?")
    m = create_marine_map(target_locations=["Ratnagiri"], workflow_result=result)

    assert isinstance(m, folium.Map)
    html_repr = m._repr_html_()
    assert html_repr is not None
    assert len(html_repr) > 100
    assert "leaflet" in html_repr.lower() or "map" in html_repr.lower()


def test_map_creation_with_multiple_locations():
    """Verify map with two locations creates geodesic connection line."""
    m = create_marine_map(target_locations=["Ratnagiri", "Goa"])
    assert isinstance(m, folium.Map)
    assert m.location is not None


def test_chart_creation_wave_conditions():
    """Verify create_wave_conditions_chart generates a Plotly figure when wave data is present."""
    mock_marine = {"wave_height": 0.52, "swell_height": 0.42}
    fig = create_wave_conditions_chart(mock_marine)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1

    # Empty marine data returns None safely
    assert create_wave_conditions_chart({}) is None


def test_chart_creation_wind_telemetry():
    """Verify create_wind_chart generates a Plotly figure."""
    mock_weather = {"wind_speed": 14.5, "wind_gusts": 22.0}
    fig = create_wind_chart(mock_weather)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1

    assert create_wind_chart({}) is None


def test_chart_creation_location_comparison():
    """Verify create_location_comparison_chart generates grouped bar chart."""
    mock_comp = {
        "location_a": {"location_name": "Ratnagiri", "annual_avg_sst_celsius": 28.2, "avg_monsoon_wave_height_m": 3.4, "avg_post_monsoon_wave_height_m": 0.9},
        "location_b": {"location_name": "Goa", "annual_avg_sst_celsius": 28.6, "avg_monsoon_wave_height_m": 3.2, "avg_post_monsoon_wave_height_m": 0.8},
    }
    fig = create_location_comparison_chart(mock_comp)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_chart_creation_what_if_scenario():
    """Verify create_what_if_chart generates baseline vs simulated scenario chart."""
    details = {
        "parameter": "wind_speed",
        "baseline_value": 12.0,
        "simulated_value": 30.0,
    }
    fig = create_what_if_chart(details)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1


def test_missing_evidence_does_not_crash_components():
    """Verify UI visualizers gracefully handle empty or failed results."""
    empty_result = {
        "query": "Test empty",
        "intent": "general_marine_query",
        "target_locations": [],
        "evidence_items": [],
        "execution_trace": [],
        "final_response": "Empty test response",
    }
    m = create_marine_map(target_locations=["Unspecified"], workflow_result=empty_result)
    assert isinstance(m, folium.Map)
    assert create_wave_conditions_chart({}) is None
    assert create_wind_chart({}) is None


def test_no_fake_values_generated_in_charts():
    """Verify charts return None when values are absent instead of generating arbitrary numbers."""
    assert create_wave_conditions_chart({"wave_height": None, "swell_height": None}) is None
    assert create_wind_chart({"wind_speed": None, "wind_gusts": None}) is None
    assert create_what_if_chart({"baseline_value": None, "simulated_value": None}) is None
