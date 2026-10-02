"""
ORCA: Marine EcOsystem Reasoning with Collaborative Agents
Main Streamlit Application Dashboard
Phase 6: Real Marine Intelligence, Route Reasoning, Alerts, Change Detection & SQLite Persistent Memory
"""

import uuid
import streamlit as st
import streamlit.components.v1 as components

from graph.workflow import run_workflow
from services.llm import llm_service
from services.memory import clear_session, load_session
from services.monitor import check_location_conditions, detect_condition_change
from utils.map_visualization import create_marine_map
from utils.chart_visualization import (
    create_wave_conditions_chart,
    create_wind_chart,
    create_location_comparison_chart,
    create_what_if_chart,
)
from utils.ui_components import (
    render_header,
    render_condition_cards,
    render_pfz_suitability_card,
    render_evidence_panel,
    render_execution_trace,
    render_replanning_alert,
    render_what_if_panel,
    render_marine_advisories_panel,
    render_route_analysis_panel,
    render_condition_changes_panel,
    render_limitations_notice,
)


def init_session_state():
    """Initializes Streamlit session memory and conversation tracking."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"orca_sess_{uuid.uuid4().hex[:8]}"

    if "session_state_dict" not in st.session_state:
        # Attempt to load context from persistent SQLite
        sess = load_session(st.session_state.session_id)
        if sess:
            st.session_state.session_state_dict = {
                "context_locations": sess.get("context_locations", []),
                "context_time_horizon": sess.get("context_time_horizon", "today"),
                "conversation_history": [],
            }
        else:
            st.session_state.session_state_dict = {
                "context_locations": [],
                "context_time_horizon": "today",
                "conversation_history": [],
            }

    if "latest_result" not in st.session_state:
        st.session_state.latest_result = None

    if "surveillance_result" not in st.session_state:
        st.session_state.surveillance_result = None

    if "previous_obs" not in st.session_state:
        st.session_state.previous_obs = None

    if "user_query_input" not in st.session_state:
        st.session_state.user_query_input = "Is it safe to fish tomorrow near Ratnagiri?"


def main():
    st.set_page_config(
        page_title="ORCA - Marine Intelligence Platform",
        page_icon="🐋",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()

    # ==========================================================================
    # Sidebar
    # ==========================================================================
    with st.sidebar:
        st.markdown("### 🐋 ORCA Control Center")
        st.markdown(f"**Session ID:** `{st.session_state.session_id}`")

        llm_info = llm_service.get_status_info()
        st.markdown(f"**Agent Engine:** `LangGraph Multi-Agent Core`")
        st.markdown(f"**LLM Backend:** `{llm_info['provider']}`")
        st.caption(llm_info["message"])

        # Display persistent session memory context
        stored_locs = st.session_state.session_state_dict.get("context_locations", [])
        if stored_locs:
            st.markdown(f"**Active Session Locations:** `{', '.join(stored_locs)}`")

        st.markdown("---")
        st.markdown("#### 🎯 Quick Queries (Phase 6 Scenarios)")
        st.caption("Click any preset to load into ORCA's reasoning pipeline:")

        example_queries = [
            "Is it safe to fish tomorrow near Ratnagiri?",
            "Are there marine warnings near Ratnagiri tomorrow?",
            "Find an informational route from Ratnagiri to Goa.",
            "Compare Ratnagiri and Goa.",
            "Which has lower waves?",
            "What if wind speed increases to 30 km/h near Ratnagiri?",
            "Compare tomorrow morning and evening near Ratnagiri.",
            "Find nearby favourable fishing zones.",
            "Are there restricted zones near Ratnagiri?",
        ]

        for q in example_queries:
            if st.button(q, key=f"btn_{q}"):
                st.session_state.user_query_input = q
                st.session_state.execute_query = True

        st.markdown("---")
        st.markdown("#### 📡 Surveillance & Proactive Monitoring")
        monitor_loc = stored_locs[0] if stored_locs else "Ratnagiri"
        if st.button(f"🔍 Check Condition Changes ({monitor_loc})"):
            curr_obs = check_location_conditions(monitor_loc)
            changes = detect_condition_change(st.session_state.previous_obs, curr_obs)
            st.session_state.previous_obs = curr_obs
            st.session_state.surveillance_result = changes

        st.markdown("---")
        st.markdown("#### ⚙️ UI Display Controls")
        show_raw_json = st.checkbox("Show Raw Evidence JSON", value=False)

        if st.button("🔄 Clear SQLite Session Memory"):
            clear_session(st.session_state.session_id)
            st.session_state.session_state_dict = {
                "context_locations": [],
                "context_time_horizon": "today",
                "conversation_history": [],
            }
            st.session_state.latest_result = None
            st.session_state.surveillance_result = None
            st.session_state.previous_obs = None
            st.session_state.session_id = f"orca_sess_{uuid.uuid4().hex[:8]}"
            st.success("Persistent session cleared.")

    # ==========================================================================
    # Main Dashboard Header
    # ==========================================================================
    render_header()

    # Query Input Section
    col_input, col_btn = st.columns([0.85, 0.15])
    with col_input:
        query = st.text_input(
            "Enter Marine Query, Navigation Question, or Scenario Simulation:",
            value=st.session_state.user_query_input,
            key="main_query_input",
        )
    with col_btn:
        st.write("")
        st.write("")
        submit_clicked = st.button("🚀 Ask ORCA", type="primary", use_container_width=True)

    # Check if we should execute
    should_run = submit_clicked or st.session_state.get("execute_query", False)
    if should_run:
        st.session_state.execute_query = False
        with st.spinner("🐋 ORCA Collaborative Agents decomposing query and querying marine telemetry..."):
            try:
                result = run_workflow(
                    query=query,
                    session_id=st.session_state.session_id,
                    session_state=st.session_state.session_state_dict,
                )
                st.session_state.latest_result = result

                # Update session memory in UI state
                planner_res = result.get("agent_results", {}).get("planner") or {}
                extracted_locs = planner_res.get("locations") or []
                if extracted_locs:
                    st.session_state.session_state_dict["context_locations"] = extracted_locs
                if planner_res.get("time_horizon"):
                    st.session_state.session_state_dict["context_time_horizon"] = planner_res.get("time_horizon")
                if result.get("final_response"):
                    st.session_state.session_state_dict["conversation_history"].append(
                        {"user": query, "assistant": result.get("final_response")}
                    )

            except Exception as e:
                st.error(f"Error during workflow execution: {str(e)}")

    # Proactive Surveillance Panel (if triggered)
    if st.session_state.surveillance_result:
        render_condition_changes_panel(st.session_state.surveillance_result)

    # ==========================================================================
    # Query-Specific Dynamic Results Presentation
    # ==========================================================================
    result = st.session_state.latest_result

    if result:
        st.markdown("---")
        intent = result.get("intent", "general_marine_query")

        # 1. Main Response Card
        with st.container():
            st.markdown(result.get("final_response", ""))

        # 2. What-If Panel (if applicable)
        if result.get("is_what_if"):
            render_what_if_panel(result)

        # 3. Active Marine Advisories Panel (prominent if warnings present or advisory_check)
        if result.get("marine_advisories"):
            render_marine_advisories_panel(result)

        # 4. Route Analysis Panel (prominent if route_planning)
        if result.get("route_data"):
            render_route_analysis_panel(result)

        # 5. Replanning Alert (if replan was triggered)
        if result.get("replan_history"):
            render_replanning_alert(result.get("replan_history", []))

        # 6. Marine Condition Cards (Wind, Waves, Temp, Oceanography)
        # Adaptively shown for safety, comparison, fishing, or general queries
        render_condition_cards(result)

        # 7. Interactive Map & Chart Section (2 Columns)
        st.markdown("---")
        st.subheader("🗺 Marine Spatial Intelligence & Visual Analytics")

        map_col, chart_col = st.columns([0.55, 0.45])

        target_locs = [
            loc.get("name") if isinstance(loc, dict) else str(loc)
            for loc in result.get("target_locations", [])
        ]
        if not target_locs:
            target_locs = ["Ratnagiri"]

        # Left Column: Interactive Folium Map
        with map_col:
            st.markdown(f"**Spatial View:** `{', '.join(target_locs)}` and surrounding corridors")
            m = create_marine_map(target_locations=target_locs, workflow_result=result)
            components.html(m._repr_html_(), height=420)
            if result.get("route_data"):
                st.caption("🚢 *Green: Recommended Safe Offshore Route | Amber (dashed): Direct Inshore Route | Red/Orange: Marine Zones*")
            else:
                st.caption("📍 *Blue pins: coastal ports | Red/Orange: sample exclusion/port limit zones | Green: sample artisanal fishing zone*")

        # Right Column: Relevant Plotly Chart
        with chart_col:
            st.markdown("**Deterministic Telemetry Chart**")
            chart_rendered = False

            # Priority 1: What-If simulation chart
            if result.get("is_what_if"):
                risk_metrics = (result.get("risk_assessment") or {}).get("preliminary_metrics", {})
                w_details = risk_metrics.get("what_if_details")
                if w_details:
                    fig_whatif = create_what_if_chart(w_details)
                    if fig_whatif:
                        st.plotly_chart(fig_whatif, use_container_width=True)
                        chart_rendered = True

            # Priority 2: Location comparison chart
            if not chart_rendered and result.get("geospatial_data", {}).get("comparison"):
                comp_data = result["geospatial_data"]["comparison"]
                fig_comp = create_location_comparison_chart(comp_data)
                if fig_comp:
                    st.plotly_chart(fig_comp, use_container_width=True)
                    chart_rendered = True

            # Priority 3: Wave conditions chart
            if not chart_rendered:
                w_payload = result.get("weather_data") or {}
                m_data = w_payload.get("marine_data") or result.get("ocean_data", {}).get("marine_telemetry") or {}
                fig_wave = create_wave_conditions_chart(m_data)
                if fig_wave:
                    st.plotly_chart(fig_wave, use_container_width=True)
                    chart_rendered = True

            # Priority 4: Wind chart fallback
            if not chart_rendered:
                w_payload = result.get("weather_data") or {}
                w_inner = w_payload.get("weather_data") or {}
                fig_wind = create_wind_chart(w_inner)
                if fig_wind:
                    st.plotly_chart(fig_wind, use_container_width=True)
                    chart_rendered = True

            if not chart_rendered:
                st.info("No numerical telemetry chart available for this general query.")

        # 8. Demonstration PFZ Suitability (if calculated)
        if intent == "fishing_zone" or result.get("pfz_data"):
            render_pfz_suitability_card(result.get("pfz_data") or {})

        # 9. Agent Execution Trace
        render_execution_trace(result.get("execution_trace", []))

        # 10. Evidence Inventory & Provenance Panel
        render_evidence_panel(result.get("evidence_items", []), show_raw_json=show_raw_json)

        # 11. Advisory & Legal Limitations Notice
        render_limitations_notice()


if __name__ == "__main__":
    main()
