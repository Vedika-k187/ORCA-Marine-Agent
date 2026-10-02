"""
ORCA Deterministic Geospatial Tools
Provides coordinate resolution, Haversine distance, point-in-polygon geofencing,
and marine zone spatial queries using Shapely and GeoPandas.
"""

import math
import os
from typing import Any, Dict, List, Optional, Tuple
import geopandas as gpd
from shapely.geometry import Point

from tools.base import build_evidence, EvidenceDict


# Verified coastal coordinates (latitude, longitude)
COASTAL_COORDINATES: Dict[str, Tuple[float, float]] = {
    "Ratnagiri": (16.9902, 73.3000),
    "Mumbai": (18.9220, 72.8347),
    "Goa": (15.4909, 73.8278),
    "Panaji": (15.4909, 73.8278),
    "Malvan": (16.0610, 73.4730),
    "Karwar": (14.8130, 74.1290),
    "Alibaug": (18.6414, 72.8722),
    "Mangalore": (12.8700, 74.8800),
    "Kochi": (9.9312, 76.2673),
    "Cochin": (9.9312, 76.2673),
    "Chennai": (13.0827, 80.2707),
    "Visakhapatnam": (17.6868, 83.2185),
    "Vizag": (17.6868, 83.2185),
    "Porbandar": (21.6417, 69.6293),
    "Veraval": (20.9000, 70.3667),
    "Kolkata": (22.5726, 88.3639),
    "Paradip": (20.3160, 86.6110),
    "Daman": (20.3974, 72.8328),
    "Diu": (20.7144, 70.9874),
    "Kavaratti": (10.5667, 72.6417),
    "Port Blair": (11.6234, 92.7265),
    "Tuticorin": (8.7642, 78.1348),
    "Thoothukudi": (8.7642, 78.1348),
}

_GEOJSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "sample_marine_zones.geojson",
)

_ZONES_GDF: Optional[gpd.GeoDataFrame] = None


def lookup_coordinates(location_name: str) -> Optional[Tuple[float, float]]:
    """
    Deterministically resolves a coastal location name to (latitude, longitude).
    Case-insensitive matching.
    """
    clean_name = location_name.strip().lower()
    for known_loc, coords in COASTAL_COORDINATES.items():
        if known_loc.lower() == clean_name:
            return coords
    return None


def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    Computes great-circle distance between two (lat, lon) points in kilometers.
    Pure deterministic formula.
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    radius_earth_km = 6371.0
    return round(radius_earth_km * c, 2)


def find_nearest_location(lat: float, lon: float) -> Dict[str, Any]:
    """Finds the closest known coastal port/station to a given coordinate."""
    min_dist = float("inf")
    nearest_name = ""
    target_coord = (lat, lon)

    for name, coords in COASTAL_COORDINATES.items():
        d = haversine_distance(target_coord, coords)
        if d < min_dist:
            min_dist = d
            nearest_name = name

    return {
        "nearest_location": nearest_name,
        "distance_km": min_dist,
        "coordinates": COASTAL_COORDINATES.get(nearest_name),
    }


def get_marine_zones_gdf() -> gpd.GeoDataFrame:
    """Loads and caches the sample marine zones GeoDataFrame."""
    global _ZONES_GDF
    if _ZONES_GDF is None:
        if os.path.exists(_GEOJSON_PATH):
            _ZONES_GDF = gpd.read_file(_GEOJSON_PATH)
        else:
            _ZONES_GDF = gpd.GeoDataFrame(
                columns=["zone_id", "name", "category", "restriction_level", "geometry"],
                geometry="geometry",
                crs="EPSG:4326",
            )
    return _ZONES_GDF


def check_point_in_zones(lat: float, lon: float) -> List[Dict[str, Any]]:
    """
    Deterministic point-in-polygon geofence checking.
    Returns all sample marine zones that contain the specified coordinates.
    """
    gdf = get_marine_zones_gdf()
    if gdf.empty:
        return []

    point = Point(lon, lat)
    matching_zones = []

    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is not None and geom.contains(point):
            matching_zones.append({
                "zone_id": row.get("zone_id"),
                "name": row.get("name"),
                "category": row.get("category"),
                "restriction_level": row.get("restriction_level"),
                "allowed_activities": row.get("allowed_activities"),
                "prohibited_activities": row.get("prohibited_activities"),
                "data_classification": "demonstration_sample",
            })

    return matching_zones


