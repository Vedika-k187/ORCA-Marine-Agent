"""
ORCA Centralized Tool Registry
Provides safe, deterministic tool registration, discovery, and execution.
Guarantees the LLM can only invoke registered safe tools and never executes arbitrary Python code.
"""

from typing import Any, Callable, Dict, List, Optional
from tools.base import build_evidence, EvidenceDict
from tools.weather_tools import fetch_marine_weather
from tools.marine_tools import fetch_marine_conditions
from tools.tide_tools import fetch_tide_data
from tools.ocean_tools import fetch_ocean_analytics, fetch_sst, fetch_chlorophyll, fetch_ocean_current
from tools.advisory_tools import fetch_marine_advisories
from tools.geospatial_tools import (
    lookup_coordinates,
    haversine_distance,
    find_nearest_location,
    check_point_in_zones,
    find_nearby_marine_zones,
    evaluate_geospatial_context,
)
from tools.pfz_tools import compute_pfz_suitability
from tools.comparison_tools import compare_coastal_locations


class ToolDefinition:
    """Metadata and execution pointer for a registered tool."""
    def __init__(
        self,
        name: str,
        capability: str,
        description: str,
        func: Callable[..., Any],
        required_params: List[str],
        data_source_type: str,
    ):
        self.name = name
        self.capability = capability
        self.description = description
        self.func = func
        self.required_params = required_params
        self.data_source_type = data_source_type


class ToolRegistry:
    """Central registry of approved deterministic marine tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def register(self, tool_def: ToolDefinition):
        self._tools[tool_def.name] = tool_def

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self, capability: Optional[str] = None) -> List[ToolDefinition]:
        if capability:
            return [t for t in self._tools.values() if t.capability == capability]
        return list(self._tools.values())

    def execute(self, tool_name: str, **kwargs) -> Any:
        """
        Executes a registered tool deterministically with full error protection.
        """
        tool = self.get(tool_name)
        if not tool:
            return build_evidence(
                source="ORCA Tool Registry",
                source_type="mock",
                location=kwargs.get("location_name") or kwargs.get("loc") or "Unknown",
                variables=[],
                status="error",
                data={"error": f"Tool '{tool_name}' is not registered in the approved tool registry."},
            )

        try:
            return tool.func(**kwargs)
        except Exception as e:
            return build_evidence(
                source=f"Tool Execution Error ({tool_name})",
                source_type="mock",
                location=kwargs.get("location_name") or kwargs.get("loc") or "Unknown",
                variables=[],
                status="error",
                data={"error": f"Exception during execution of '{tool_name}': {str(e)}"},
            )

    def _register_default_tools(self):
        # Weather
        self.register(ToolDefinition(
            name="fetch_marine_weather",
            capability="weather",
            description="Fetches live forecast telemetry (wind, gusts, precipitation, temp) from Open-Meteo",
            func=fetch_marine_weather,
            required_params=["location_name"],
            data_source_type="live",
        ))

        # Marine / Ocean
        self.register(ToolDefinition(
            name="fetch_marine_conditions",
            capability="ocean",
            description="Fetches live marine wave height, swell height/period, and ocean currents from Open-Meteo Marine",
            func=fetch_marine_conditions,
            required_params=["location_name"],
            data_source_type="live",
        ))
        self.register(ToolDefinition(
            name="fetch_ocean_analytics",
            capability="ocean",
            description="Fetches satellite SST, chlorophyll-a concentration, and upwelling fixtures",
            func=fetch_ocean_analytics,
            required_params=["location_name"],
            data_source_type="sample",
        ))
        self.register(ToolDefinition(
            name="fetch_tide_data",
            capability="ocean",
            description="Fetches harmonic astronomical tide tables and tidal ranges for coastal stations",
            func=fetch_tide_data,
            required_params=["location_name"],
            data_source_type="sample",
        ))
        self.register(ToolDefinition(
            name="fetch_sst",
            capability="ocean",
            description="Fetches sea surface temperature (SST) satellite observations",
            func=fetch_sst,
            required_params=["location_name"],
            data_source_type="sample",
        ))
        self.register(ToolDefinition(
            name="fetch_chlorophyll",
            capability="ocean",
            description="Fetches chlorophyll-a concentration and oceanic optical fronts",
            func=fetch_chlorophyll,
            required_params=["location_name"],
            data_source_type="sample",
        ))
        self.register(ToolDefinition(
            name="fetch_ocean_current",
            capability="ocean",
            description="Fetches surface ocean current velocity and directional vector",
            func=fetch_ocean_current,
            required_params=["location_name"],
            data_source_type="sample",
        ))

        # Advisories & Warnings
        self.register(ToolDefinition(
            name="fetch_marine_advisories",
            capability="alert",
            description="Fetches coastal weather warnings, squall advisories, and high swell alerts",
            func=fetch_marine_advisories,
            required_params=["location"],
            data_source_type="sample",
        ))

        # Geospatial
        self.register(ToolDefinition(
            name="lookup_coordinates",
            capability="geospatial",
            description="Resolves latitude and longitude coordinates for coastal ports and landing centers",
            func=lookup_coordinates,
            required_params=["location_name"],
            data_source_type="deterministic",
        ))
        self.register(ToolDefinition(
            name="haversine_distance",
            capability="geospatial",
            description="Calculates great-circle distance in kilometers between two coordinates",
            func=haversine_distance,
            required_params=["coord1", "coord2"],
            data_source_type="deterministic",
        ))
        self.register(ToolDefinition(
            name="find_nearest_location",
            capability="geospatial",
            description="Finds closest recognized port/station to given coordinates",
            func=find_nearest_location,
            required_params=["lat", "lon"],
            data_source_type="deterministic",
        ))
        self.register(ToolDefinition(
            name="check_point_in_zones",
            capability="geospatial",
            description="Performs point-in-polygon geofencing against marine protected areas and restriction zones",
            func=check_point_in_zones,
            required_params=["lat", "lon"],
            data_source_type="sample",
        ))
        self.register(ToolDefinition(
            name="find_nearby_marine_zones",
            capability="geospatial",
            description="Discovers nearby marine zones within a spatial radius buffer",
            func=find_nearby_marine_zones,
            required_params=["lat", "lon"],
            data_source_type="sample",
        ))
        self.register(ToolDefinition(
            name="evaluate_geospatial_context",
            capability="geospatial",
            description="Comprehensive geospatial reasoning combining coordinate lookup, geofencing, and zone scan",
            func=evaluate_geospatial_context,
            required_params=["location_name"],
            data_source_type="sample",
        ))

        # Fishing Zone / PFZ
        self.register(ToolDefinition(
            name="compute_pfz_suitability",
            capability="fishing_zone",
            description="Calculates demonstration multi-factor fishing zone suitability index (0-100)",
            func=compute_pfz_suitability,
            required_params=["location_name"],
            data_source_type="sample",
        ))

        # Historical Comparison
        self.register(ToolDefinition(
            name="compare_coastal_locations",
            capability="comparison",
            description="Compares coastal climatology, monsoon wave exposure, and distance between two locations",
            func=compare_coastal_locations,
            required_params=["loc1", "loc2"],
            data_source_type="historical",
        ))


# Global tool registry singleton
tool_registry = ToolRegistry()
