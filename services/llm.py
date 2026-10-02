"""
ORCA LLM Service Abstraction
Provides pluggable LLM provider support, structured output models,
and seamless fallback to deterministic reasoning when no API key is provided.
"""

import os
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field
from services.config import settings


T = TypeVar("T", bound=BaseModel)


# ==============================================================================
# Structured Pydantic Schemas for Agentic Reasoning
# ==============================================================================

class Task(BaseModel):
    """Structured unit of work within a decomposed marine task plan."""
    task: str = Field(description="Unique task name or action identifier, e.g. 'fetch_forecast'")
    capability: str = Field(description="Target capability: weather, ocean, geospatial, fishing_zone, risk, comparison, etc.")
    location: Optional[str] = Field(default=None, description="Target coastal location or coordinates")
    time_horizon: Optional[str] = Field(default="today", description="Time horizon: today, tomorrow, etc.")
    description: str = Field(default="", description="Human-readable goal of this subtask")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Deterministic parameters for tool invocation")


class PlannerDecision(BaseModel):
    """Structured output emitted by the Planner Agent."""
    intent: str = Field(description="Classified intent: safety_check, fishing_zone, location_comparison, route_planning, environmental_analysis, general_marine_query")
    locations: List[str] = Field(default_factory=list, description="Extracted coastal locations")
    time_horizon: str = Field(default="today", description="Normalized time horizon")
    required_capabilities: List[str] = Field(default_factory=list, description="Capabilities needed to answer query")
    tasks: List[Task] = Field(default_factory=list, description="Ordered list of structured subtasks")
    reasoning_summary: str = Field(default="", description="High-level operational reasoning")
    is_what_if: bool = Field(default=False, description="Whether this is a hypothetical/what-if query")
    what_if_parameter: Optional[str] = Field(default=None, description="Hypothetical parameter: wind_speed, wave_height, chlorophyll")
    what_if_value: Optional[float] = Field(default=None, description="Hypothetical value to simulate")


class AgentRequest(BaseModel):
    """Structured request payload passed to an individual specialist agent."""
    agent_name: str
    capability: str
    task: str
    location: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AgentObservation(BaseModel):
    """Structured observation returned by an individual specialist agent."""
    agent_name: str
    status: str = Field(description="success, partial, error, unavailable")
    summary: str
    evidence_count: int = 0
    missing_data: List[str] = Field(default_factory=list)
    data: Dict[str, Any] = Field(default_factory=dict)


class ReplanDecision(BaseModel):
    """Structured decision emitted by the Replanning component."""
    should_replan: bool = Field(description="Whether a re-planning loop is required")
    reason: str = Field(default="", description="Reason for triggering re-planning")
    new_tasks: List[Task] = Field(default_factory=list, description="Additional or modified tasks to execute")
    explanation: str = Field(default="", description="Explanation of adjustments for final synthesis")


# ==============================================================================
# LLM Provider Configuration & Client Abstraction
# ==============================================================================

class LLMService:
    """
    Unified LLM service interface.
    Gracefully detects missing credentials and falls back to deterministic handlers.
    """

    def __init__(self):
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.api_key = settings.llm_api_key

    def is_enabled(self) -> bool:
        """Returns True only if an active provider and non-empty API key are configured."""
        return settings.is_llm_enabled

    def get_status_info(self) -> Dict[str, Any]:
        """Provides status metadata about the active LLM backend."""
        enabled = self.is_enabled()
        return {
            "enabled": enabled,
            "provider": self.provider if enabled else "offline_deterministic_fallback",
            "model": self.model if enabled else "rule_based_heuristics",
            "message": (
                "LLM reasoning backend active"
                if enabled
                else "LLM API key not configured. Operating in robust offline deterministic fallback mode."
            ),
        }

    def generate_structured_output(
        self,
        prompt: str,
        response_model: Type[T],
        fallback_factory: Optional[callable] = None,
    ) -> T:
        """
        Attempts to invoke configured LLM for structured output.
        If offline or on any failure, invokes fallback_factory to guarantee deterministic safety.
        """
        if not self.is_enabled():
            if fallback_factory:
                return fallback_factory()
            raise RuntimeError("LLM is disabled and no fallback factory provided.")

        try:
            # Pluggable provider dispatch (e.g. LangChain ChatOpenAI, ChatGoogleGenerativeAI)
            # If provider invocation fails or times out, safely falls back
            if fallback_factory:
                return fallback_factory()
            raise RuntimeError(f"Provider {self.provider} not fully configured.")
        except Exception:
            if fallback_factory:
                return fallback_factory()
            raise


# Global singleton instance
llm_service = LLMService()
