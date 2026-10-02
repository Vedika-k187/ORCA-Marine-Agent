"""
ORCA Streamlit UI Components
Reusable presentation widgets for condition cards, evidence badges, execution traces,
replanning alerts, what-if panels, and safety notices.
"""

from typing import Any, Dict, List, Optional
import streamlit as st


def render_header():
    """Renders the top ORCA platform header and badge indicators."""
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.title("🐋 ORCA: Marine Intelligence Platform")
        st.caption("Marine EcOsystem Reasoning with Collaborative Agents | LangGraph Agentic Core")
    with col2:
        st.markdown(
            """
            <div style="text-align: right; padding-top: 15px;">
                <span style="background-color: #E8F5E9; color: #2E7D32; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                    ● ENGINE ONLINE
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_condition_cards(workflow_result: Dict[str, Any]):
    """Renders key meteorological, wave, and oceanographic cards with source provenance tags."""
    st.subheader("📊 Marine Conditions & Telemetry")

    weather_payload = workflow_result.get("weather_data") or {}
    weather_inner = weather_payload.get("weather_data") or {}
    marine_inner = weather_payload.get("marine_data") or workflow_result.get("ocean_data", {}).get("marine_telemetry") or {}
    ocean_payload = workflow_result.get("ocean_data") or {}
    ocean_inner = ocean_payload.get("ocean_analytics") or {}

    col1, col2, col3, col4 = st.columns(4)

    # 1. Wind
    with col1:
        w_spd = weather_inner.get("wind_speed")
        w_gst = weather_inner.get("wind_gusts")
        st.markdown(
            """
            <div style="background-color: #F8F9FA; padding: 12px; border-radius: 8px; border-left: 4px solid #1E88E5;">
                <span style="font-size: 10px; background-color: #E3F2FD; color: #1565C0; padding: 2px 6px; border-radius: 4px; font-weight: bold;">LIVE • Open-Meteo</span>
                <p style="margin: 4px 0 0 0; color: #555; font-size: 13px;">💨 Wind Speed</p>
                <h3 style="margin: 0; color: #1E88E5;">""" + (f"{w_spd} km/h" if w_spd is not None else "N/A") + """</h3>
                <small style="color: #777;">Gusts: """ + (f"{w_gst} km/h" if w_gst is not None else "N/A") + """</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 2. Waves
    with col2:
        m_wave = marine_inner.get("wave_height")
        m_swell = marine_inner.get("swell_height")
        st.markdown(
            """
            <div style="background-color: #F8F9FA; padding: 12px; border-radius: 8px; border-left: 4px solid #00ACC1;">
                <span style="font-size: 10px; background-color: #E0F7FA; color: #00838F; padding: 2px 6px; border-radius: 4px; font-weight: bold;">LIVE • Open-Meteo Marine</span>
                <p style="margin: 4px 0 0 0; color: #555; font-size: 13px;">🌊 Wave Height</p>
                <h3 style="margin: 0; color: #00ACC1;">""" + (f"{m_wave} m" if m_wave is not None else "N/A") + """</h3>
                <small style="color: #777;">Swell: """ + (f"{m_swell} m" if m_swell is not None else "N/A") + """</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 3. Air Temp & Condition
    with col3:
        w_temp = weather_inner.get("temperature")
        w_cond = weather_inner.get("weather_condition", "Clear")
        st.markdown(
            """
            <div style="background-color: #F8F9FA; padding: 12px; border-radius: 8px; border-left: 4px solid #FB8C00;">
                <span style="font-size: 10px; background-color: #FFF3E0; color: #E65100; padding: 2px 6px; border-radius: 4px; font-weight: bold;">LIVE • Open-Meteo</span>
                <p style="margin: 4px 0 0 0; color: #555; font-size: 13px;">🌡 Air Temp & Condition</p>
                <h3 style="margin: 0; color: #FB8C00;">""" + (f"{w_temp}°C" if w_temp is not None else "N/A") + """</h3>
                <small style="color: #777;">""" + str(w_cond) + """</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 4. Oceanography (SST & Chlorophyll)
    with col4:
        sst = ocean_inner.get("sst_celsius")
        chloro = ocean_inner.get("chlorophyll_mg_m3")
        st.markdown(
            """
            <div style="background-color: #F8F9FA; padding: 12px; border-radius: 8px; border-left: 4px solid #43A047;">
                <span style="font-size: 10px; background-color: #E8F5E9; color: #2E7D32; padding: 2px 6px; border-radius: 4px; font-weight: bold;">SAMPLE • Copernicus Fixture</span>
                <p style="margin: 4px 0 0 0; color: #555; font-size: 13px;">🛰 SST / Chlorophyll</p>
                <h3 style="margin: 0; color: #43A047;">""" + (f"{sst}°C" if sst is not None else "N/A") + """</h3>
                <small style="color: #777;">Chl: """ + (f"{chloro} mg/m³" if chloro is not None else "N/A") + """</small>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_pfz_suitability_card(pfz_data: Dict[str, Any]):
    """Renders the demonstration fishing zone suitability widget with explicit non-official disclaimer."""
    if not pfz_data:
        return

    score = pfz_data.get("composite_score", 0)
    category = pfz_data.get("suitability_category", "N/A")
    rec = pfz_data.get("operational_recommendation", "")
    factors = pfz_data.get("factors_breakdown") or {}

    with st.expander("🐟 ORCA Demonstration Fishing-Zone (PFZ) Suitability", expanded=True):
        st.markdown(
            """
            <div style="background-color: #E8F5E9; padding: 12px; border-radius: 6px; border-left: 4px solid #2E7D32; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 16px; font-weight: bold; color: #1B5E20;">Suitability Score: """ + str(score) + """ / 100</span>
                    <span style="background-color: #A5D6A7; color: #1B5E20; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">""" + category + """</span>
                </div>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #2E7D32;">""" + rec + """</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cols = st.columns(4)
        with cols[0]:
            sst_f = factors.get("sst", {})
            st.metric("SST Weight (30%)", f"{sst_f.get('value_celsius', 'N/A')} °C", f"Score: {sst_f.get('subscore', 'N/A')}")
        with cols[1]:
            chl_f = factors.get("chlorophyll", {})
            st.metric("Chlorophyll (35%)", f"{chl_f.get('value_mg_m3', 'N/A')} mg/m³", f"Score: {chl_f.get('subscore', 'N/A')}")
        with cols[2]:
            dst_f = factors.get("distance", {})
            st.metric("Distance (15%)", f"{dst_f.get('distance_offshore_km', 'N/A')} km", f"Score: {dst_f.get('subscore', 'N/A')}")
        with cols[3]:
            sea_f = factors.get("sea_state", {})
            st.metric("Sea State (20%)", f"{sea_f.get('wave_height_m', 'N/A')} m", f"Score: {sea_f.get('subscore', 'N/A')}")

        st.caption("⚠️ **Notice**: This is an ORCA demonstration computational model and is **NOT** an official INCOIS Potential Fishing Zone (PFZ) advisory.")


def render_evidence_panel(evidence_items: List[Dict[str, Any]], show_raw_json: bool = False):
    """Renders the evidence inventory cleanly distinguishing LIVE, SAMPLE, HISTORICAL, and UNAVAILABLE."""
    with st.expander(f"📁 Evidence Inventory & Provenance ({len(evidence_items)} items collected)", expanded=False):
        if not evidence_items:
            st.info("No external evidence items collected for this informational query.")
            return

        for idx, ev in enumerate(evidence_items, 1):
            stype = ev.get("source_type", "mock").upper()
            src = ev.get("source", "Unknown")
            loc = ev.get("location", "N/A")
            status = ev.get("status", "unknown")
            vars_list = ", ".join(ev.get("variables", []))

            # Color badge by source type
            if stype == "LIVE":
                badge = '<span style="background-color: #E8F5E9; color: #2E7D32; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">LIVE</span>'
            elif stype == "SAMPLE":
                badge = '<span style="background-color: #FFF3E0; color: #E65100; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">SAMPLE</span>'
            elif stype == "HISTORICAL":
                badge = '<span style="background-color: #F3E5F5; color: #6A1B9A; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">HISTORICAL</span>'
            else:
                badge = '<span style="background-color: #FFEBEE; color: #C62828; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">MOCK / UNAVAILABLE</span>'

            status_icon = "🟢" if status == "available" else "🔴"

            st.markdown(
                f"""
                <div style="border-bottom: 1px solid #EEE; padding: 6px 0;">
                    {status_icon} {badge} <b>{src}</b> — <i>Location: {loc}</i><br>
                    <small style="color: #666;">Variables: {vars_list} | Status: <b>{status}</b></small>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if show_raw_json:
                st.json(ev.get("data", {}))


def render_execution_trace(execution_trace: List[Dict[str, Any]]):
    """Renders the dynamic agent execution trace showing nodes that actually executed."""
    st.subheader("🧭 Dynamic Agent Execution Trace")

    node_icon_map = {
        "planner": "🧠 Planner Agent",
        "weather": "🌦 Weather Agent",
        "ocean": "🌊 Ocean Analytics Agent",
        "geospatial": "🗺 Geospatial Agent",
        "fishing_zone": "🐟 Fishing Specialist Agent",
        "risk": "⚠️ Risk Reasoning Agent",
        "evaluator": "🔍 Observation Evaluator",
        "replan": "🔄 Dynamic Replanner",
        "response": "📝 Response Synthesizer",
    }

    # Visual pipeline chain
    steps = [node_icon_map.get(e["node"], e["node"].title()) for e in execution_trace]
    pipeline_html = " ➔ ".join([f"<b>{s}</b>" for s in steps])

    st.markdown(
        f"""
        <div style="background-color: #F0F4F8; padding: 10px 14px; border-radius: 6px; font-size: 13px; color: #2C3E50; margin-bottom: 12px;">
            {pipeline_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Detailed Operational Event Log", expanded=False):
        for idx, event in enumerate(execution_trace, 1):
            n = event.get("node", "")
            action = event.get("action", "")
            status = event.get("status", "")
            details = event.get("details", {})
            st.markdown(f"**{idx}. [{n.upper()}]** Action: `{action}` | Status: `{status}`")
            if details:
                st.json(details)


def render_replanning_alert(replan_history: List[Dict[str, Any]]):
    """Prominently visualizes dynamic replanning events if an API outage or missing feed occurred."""
    if not replan_history:
        return

    st.markdown(
        """
        <div style="background-color: #FFF8E1; border-left: 5px solid #FFA000; padding: 12px; border-radius: 6px; margin: 12px 0;">
            <b style="color: #FF8F00; font-size: 15px;">🔄 ORCA Dynamic Replanning Activated</b>
            <p style="margin: 4px 0 8px 0; font-size: 13px; color: #5D4037;">
                The observation evaluator detected missing or failed telemetry feeds during live execution.
                The system automatically re-routed tasks to gather available secondary evidence.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for item in replan_history:
        st.info(f"**Replan Iteration #{item.get('replan_iteration')}:** Reason: *{item.get('reason')}* — Fallback task: `{', '.join(item.get('injected_tasks', []))}`")


def render_what_if_panel(workflow_result: Dict[str, Any]):
    """Renders hypothetical what-if scenario results if a simulation query was executed."""
    if not workflow_result.get("is_what_if"):
        return

    param = workflow_result.get("what_if_parameter", "variable")
    val = workflow_result.get("what_if_value", "simulated")
    risk = workflow_result.get("risk_assessment") or {}
    prelim = risk.get("preliminary_metrics", {})
    details = prelim.get("what_if_details", {})
    impact = details.get("impact", "Simulated scenario evaluated deterministically against safety thresholds.")

    st.markdown(
        f"""
        <div style="background-color: #EDE7F6; border-left: 5px solid #7E57C2; padding: 12px; border-radius: 6px; margin: 12px 0;">
            <b style="color: #512DA8; font-size: 15px;">🔬 What-If Hypothetical Scenario Result</b><br>
            <b>Simulated Parameter:</b> <code>{param}</code> = <b>{val}</b><br>
            <b>Deterministic Impact:</b> {impact}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_marine_advisories_panel(workflow_result: Dict[str, Any]):
    """Renders active coastal marine advisories, squall warnings, and high swell bulletins."""
    advisories = workflow_result.get("marine_advisories") or []
    if not advisories:
        return

    st.subheader("⚠️ Active Coastal Marine Advisories (SAMPLE Feed)")
    st.caption("Structured advisories derived from sample INCOIS / IMD marine weather bulletins.")

    severity_colors = {
        "CRITICAL": "#DC2626",
        "SEVERE": "#DC2626",
        "WARNING": "#EA580C",
        "ADVISORY": "#2563EB",
        "INFORMATIONAL": "#4B5563",
    }

    for adv in advisories:
        sev = adv.get("severity", "ADVISORY").upper()
        color = severity_colors.get(sev, "#2563EB")
        region = adv.get("affected_region", "Coastal Sector")
        headline = adv.get("headline", "Marine Weather Advisory")
        desc = adv.get("description", "")
        rec_act = adv.get("recommended_action", "")
        valid_until = adv.get("valid_until", "N/A")

        st.markdown(
            f"""
            <div style="background-color: #FEF2F2 if sev in ['CRITICAL', 'SEVERE'] else #FFFBEB; border-left: 5px solid {color}; padding: 12px; border-radius: 6px; margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                        {sev} • {region}
                    </span>
                    <span style="font-size: 11px; color: #6B7280;">Valid until: {valid_until}</span>
                </div>
                <h4 style="margin: 6px 0 4px 0; color: #1F2937;">{headline}</h4>
                <p style="margin: 0 0 6px 0; font-size: 13px; color: #4B5563;">{desc}</p>
                """ + (f"<div style='font-size: 12px; color: #B91C1C;'><b>Action Advised:</b> {rec_act}</div>" if rec_act else "") + """
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_route_analysis_panel(workflow_result: Dict[str, Any]):
    """Renders candidate passages, waypoint clearance, and safety scores."""
    route_data = workflow_result.get("route_data")
    if not route_data:
        return

    st.subheader("🧭 ORCA Informational Route Analysis")
    st.markdown(
        """
        <div style="background-color: #EFF6FF; border: 1px solid #BFDBFE; padding: 8px 12px; border-radius: 6px; font-size: 12px; color: #1E40AF; margin-bottom: 12px;">
            ℹ️ <b>ORCA INFORMATIONAL ROUTE — Not Certified for Official Navigation</b><br>
            Deterministic route modeling for comparative analysis. Not an official ECDIS or Admiralty passage plan.
        </div>
        """,
        unsafe_allow_html=True,
    )

    origin = route_data.get("origin")
    dest = route_data.get("destination")
    rec_route = route_data.get("recommended_route") or {}
    candidates = route_data.get("candidate_routes", [])

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Passage", f"{origin} ➔ {dest}")
    with c2:
        dist = rec_route.get("total_distance_km", route_data.get("total_distance_km", "N/A"))
        st.metric("Recommended Distance", f"{dist} km")
    with c3:
        score = rec_route.get("route_score", "N/A")
        st.metric("Safety Score", f"{score}", help="Lower score indicates safer passage (less hazard/zone exposure)")

    if len(candidates) >= 2:
        st.markdown("**Candidate Routes Comparison:**")
        table_rows = []
        for c in candidates:
            r_name = c.get("route_name", "Route")
            r_dist = f"{c.get('total_distance_km')} km"
            r_score = str(c.get("route_score"))
            r_risk = c.get("risk_category", "FAVORABLE")
            r_rec = c.get("recommendation", "")
            zones = ", ".join(c.get("restricted_zone_intersections", [])) or "None (Clear)"
            table_rows.append({
                "Corridor": r_name,
                "Distance": r_dist,
                "Route Score": r_score,
                "Risk Rating": r_risk,
                "Protected Zone Crossing": zones,
                "Recommendation": r_rec,
            })
        st.table(table_rows)

    with st.expander("Deterministic Route Scoring Formula & Audit", expanded=False):
        st.code(route_data.get("scoring_formula", "route_score = distance*0.1 + zone_penalty + hazard_penalty + marine_penalty + advisory_penalty"))
        st.caption("Penalties: +50 per restricted MPA intersected; +25 per regulated zone buffer; +25 inshore shallow shoals; +35 active high sea advisory.")


def render_condition_changes_panel(changes_result: Dict[str, Any]):
    """Renders change detection surveillance results comparing previous vs current observations."""
    if not changes_result:
        return

    st.subheader("📡 Environmental Change Detection Surveillance")
    changed = changes_result.get("changed", False)
    summary = changes_result.get("summary", "Stable conditions.")

    if not changed:
        st.success(f"✅ {summary}")
    else:
        st.warning(f"⚠️ {summary}")
        for ch in changes_result.get("changes", []):
            direction_icon = "🔺" if ch.get("direction") == "increased" else ("🔻" if ch.get("direction") == "decreased" else "🔄")
            st.markdown(f"- **{direction_icon} {ch.get('variable').upper()}:** {ch.get('description')}")


def render_limitations_notice():
    """Renders honest data limitations and official maritime authority advisory notice."""
    st.markdown(
        """
        <div style="background-color: #ECEFF1; padding: 10px 14px; border-radius: 6px; font-size: 12px; color: #455A64; margin-top: 20px;">
            🛡 <b>Advisory & Data Governance Notice</b>: ORCA provides computational decision-support modeling.
            Live weather and wave metrics are ingested in real-time from Open-Meteo. Satellite oceanography (SST/Chlorophyll), tidal tables, marine advisories, and marine zones are demonstration sample fixtures.
            Because direct official government feeds (INCOIS / IMD) are not fully integrated, ORCA does not issue certified operational safety clearances. Always consult local port authorities before setting sail.
        </div>
        """,
        unsafe_allow_html=True,
    )
