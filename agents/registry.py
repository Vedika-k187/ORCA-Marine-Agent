"""
ORCA Capability Registry
Defines the capabilities available within the multi-agent system,
their supported tasks, required inputs, and associated deterministic tools.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CapabilityDefinition(BaseModel):
    """Metadata describing an agentic capability within ORCA."""
    name: str
    description: str
    supported_tasks: List[str]
    available_tools: List[str]
    required_inputs: List[str]
    output_schema: Dict[str, Any] = Field(default_factory=dict)


class CapabilityRegistry:
    """Central registry of specialized capabilities."""

    def __init__(self):
        self._capabilities: Dict[str, CapabilityDefinition] = {}
        self._register_default_capabilities()

    def register(self, cap: CapabilityDefinition):
        self._capabilities[cap.name] = cap

    def get(self, name: str) -> Optional[CapabilityDefinition]:
        return self._capabilities.get(name)

    def list_all(self) -> List[CapabilityDefinition]:
        return list(self._capabilities.values())

    def get_supported_capabilities(self) -> List[str]:
        return list(self._capabilities.keys())

    def _register_default_capabilities(self):
        self.register(CapabilityDefinition(
            name="weather",
            description="Meteorological conditions, wind speed, gusts, precipitation, atmospheric fronts",
            supported_tasks=["fetch_forecast", "fetch_wind_telemetry", "check_storm_advisories"],
            available_tools=["fetch_marine_weather"],
            required_inputs=["location_name", "time_horizon"],
            output_schema={"wind_speed": "float", "wind_gusts": "float", "precipitation": "float", "temperature": "float"},
        ))

        self.register(CapabilityDefinition(
            name="ocean",
            description="Sea state, wave heights, swell periods, ocean currents, satellite SST, and chlorophyll",
            supported_tasks=["fetch_wave_data", "fetch_ocean_analytics", "fetch_tide_data", "fetch_sst", "fetch_chlorophyll", "fetch_ocean_current"],
            available_tools=["fetch_marine_conditions", "fetch_ocean_analytics", "fetch_tide_data", "fetch_sst", "fetch_chlorophyll", "fetch_ocean_current"],
            required_inputs=["location_name"],
            output_schema={"wave_height": "float", "swell_height": "float", "sst_celsius": "float", "chlorophyll_mg_m3": "float"},
        ))

        self.register(CapabilityDefinition(
            name="geospatial",
            description="Coordinate resolution, geodesic distance, point-in-polygon geofencing, and marine zones",
            supported_tasks=["resolve_boundaries", "check_marine_zones", "compute_distance"],
            available_tools=[
                "lookup_coordinates",
                "haversine_distance",
                "find_nearest_location",
                "check_point_in_zones",
                "find_nearby_marine_zones",
                "evaluate_geospatial_context",
            ],
            required_inputs=["location_name"],
            output_schema={"coordinates": "tuple", "inside_restricted_zones": "list", "nearby_marine_zones": "list"},
        ))

        self.register(CapabilityDefinition(
            name="fishing_zone",
            description="Potential Fishing Zone (PFZ) demonstration suitability analysis based on thermal/chlorophyll fronts",
            supported_tasks=["evaluate_suitability", "fetch_pfz_advisories"],
            available_tools=["compute_pfz_suitability"],
            required_inputs=["location_name"],
            output_schema={"composite_score": "float", "suitability_category": "str", "factors_breakdown": "dict"},
        ))

        self.register(CapabilityDefinition(
            name="risk",
            description="Deterministic maritime risk evaluation synthesizing weather, sea state, and regulatory zones",
            supported_tasks=["compute_risk_index", "regulatory_safety_audit", "what_if_risk_simulation"],
            available_tools=[],  # Risk uses specialized agent synthesis
            required_inputs=["weather_data", "marine_data", "geospatial_data"],
            output_schema={"risk_level": "str", "status": "str", "reason": "str"},
        ))

        self.register(CapabilityDefinition(
            name="route",
            description="Navigational passage evaluation, waypoint clearance, and route weather auditing",
            supported_tasks=["plan_waypoints", "route_safety_audit"],
            available_tools=["lookup_coordinates", "haversine_distance", "fetch_marine_weather"],
            required_inputs=["origin", "destination"],
            output_schema={"route_waypoints": "list", "route_hazard_status": "str"},
        ))

        self.register(CapabilityDefinition(
            name="comparison",
            description="Multi-location comparative analytics across distance, seasonal wave exposure, and climatology",
            supported_tasks=["compare_weather", "compare_ocean_metrics", "comparative_risk"],
            available_tools=["compare_coastal_locations"],
            required_inputs=["loc1", "loc2"],
            output_schema={"geodesic_distance_km": "float", "comparison_data": "dict"},
        ))

        self.register(CapabilityDefinition(
            name="alerts",
            description="Severe marine weather advisories, squall warnings, and official exclusion notifications",
            supported_tasks=["scan_active_alerts", "fetch_advisories"],
            available_tools=["fetch_marine_advisories", "fetch_marine_weather"],
            required_inputs=["location_name"],
            output_schema={"active_warnings": "list", "total_advisories": "int"},
        ))
        self.register(CapabilityDefinition(
            name="alert",
            description="Severe marine weather advisories, squall warnings, and official exclusion notifications",
            supported_tasks=["scan_active_alerts", "fetch_advisories"],
            available_tools=["fetch_marine_advisories"],
            required_inputs=["location_name"],
            output_schema={"active_warnings": "list"},
        ))

        self.register(CapabilityDefinition(
            name="evidence",
            description="Evidence aggregation, classification, provenance tracking, and data sufficiency evaluation",
            supported_tasks=["audit_evidence_provenance", "evaluate_sufficiency"],
            available_tools=[],
            required_inputs=["evidence_items"],
            output_schema={"live_sources": "list", "sample_sources": "list", "historical_sources": "list"},
        ))


# Global capability registry singleton
capability_registry = CapabilityRegistry()