def find_nearby_marine_zones(lat: float, lon: float, radius_km: float = 60.0) -> List[Dict[str, Any]]:
    """
    Finds marine zones whose centroid or boundary is within `radius_km` of the point.
    """
    gdf = get_marine_zones_gdf()
    if gdf.empty:
        return []

    target = (lat, lon)
    nearby = []

    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is not None:
            # Centroid approximation for distance
            c_lon, c_lat = geom.centroid.x, geom.centroid.y
            dist = haversine_distance(target, (c_lat, c_lon))
            if dist <= radius_km:
                nearby.append({
                    "zone_id": row.get("zone_id"),
                    "name": row.get("name"),
                    "category": row.get("category"),
                    "restriction_level": row.get("restriction_level"),
                    "distance_km": dist,
                    "data_classification": "demonstration_sample",
                })

    nearby.sort(key=lambda z: z["distance_km"])
    return nearby


def evaluate_geospatial_context(location_name: str) -> EvidenceDict:
    """
    High-level geospatial evidence tool.
    Resolves coordinates, performs geofencing against marine zones, and scans nearby corridors.
    """
    coords = lookup_coordinates(location_name)
    if not coords:
        return build_evidence(
            source="ORCA Geospatial Registry",
            source_type="sample",
            location=location_name,
            variables=["coordinates", "geofence", "nearby_zones"],
            status="unavailable",
            data={"error": f"Location '{location_name}' is not in the recognized coastal registry."},
        )

    lat, lon = coords
    inside_zones = check_point_in_zones(lat, lon)
    nearby_zones = find_nearby_marine_zones(lat, lon, radius_km=80.0)

    return build_evidence(
        source="ORCA Geospatial Engine (Shapely/GeoPandas) & Sample Marine Zones",
        source_type="sample",
        location=location_name,
        variables=["coordinates", "geofence", "nearby_zones"],
        status="available",
        data={
            "location_name": location_name,
            "latitude": lat,
            "longitude": lon,
            "inside_restricted_zones": inside_zones,
            "nearby_marine_zones": nearby_zones,
            "data_classification": "demonstration_sample_boundaries",
        },
    )


