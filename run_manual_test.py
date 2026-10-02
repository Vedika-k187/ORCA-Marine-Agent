"""
ORCA Phase 6 Manual Verification Runner
Executes all required real marine intelligence scenarios:

A. "Is it safe to fish tomorrow near Ratnagiri?"
B. "Compare Ratnagiri and Goa."
C. "Find nearby favourable fishing zones."
D. "Are there restricted zones near Ratnagiri?"
E. "What if wind speed increases to 30 km/h near Ratnagiri?"
F. "Find an informational route from Ratnagiri to Goa."
G. "Are there marine warnings near Ratnagiri tomorrow?"
H. "Compare tomorrow morning and evening near Ratnagiri."
I. Turn 1: "Compare Ratnagiri and Goa." -> Turn 2: "Which has lower waves?" (Session continuity)
J. Fault injection & graceful fallback:
   - Marine API failure
   - Advisory feed unavailable
   - SQLite unavailable
"""

import sys
from typing import Any, Dict, Optional
from unittest.mock import patch

from graph.workflow import run_workflow
from services.memory import save_session, load_session, clear_session
from tools.advisory_tools import fetch_marine_advisories

# Configure UTF-8 encoding on Windows terminal
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def display_scenario(scenario_id: str, title: str, query: str, session_id: str = "demo_session", session_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("=" * 80)
    print(f"SCENARIO {scenario_id}: {title}")
    print(f"Query: \"{query}\"")
    print("=" * 80)

    result: Dict[str, Any] = run_workflow(query, session_id=session_id, session_state=session_state)

    print(f"\n[1] DETECTED INTENT & PLANNING:")
    print(f"    Intent:                {result.get('intent')}")
    locs = [l.get("name") if isinstance(l, dict) else str(l) for l in result.get("target_locations", [])]
    print(f"    Target Location(s):    {', '.join(locs) if locs else 'General Coastal Zone'}")
    print(f"    Time Horizon:          {result.get('time_horizon')}")
    if result.get("temporal_scope"):
        ts = result.get("temporal_scope")
        print(f"    Temporal Scope:        {ts.get('scope')} (Sub-period: {ts.get('sub_period')}, Hours ahead: {ts.get('hours_ahead')})")
    planner_obs = result.get("agent_results", {}).get("planner") or {}
    print(f"    Selected Capabilities: {planner_obs.get('required_capabilities', [])}")

    print(f"\n[2] STRUCTURED TASK PLAN:")
    for idx, t in enumerate(result.get("task_plan", []), 1):
        task_name = t.get("task") or t.get("action")
        cap = t.get("capability") or t.get("agent")
        desc = t.get("description", "")
        print(f"    {idx}. [{cap}] {task_name}: {desc}")

    print(f"\n[3] TOOLS ACTUALLY CALLED & EVIDENCE COLLECTED ({len(result.get('evidence_items', []))} items):")
    for idx, ev in enumerate(result.get("evidence_items", []), 1):
        stype = ev.get("source_type", "unknown").upper()
        src = ev.get("source", "Unknown")
        loc = ev.get("location", "N/A")
        status = ev.get("status", "unknown")
        vars_str = ", ".join(ev.get("variables", []))
        print(f"    {idx}. [{stype:<10}] Source: {src}")
        print(f"       Location: {loc} | Status: {status} | Variables: {vars_str}")

    # Route reasoning display if applicable
    if result.get("route_data"):
        r = result["route_data"]
        rec = r.get("recommended_route") or {}
        print(f"\n[ROUTE REASONING]:")
        print(f"    Passage: {r.get('origin')} -> {r.get('destination')}")
        print(f"    Recommended Corridor: {rec.get('route_name')} (Distance: {rec.get('total_distance_km')} km, Score: {rec.get('route_score')})")
        print(f"    Disclaimer: {r.get('route_disclaimer')}")

    # Active advisories if applicable
    if result.get("marine_advisories"):
        print(f"\n[ACTIVE ADVISORIES ({len(result['marine_advisories'])} items)]:")
        for adv in result["marine_advisories"]:
            print(f"    - [{adv.get('severity')}] {adv.get('affected_region')}: {adv.get('headline')}")

    # Cross-domain evidence correlation
    if result.get("evidence_correlation"):
        corr = result["evidence_correlation"]
        print(f"\n[EVIDENCE CORRELATION]:")
        print(f"    Metocean Coherence: {corr.get('metocean_coherence')}")
        print(f"    Summary: {corr.get('correlation_summary')}")

    print(f"\n[4] AGENT EXECUTION FLOW & OPERATIONAL TRACE:")
    flow = [e["node"] for e in result.get("execution_trace", [])]
    print(f"    Flow: {' -> '.join(flow)}")

    print(f"\n[5] FINAL EVIDENCE-BACKED RESPONSE:")
    print("-" * 80)
    print(result.get("final_response"))
    print("-" * 80)
    print("\n")

    return result


def run_all_phase6_demos():
    print("\n" + "#" * 80)
    print("ORCA PHASE 6: REAL MARINE INTELLIGENCE, ROUTE REASONING & ALERTS DEMONSTRATION")
    print("#" * 80 + "\n")

    # A: Operational Safety
    display_scenario("A", "Operational Safety Query", "Is it safe to fish tomorrow near Ratnagiri?")

    # B: Comparison
    display_scenario("B", "Coastal Climatological Comparison", "Compare Ratnagiri and Goa.")

    # C: Fishing Zones
    display_scenario("C", "Demonstration Fishing Zones", "Find nearby favourable fishing zones.")

    # D: Restricted Zones
    display_scenario("D", "Geospatial Boundary Restrictions", "Are there restricted zones near Ratnagiri?")

    # E: What-If Simulation
    display_scenario("E", "What-If Simulated Wind Surge", "What if wind speed increases to 30 km/h near Ratnagiri?")

    # F: Informational Route Planning
    display_scenario("F", "Informational Route Planning & Safety Scoring", "Find an informational route from Ratnagiri to Goa.")

    # G: Marine Warnings
    display_scenario("G", "Active Marine Advisories & Squall Warnings", "Are there marine warnings near Ratnagiri tomorrow?")

    # H: Temporal Horizon Comparison
    display_scenario("H", "Temporal Reasoning & Forecast Comparison", "Compare tomorrow morning and evening near Ratnagiri.")

    # I: Multi-turn Session Memory
    print("=" * 80)
    print("SCENARIO I: MULTI-TURN PERSISTENT SESSION CONTINUITY")
    print("=" * 80)
    sess_id = "phase6_session_demo"
    clear_session(sess_id)
    t1 = display_scenario("I.1", "Turn 1: Establish Context Locations", "Compare Ratnagiri and Goa.", session_id=sess_id)
    t2 = display_scenario("I.2", "Turn 2: Anaphoric Follow-up", "Which has lower waves?", session_id=sess_id)

    # J: Fault Injection & Graceful Fallback
    print("=" * 80)
    print("SCENARIO J: FAULT RESILIENCE & GRACEFUL FALLBACK SIMULATION")
    print("=" * 80)

    # 1. Marine API 503 Outage
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
        res_j1 = run_workflow("Is it safe to fish tomorrow near Ratnagiri?")
        print("[J.1] Marine API Outage Handled Gracefully:")
        print(f"      Risk status: {res_j1.get('risk_assessment', {}).get('status')}")
        print(f"      Risk level:  {res_j1.get('risk_assessment', {}).get('risk_level')}")
        assert res_j1.get("final_response") != ""

    # 2. Advisory feed missing
    with patch("tools.advisory_tools.load_raw_advisories", return_value=[]):
        adv_res = fetch_marine_advisories("Ratnagiri")
        print("[J.2] Missing Advisory Feed Handled Gracefully:")
        print(f"      Status: {adv_res.get('status')} | Classification: {adv_res.get('source_type')}")
        assert adv_res.get("status") == "unavailable"

    # 3. SQLite unavailable
    def mock_sqlite_fail(*args, **kwargs):
        raise RuntimeError("Simulated SQLite Disk Error")

    with patch("sqlite3.connect", side_effect=mock_sqlite_fail):
        save_session("sim_fail_sess", {"target_locations": [{"name": "Ratnagiri"}]})
        loaded = load_session("sim_fail_sess")
        print("[J.3] SQLite Failure Handled Gracefully:")
        print(f"      Recovered from memory fallback: {loaded is not None}")
        assert loaded is not None

    print("\n" + "=" * 80)
    print("ALL PHASE 6 VERIFICATION SCENARIOS COMPLETED SUCCESSFULLY")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_all_phase6_demos()
