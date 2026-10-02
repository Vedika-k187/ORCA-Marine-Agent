"""
ORCA Interactive Marine Map Visualizer
Generates interactive Folium marine maps displaying target ports, sample marine zones,
geofenced corridors, and navigational route clearance.
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple
import folium
from folium import plugins

from tools.geospatial_tools import lookup_coordinates, haversine_distance, _GEOJSON_PATH

ZONE_STYLE_MAP = {
    "Marine Protected Area (MPA)": {"fillColor": "#E53935", "color": "#B71C1C", "weight": 2, "fillOpacity": 0.35},
    "Port Navigation & Anchorage Limit": {"fillColor": "#FB8C00", "color": "#E65100", "weight": 2, "fillOpacity": 0.35},
    "Designated Artisanal Fishing Zone": {"fillColor": "#00897B", "color": "#004D40", "weight": 2, "fillOpacity": 0.35},
    "Offshore Oil & Energy Exclusion Zone": {"fillColor": "#D81B60", "color": "#880E4F", "weight": 2, "fillOpacity": 0.40},
    "Coastal Tourism & Regulated Zone": {"fillColor": "#1E88E5", "color": "#0D47A1", "weight": 2, "fillOpacity": 0.35},
}


def create_marine_map(
    target_locations: List[str],
    workflow_result: Optional[Dict[str, Any]] = None,
    default_center: Tuple[float, float] = (16.9902, 73.3000),
    zoom_start: int = 8,
) -> folium.Map:
    """
    Creates an interactive Folium marine map centered on the active target location(s).
    Renders sample marine zones, restricted corridors, and navigational routes.
    """
    # Determine map center
    coords_list: List[Tuple[str, Tuple[float, float]]] = []
    for loc in target_locations:
        c = lookup_coordinates(loc)
        if c:
            coords_list.append((loc, c))

    if coords_list:
        center_lat = sum(c[1][0] for c in coords_list) / len(coords_list)
        center_lon = sum(c[1][1] for c in coords_list) / len(coords_list)
        map_center = (center_lat, center_lon)
        # Adjust zoom if multiple distant locations
        zoom = 7 if len(coords_list) >= 2 else 9
    else:
        map_center = default_center
        zoom = zoom_start

    # Initialize Folium Map with OpenStreetMap
    m = folium.Map(
        location=map_center,
        zoom_start=zoom,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    # Add Esri Ocean / Nautical basemap layer for realistic marine backdrop
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, Garmin, GEBCO, NOAA NGDC, and other contributors",
        name="Esri Ocean Basemap",
        overlay=False,
        control=True,
    ).add_to(m)

    # 1. Overlay Sample Marine Zones from GeoJSON
    if os.path.exists(_GEOJSON_PATH):
        try:
            with open(_GEOJSON_PATH, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            def style_function(feature):
                category = feature.get("properties", {}).get("category", "")
                return ZONE_STYLE_MAP.get(
                    category,
                    {"fillColor": "#3949AB", "color": "#1A237E", "weight": 2, "fillOpacity": 0.3},
                )

            def highlight_function(feature):
                return {"weight": 3, "color": "#FFD600", "fillOpacity": 0.55}

            zone_layer = folium.GeoJson(
                geojson_data,
                name="Marine Zones (Sample Fixtures)",
                style_function=style_function,
                highlight_function=highlight_function,
                tooltip=folium.GeoJsonTooltip(
                    fields=["name", "category", "restriction_level"],
                    aliases=["Zone:", "Category:", "Status:"],
                    localize=True,
                ),
                popup=folium.GeoJsonPopup(
                    fields=["name", "category", "restriction_level", "allowed_activities", "prohibited_activities", "data_classification"],
                    aliases=["Zone Name:", "Category:", "Restriction Level:", "Allowed Activities:", "Prohibited:", "Classification:"],
                    labels=True,
                ),
            )
            zone_layer.add_to(m)
        except Exception:
            pass

    # 2. Add Markers for Target Location(s)
    weather_payload = (workflow_result or {}).get("weather_data") or {}
    weather_inner = weather_payload.get("weather_data") or {}
    marine_inner = weather_payload.get("marine_data") or (workflow_result or {}).get("ocean_data", {}).get("marine_telemetry") or {}
    pfz_data = (workflow_result or {}).get("pfz_data") or {}

    for loc_name, (lat, lon) in coords_list:
        wind = weather_inner.get("wind_speed", "N/A")
        waves = marine_inner.get("wave_height", "N/A")
        temp = weather_inner.get("temperature", "N/A")

        popup_html = f"""
        <div style="font-family: sans-serif; font-size: 13px; min-width: 180px;">
            <b style="color: #007791; font-size: 14px;">📍 {loc_name}</b><br>
            <hr style="margin: 4px 0;">
            <b>Coordinates:</b> {lat:.4f}°N, {lon:.4f}°E<br>
            <b>Wind (LIVE):</b> {wind} km/h<br>
            <b>Waves (LIVE):</b> {waves} m<br>
            <b>Air Temp (LIVE):</b> {temp}°C<br>
        </div>
        """

        folium.Marker(
            location=(lat, lon),
            tooltip=f"{loc_name} (Active Target)",
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color="blue", icon="anchor", prefix="fa"),
        ).add_to(m)

    # 3. If Demonstration PFZ suitability was calculated, add PFZ demonstration circle
    if pfz_data and coords_list:
        p_lat, p_lon = coords_list[0][1]
        score = pfz_data.get("composite_score", 0)
        cat = pfz_data.get("suitability_category", "Demonstration Zone")

        # Offset slightly offshore (westwards by ~0.15 deg)
        pfz_lat = p_lat
        pfz_lon = p_lon - 0.15

        pfz_popup = f"""
        <div style="font-family: sans-serif; font-size: 13px; min-width: 200px;">
            <b style="color: #2E7D32;">🐟 ORCA Demonstration Fishing Zone</b><br>
            <hr style="margin: 4px 0;">
            <b>Location:</b> Off {coords_list[0][0]}<br>
            <b>Suitability Index:</b> {score} / 100<br>
            <b>Category:</b> {cat}<br>
            <small style="color: #666;"><i>Demonstration model only — not official INCOIS PFZ.</i></small>
        </div>
        """

        folium.CircleMarker(
            location=(pfz_lat, pfz_lon),
            radius=16,
            color="#2E7D32",
            fill=True,
            fill_color="#4CAF50",
            fill_opacity=0.6,
            tooltip=f"Demonstration PFZ: {cat} ({score}/100)",
            popup=folium.Popup(pfz_popup, max_width=250),
        ).add_to(m)

    # 4. If Route Planning data with candidate routes is present, render routes & waypoints
    route_data = (workflow_result or {}).get("route_data") or {}
    candidate_routes = route_data.get("candidate_routes", [])

    if candidate_routes:
        route_group = folium.FeatureGroup(name="ORCA Informational Routes", show=True).add_to(m)

        for cand in candidate_routes:
            wps = cand.get("waypoints", [])
            if len(wps) >= 2:
                pts = [(wp["lat"], wp["lon"]) for wp in wps]
                r_name = cand.get("route_name", "Candidate Route")
                r_dist = cand.get("total_distance_km", "N/A")
                r_score = cand.get("route_score", "N/A")
                r_risk = cand.get("risk_category", "FAVORABLE")
                is_rec = cand.get("route_id") == "recommended_offshore"

                line_color = "#10B981" if is_rec else "#F59E0B"
                dash = None if is_rec else "6, 8"
                weight = 4 if is_rec else 3

                intersections = cand.get("restricted_zone_intersections", [])
                inter_str = f"<br><b style='color:#DC2626;'>Zone Crossings:</b> {', '.join(intersections)}" if intersections else "<br><span style='color:#059669;'>Zero restricted zone crossings.</span>"

                popup_content = f"""
                <div style="font-family: sans-serif; font-size: 13px; min-width: 220px;">
                    <b style="color: {line_color}; font-size: 14px;">🚢 {r_name}</b><br>
                    <span style="font-size: 11px; color: #64748B;">ORCA INFORMATIONAL ROUTE (Not certified for navigation)</span><br>
                    <hr style="margin: 4px 0;">
                    <b>Distance:</b> {r_dist} km<br>
                    <b>Safety Score:</b> {r_score} ({r_risk})<br>
                    {inter_str}
                </div>
                """

                folium.PolyLine(
                    locations=pts,
                    color=line_color,
                    weight=weight,
                    dash_array=dash,
                    tooltip=f"{r_name}: {r_dist} km (Score: {r_score})",
                    popup=folium.Popup(popup_content, max_width=280),
                ).add_to(route_group)

                # Render intermediate waypoints for the recommended route
                if is_rec:
                    for i, wp in enumerate(wps):
                        is_terminal = (i == 0 or i == len(wps) - 1)
                        if not is_terminal:
                            folium.CircleMarker(
                                location=(wp["lat"], wp["lon"]),
                                radius=5,
                                color="#10B981",
                                fill=True,
                                fill_color="#FFFFFF",
                                fill_opacity=0.9,
                                tooltip=f"Waypoint {i}: {wp.get('name')}",
                            ).add_to(route_group)

    # 5. If Comparison or corridor with >= 2 points (and not already route-planned), draw baseline geodesic line
    elif len(coords_list) >= 2:
        points = [c[1] for c in coords_list]
        dist = haversine_distance(coords_list[0][1], coords_list[1][1])

        line_popup = f"""
        <div style="font-family: sans-serif; font-size: 13px;">
            <b>Geodesic Corridor:</b> {coords_list[0][0]} ↔ {coords_list[1][0]}<br>
            <b>Great-Circle Distance:</b> {dist:.2f} km
        </div>
        """

        folium.PolyLine(
            locations=points,
            color="#3F51B5",
            weight=3,
            dash_array="6, 8",
            tooltip=f"Transit corridor: {dist:.1f} km",
            popup=folium.Popup(line_popup, max_width=200),
        ).add_to(m)

    # 5. Add Layer Control & MiniMap plugin
    folium.LayerControl(position="topright").add_to(m)
    plugins.MiniMap(toggle_display=True, position="bottomright").add_to(m)

    return m
