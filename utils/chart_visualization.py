"""
ORCA Interactive Marine Chart Visualizer
Builds Plotly charts for wave conditions, wind thresholds, location comparisons, and what-if simulations.
"""

from typing import Any, Dict, List, Optional
import plotly.graph_objects as go


def create_wave_conditions_chart(marine_data: Dict[str, Any]) -> Optional[go.Figure]:
    """Generates bar chart comparing significant wave height, swell, and sea state safety thresholds."""
    wave_h = marine_data.get("wave_height")
    swell_h = marine_data.get("swell_height")

    if wave_h is None and swell_h is None:
        return None

    categories = []
    values = []
    colors = []

    if wave_h is not None:
        categories.append("Significant Wave Height")
        values.append(float(wave_h))
        colors.append("#0288D1")

    if swell_h is not None:
        categories.append("Swell Wave Height")
        values.append(float(swell_h))
        colors.append("#26A69A")

    fig = go.Figure(
        data=[
            go.Bar(
                x=categories,
                y=values,
                marker=dict(color=colors),
                text=[f"{v:.2f} m" for v in values],
                textposition="auto",
                width=0.45,
            )
        ]
    )

    # Threshold horizontal line at 1.8m (moderate caution) and 2.5m (rough sea warning)
    fig.add_hline(y=1.8, line_dash="dot", line_color="#FB8C00", annotation_text="Caution (>1.8m)", annotation_position="top right")
    fig.add_hline(y=2.5, line_dash="dash", line_color="#E53935", annotation_text="Rough (>2.5m)", annotation_position="top right")

    max_val = max(values + [2.8])
    fig.update_layout(
        title="🌊 Live Sea State & Wave Heights",
        yaxis_title="Height (meters)",
        yaxis=dict(range=[0, max_val * 1.15]),
        template="plotly_white",
        height=320,
        margin=dict(l=40, r=40, t=50, b=40),
    )
    return fig


def create_wind_chart(weather_data: Dict[str, Any]) -> Optional[go.Figure]:
    """Generates bar chart comparing sustained wind speed, wind gusts, and safety thresholds."""
    wind_spd = weather_data.get("wind_speed")
    wind_gst = weather_data.get("wind_gusts")

    if wind_spd is None and wind_gst is None:
        return None

    categories = []
    values = []
    colors = []

    if wind_spd is not None:
        categories.append("Sustained Wind (10m)")
        values.append(float(wind_spd))
        colors.append("#5C6BC0")

    if wind_gst is not None:
        categories.append("Peak Wind Gusts")
        values.append(float(wind_gst))
        colors.append("#AB47BC")

    fig = go.Figure(
        data=[
            go.Bar(
                x=categories,
                y=values,
                marker=dict(color=colors),
                text=[f"{v:.1f} km/h" for v in values],
                textposition="auto",
                width=0.45,
            )
        ]
    )

    fig.add_hline(y=25.0, line_dash="dash", line_color="#F57C00", annotation_text="Artisanal Safe Limit (25 km/h)", annotation_position="top right")
    fig.add_hline(y=40.0, line_dash="dot", line_color="#D32F2F", annotation_text="Squall Warning (40 km/h)", annotation_position="top right")

    max_val = max(values + [30.0])
    fig.update_layout(
        title="💨 Live Wind & Gust Telemetry",
        yaxis_title="Speed (km/h)",
        yaxis=dict(range=[0, max_val * 1.15]),
        template="plotly_white",
        height=320,
        margin=dict(l=40, r=40, t=50, b=40),
    )
    return fig


def create_location_comparison_chart(comparison_payload: Dict[str, Any]) -> Optional[go.Figure]:
    """Generates multi-metric grouped bar chart comparing two coastal locations."""
    loc_a = comparison_payload.get("location_a") or {}
    loc_b = comparison_payload.get("location_b") or {}

    name_a = loc_a.get("location_name", "Location A")
    name_b = loc_b.get("location_name", "Location B")

    metrics = ["Annual Avg SST (°C)", "Avg Monsoon Waves (m)", "Post-Monsoon Waves (m)"]
    vals_a = [
        loc_a.get("annual_avg_sst_celsius", 0),
        loc_a.get("avg_monsoon_wave_height_m", 0),
        loc_a.get("avg_post_monsoon_wave_height_m", 0),
    ]
    vals_b = [
        loc_b.get("annual_avg_sst_celsius", 0),
        loc_b.get("avg_monsoon_wave_height_m", 0),
        loc_b.get("avg_post_monsoon_wave_height_m", 0),
    ]

    fig = go.Figure(
        data=[
            go.Bar(name=name_a, x=metrics, y=vals_a, marker_color="#1E88E5"),
            go.Bar(name=name_b, x=metrics, y=vals_b, marker_color="#43A047"),
        ]
    )

    fig.update_layout(
        title=f"📊 Climatological Comparison: {name_a} vs {name_b}",
        barmode="group",
        template="plotly_white",
        height=340,
        margin=dict(l=40, r=40, t=50, b=40),
    )
    return fig


def create_what_if_chart(what_if_details: Dict[str, Any]) -> Optional[go.Figure]:
    """Generates comparison chart showing baseline vs simulated what-if parameter."""
    param = what_if_details.get("parameter", "Parameter")
    baseline = what_if_details.get("baseline_value")
    simulated = what_if_details.get("simulated_value")

    if baseline is None or simulated is None:
        return None

    labels = ["Current Baseline", "Simulated Scenario"]
    vals = [float(baseline), float(simulated)]
    colors = ["#43A047" if vals[0] < 25.0 else "#FB8C00", "#E53935" if vals[1] >= 25.0 else "#43A047"]

    unit = "km/h" if "wind" in param else ("m" if "wave" in param else "")

    fig = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=vals,
                marker=dict(color=colors),
                text=[f"{v:.1f} {unit}" for v in vals],
                textposition="auto",
                width=0.45,
            )
        ]
    )

    if "wind" in param:
        fig.add_hline(y=25.0, line_dash="dash", line_color="#D32F2F", annotation_text="Artisanal Safe Threshold (25 km/h)", annotation_position="top right")

    max_val = max(vals + [30.0])
    fig.update_layout(
        title=f"🔬 What-If Simulation: {param.replace('_', ' ').title()}",
        yaxis_title=f"{param.replace('_', ' ').title()} ({unit})",
        yaxis=dict(range=[0, max_val * 1.15]),
        template="plotly_white",
        height=320,
        margin=dict(l=40, r=40, t=50, b=40),
    )
    return fig
