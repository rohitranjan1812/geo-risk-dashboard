import json
import logging
from pathlib import Path

from shapely.geometry import Point, shape, mapping
import geopandas as gpd
import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)


def load_geojson(filename: str) -> dict | None:
    filepath = (settings.CATALOG_DIR / filename).resolve()
    if not filepath.is_relative_to(settings.CATALOG_DIR.resolve()):
        logger.warning("Path traversal attempt blocked: %s", filename)
        return None
    if not filepath.exists():
        return None
    with open(filepath) as f:
        return json.load(f)


def point_in_hazard_zones(lat: float, lon: float, hazard_file: str) -> list[dict]:
    data = load_geojson(hazard_file)
    if not data:
        return []

    point = Point(lon, lat)
    matches = []

    for feature in data.get("features", []):
        try:
            geom = shape(feature["geometry"])
            if geom.contains(point) or geom.distance(point) < 0.01:
                matches.append(feature["properties"])
        except Exception as e:
            logger.debug(f"Geometry check failed: {e}")

    return matches


def compute_nearby_earthquakes(lat: float, lon: float, radius_deg: float = 2.0) -> list[dict]:
    data = load_geojson("earthquakes_recent.geojson")
    if not data:
        return []

    point = Point(lon, lat)
    nearby = []

    for feature in data.get("features", []):
        try:
            coords = feature["geometry"]["coordinates"]
            eq_point = Point(coords[0], coords[1])
            dist = point.distance(eq_point)
            if dist <= radius_deg:
                props = feature["properties"]
                nearby.append({
                    "magnitude": props.get("mag"),
                    "place": props.get("place"),
                    "time": props.get("time"),
                    "distance_deg": round(dist, 3),
                    "depth": coords[2] if len(coords) > 2 else None,
                })
        except Exception:
            continue

    return sorted(nearby, key=lambda x: x.get("distance_deg", 999))[:20]


def batch_intersect(properties: list[dict], hazard_file: str) -> dict[int, list[dict]]:
    data = load_geojson(hazard_file)
    if not data:
        return {}

    hazard_geoms = []
    for feature in data.get("features", []):
        try:
            hazard_geoms.append((shape(feature["geometry"]), feature["properties"]))
        except Exception:
            continue

    results = {}
    for prop in properties:
        point = Point(prop["longitude"], prop["latitude"])
        matches = []
        for geom, props in hazard_geoms:
            try:
                if geom.contains(point):
                    matches.append(props)
            except Exception:
                continue
        results[prop.get("id", 0)] = matches

    return results


def properties_to_geodataframe(properties: list[dict]) -> gpd.GeoDataFrame:
    df = pd.DataFrame(properties)
    geometry = [Point(row["longitude"], row["latitude"]) for _, row in df.iterrows()]
    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")


def hexbin_accumulation(properties: list[dict], resolution: int = 5) -> list[dict]:
    try:
        import h3
    except ImportError:
        logger.warning("h3 not available, skipping hexbin")
        return []

    hex_data = {}
    for prop in properties:
        h3_idx = h3.latlng_to_cell(prop["latitude"], prop["longitude"], resolution)
        if h3_idx not in hex_data:
            hex_data[h3_idx] = {"h3_index": h3_idx, "count": 0, "total_tiv": 0, "properties": []}
        hex_data[h3_idx]["count"] += 1
        hex_data[h3_idx]["total_tiv"] += prop.get("tiv", 0)
        hex_data[h3_idx]["properties"].append(prop.get("id"))

    for h3_idx, data in hex_data.items():
        boundary = h3.cell_to_boundary(h3_idx)
        coords = [[lng, lat] for lat, lng in boundary]
        coords.append(coords[0])
        data["geometry"] = {"type": "Polygon", "coordinates": [coords]}

    return sorted(hex_data.values(), key=lambda x: x["total_tiv"], reverse=True)