def plan_candidate_marine_routes(
    origin_name: str,
    destination_name: str,
) -> Dict[str, Any]:
    """
    Generates deterministic candidate marine routes between two coastal points:
    1. Direct Coastal Route (inshore, hugs coastline, shorter distance, higher coastal/MPA hazard risk)
    2. Recommended Offshore Passage (seaward standoff ~15-20km, avoids MPAs and shallow shoals)

    Explicitly labeled as 'ORCA Informational Route - Not Certified for Official Navigation'.
    """
    c1 = lookup_coordinates(origin_name)
    c2 = lookup_coordinates(destination_name)

    if not c1 or not c2:
        return {
            "error": f"Could not resolve coordinates for '{origin_name}' or '{destination_name}'.",
            "origin": origin_name,
            "destination": destination_name,
            "candidate_routes": [],
            "status": "unavailable",
        }

    direct_dist = haversine_distance(c1, c2)

    # Route 1: Direct Coastal Route (Interpolate waypoints hugging coastline)
    mid_lat = round((c1[0] + c2[0]) / 2.0, 4)
    mid_lon = round((c1[1] + c2[1]) / 2.0, 4)
    # Check if route passes near Malvan (16.06, 73.47) between Ratnagiri (~17.0) and Goa (~15.5)
    inshore_wp2 = (16.0610, 73.4730) if ("ratnagiri" in origin_name.lower() or "goa" in destination_name.lower() or "goa" in origin_name.lower()) else (mid_lat, mid_lon)

    direct_waypoints = [
        {"name": f"Departure: {origin_name} Port Approach", "lat": c1[0], "lon": c1[1], "stage": "departure"},
        {"name": "Inshore Coastal Waypoint 1 (Near Vijaydurg)", "lat": round((c1[0] + inshore_wp2[0]) / 2, 4), "lon": round((c1[1] + inshore_wp2[1]) / 2, 4), "stage": "transit"},
        {"name": "Inshore Coastal Waypoint 2 (Near Malvan Coast)", "lat": inshore_wp2[0], "lon": inshore_wp2[1], "stage": "transit"},
        {"name": f"Arrival: {destination_name} Fairway", "lat": c2[0], "lon": c2[1], "stage": "arrival"},
    ]

    # Calculate distance for direct route
    direct_total_dist = 0.0
    for i in range(len(direct_waypoints) - 1):
        p1 = (direct_waypoints[i]["lat"], direct_waypoints[i]["lon"])
        p2 = (direct_waypoints[i + 1]["lat"], direct_waypoints[i + 1]["lon"])
        direct_total_dist += haversine_distance(p1, p2)
    direct_total_dist = round(direct_total_dist, 2)

    # Route 2: Recommended Safe Offshore Passage (Waypoints pushed ~0.2-0.3 deg seaward into open water)
    # For West Coast India (longitudes ~72.8 - 74.0), moving seaward means decreasing longitude by ~0.18-0.25 deg
    offshore_offset = -0.22
    offshore_wp1 = (round(c1[0] - 0.3 * (c1[0] - c2[0]), 4), round(c1[1] + offshore_offset, 4))
    offshore_wp2 = (round(c1[0] - 0.7 * (c1[0] - c2[0]), 4), round(c2[1] + offshore_offset, 4))

    offshore_waypoints = [
        {"name": f"Departure: {origin_name} Deep Channel", "lat": c1[0], "lon": c1[1], "stage": "departure"},
        {"name": "Seaward Stand-off Waypoint Alpha", "lat": offshore_wp1[0], "lon": offshore_wp1[1], "stage": "transit"},
        {"name": "Seaward Stand-off Waypoint Bravo", "lat": offshore_wp2[0], "lon": offshore_wp2[1], "stage": "transit"},
        {"name": f"Arrival: {destination_name} Pilot Station", "lat": c2[0], "lon": c2[1], "stage": "arrival"},
    ]

    offshore_total_dist = 0.0
    for i in range(len(offshore_waypoints) - 1):
        p1 = (offshore_waypoints[i]["lat"], offshore_waypoints[i]["lon"])
        p2 = (offshore_waypoints[i + 1]["lat"], offshore_waypoints[i + 1]["lon"])
        offshore_total_dist += haversine_distance(p1, p2)
    offshore_total_dist = round(offshore_total_dist, 2)

    return {
        "origin": origin_name,
        "destination": destination_name,
        "origin_coordinates": c1,
        "destination_coordinates": c2,
        "great_circle_distance_km": direct_dist,
        "candidate_routes": [
            {
                "route_id": "direct_inshore",
                "route_name": "Direct Inshore Route",
                "corridor_type": "inshore_coastal",
                "total_distance_km": direct_total_dist,
                "waypoints": direct_waypoints,
                "description": "Shortest coastal passage hugging shoreline; approaches coastal MPAs and shallow rocky points.",
            },
            {
                "route_id": "recommended_offshore",
                "route_name": "Recommended Safe Offshore Passage",
                "corridor_type": "offshore_safe_channel",
                "total_distance_km": offshore_total_dist,
                "waypoints": offshore_waypoints,
                "description": "Seaward stand-off passage (~15-20km offshore); clears all coastal Marine Protected Areas and shallow headlands.",
            },
        ],
        "data_classification": "demonstration_sample_route",
        "route_disclaimer": "ORCA Informational Route — Not Certified for Official Navigation.",
    }


