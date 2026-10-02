"""
ORCA State Definition for LangGraph
Defines the state structure passed between LangGraph nodes during marine reasoning workflows.
Includes multi-turn session memory, what-if hypothetical attributes, and replanning counters.
"""

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
import operator


def merge_dicts(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Reducer for merging dictionary state updates."""
    merged = dict(a) if a else {}
    if b:
        merged.update(b)
    return merged


class ORCAState(TypedDict, total=False):
    """
    Central State passed between LangGraph nodes during marine reasoning workflows.
    All fields are optional when instantiating or returning node deltas.
    """
    # Core user query and session metadata
    query: str
    language: str  # "en", "mr" (Marathi), "hi" (Hindi)
    session_id: str

    # Multi-turn session memory
    conversation_history: Annotated[List[Dict[str, str]], operator.add]
    context_locations: List[str]
    context_intent: Optional[str]
    context_time_horizon: Optional[str]

    # What-If hypothetical reasoning attributes
    is_what_if: bool
    what_if_parameter: Optional[str]  # e.g. "wind_speed", "wave_height", "chlorophyll"
    what_if_value: Optional[float]    # e.g. 30.0, 2.5
    what_if_explanation: Optional[str]

    # Dynamic replanning counters & evaluation
    replan_count: int
    max_replans: int
    evaluation_summary: Optional[Dict[str, Any]]
    replan_history: Annotated[List[Dict[str, Any]], operator.add]

    # Planner decomposition & orchestration
    intent: str
    target_locations: List[Dict[str, Any]]
    time_horizon: Optional[str]
    task_plan: List[Dict[str, Any]]
    current_task: Optional[str]

    # Agent observations & deterministic outputs
    observations: Annotated[Dict[str, Any], merge_dicts]
    agent_results: Annotated[Dict[str, Any], merge_dicts]

    # Specialized domain payloads
    weather_data: Optional[Dict[str, Any]]
    ocean_data: Optional[Dict[str, Any]]
    pfz_data: Optional[Dict[str, Any]]
    geospatial_data: Optional[Dict[str, Any]]
    risk_assessment: Optional[Dict[str, Any]]
    marine_advisories: Optional[List[Dict[str, Any]]]
    route_data: Optional[Dict[str, Any]]
    evidence_correlation: Optional[Dict[str, Any]]
    temporal_scope: Optional[Dict[str, Any]]

    # Evidence, errors, and operational execution trace
    evidence_items: Annotated[List[Dict[str, Any]], operator.add]
    errors: Annotated[List[str], operator.add]
    execution_trace: Annotated[List[Dict[str, Any]], operator.add]

    # Final response
    final_response: str