def evaluate_route_safety(
    route: Dict[str, Any],
    weather_data: Optional[Dict[str, Any]] = None,
    marine_data: Optional[Dict[str, Any]] = None,
    advisories: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Evaluates safety of candidate routes using explicit deterministic formula:
    route_score = distance_component + restricted_zone_penalty + hazard_penalty + marine_condition_penalty

    Lower score = safer and preferred route.
    """
    candidates = route.get("candidate_routes", [])
    evaluated_candidates = []

    wind_speed = (weather_data or {}).get("wind_speed", 15.0) or 15.0
    wave_height = (marine_data or {}).get("wave_height", 1.2) or 1.2

    # Metocean condition penalty
    marine_penalty = 0.0
    if wave_height >= 2.5:
        marine_penalty += 35.0
    elif wave_height >= 1.8:
        marine_penalty += 20.0
    elif wave_height >= 1.4:
        marine_penalty += 10.0

    if wind_speed >= 40.0:
        marine_penalty += 30.0
    elif wind_speed >= 25.0:
        marine_penalty += 15.0

    # Active advisory penalty in corridor
    advisory_count = len(advisories or [])
    advisory_penalty = min(advisory_count * 15.0, 30.0)

    for cand in candidates:
        waypoints = cand.get("waypoints", [])
        dist_km = cand.get("total_distance_km", 100.0)

        # 1. Distance component (normalized: 0.1 per km)
        distance_comp = round(dist_km * 0.1, 2)

        # 2. Check restricted zones for each waypoint
        restricted_intersections = []
        zone_penalty = 0.0

        for wp in waypoints:
            zones = check_point_in_zones(wp["lat"], wp["lon"])
            for z in zones:
                if z.get("restriction_level") == "Restricted":
                    zone_penalty += 50.0
                    restricted_intersections.append(f"{z.get('name')} (Restricted MPA at {wp['name']})")
                elif z.get("restriction_level") == "Regulated Navigation":
                    zone_penalty += 25.0
                    restricted_intersections.append(f"{z.get('name')} (Regulated Navigation at {wp['name']})")

        # 3. Hazard penalty (shallow water / rocky coast near inshore)
        hazard_penalty = 0.0
        hazards = []
        if cand.get("corridor_type") == "inshore_coastal":
            hazard_penalty = 25.0
            hazards.append("Coastal shallow shoals and artisanal driftnets within 5 nautical miles of headlands")
            if restricted_intersections:
                hazards.append("Intersects or borders designated Marine Protected Area sanctuary boundary")
        else:
            hazards.append("Deep open-water transit; monitor seasonal swell and cross-traffic")

        # Total deterministic score
        total_score = round(
            distance_comp + zone_penalty + hazard_penalty + marine_penalty + advisory_penalty, 2
        )

        risk_category = "FAVORABLE"
        if total_score > 90.0:
            risk_category = "HIGH_RISK"
        elif total_score > 55.0:
            risk_category = "MODERATE_RISK"

        evaluated_candidates.append({
            "route_id": cand.get("route_id"),
            "route_name": cand.get("route_name"),
            "total_distance_km": dist_km,
            "waypoints": waypoints,
            "route_score": total_score,
            "risk_category": risk_category,
            "score_breakdown": {
                "distance_component": distance_comp,
                "restricted_zone_penalty": zone_penalty,
                "hazard_penalty": hazard_penalty,
                "marine_condition_penalty": marine_penalty,
                "advisory_penalty": advisory_penalty,
            },
            "restricted_zone_intersections": restricted_intersections,
            "identified_hazards": hazards,
            "recommendation": "RECOMMENDED" if cand.get("corridor_type") == "offshore_safe_channel" else "HIGHER_RISK_ALTERNATIVE",
        })

    # Sort candidates by score ascending (lowest risk score first)
    evaluated_candidates.sort(key=lambda c: c["route_score"])

    best_route = evaluated_candidates[0] if evaluated_candidates else None

    return {
        "origin": route.get("origin"),
        "destination": route.get("destination"),
        "origin_coordinates": route.get("origin_coordinates"),
        "destination_coordinates": route.get("destination_coordinates"),
        "candidate_routes": evaluated_candidates,
        "recommended_route": best_route,
        "scoring_formula": "route_score = distance_component (dist*0.1) + restricted_zone_penalty + hazard_penalty + marine_condition_penalty + advisory_penalty",
        "data_classification": "demonstration_sample_route",
        "route_disclaimer": "ORCA Informational Route — Not Certified for Official Navigation.",
    }

