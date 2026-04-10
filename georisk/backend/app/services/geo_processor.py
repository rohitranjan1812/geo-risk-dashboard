import json
import logging
from functools import lru_cache

from shapely.geometry import Point, shape
import geopandas as gpd
import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

# In-memory cache for GeoJSON files — loaded once, reused across all requests.
_geojson_cache: dict[str, dict | None] = {}


def load_geojson(filename: str) -> dict | None:
    if filename in _geojson_cache:
        return _geojson_cache[filename]

    filepath = settings.CATALOG_DIR / filename
    if not filepath.exists():
        _geojson_cache[filename] = None
        return None
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    _geojson_cache[filename] = data
    return data


def invalidate_geojson_cache(filename: str | None = None) -> None:
    """Call after a scraper writes new data to force reload on next access."""
    if filename:
        _geojson_cache.pop(filename, None)
    else:
        _geojson_cache.clear()


# Pre-built shapely geometries cache — avoids re-parsing on every call.
_geometry_cache: dict[str, list[tuple]] = {}


def _get_geometries(filename: str) -> list[tuple]:
    """Return [(shapely_geom, properties_dict), ...] for a hazard file, cached."""
    if filename in _geometry_cache:
        return _geometry_cache[filename]

    data = load_geojson(filename)
    if not data:
        return []

    geom_list = []
    for feature in data.get("features", []):
        try:
            geom_list.append((shape(feature["geometry"]), feature.get("properties", {})))
        except (ValueError, TypeError):
            continue

    _geometry_cache[filename] = geom_list
    return geom_list


def point_in_hazard_zones(lat: float, lon: float, hazard_file: str) -> list[dict]:
    geoms = _get_geometries(hazard_file)
    if not geoms:
        return []

    point = Point(lon, lat)
    matches = []

    for geom, props in geoms:
        try:
            if geom.contains(point) or geom.distance(point) < 0.01:
                matches.append(props)
        except (ValueError, TypeError) as e:
            logger.debug("Geometry check failed: %s", e)

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
            # Fast bounding-box pre-filter before expensive distance calc
            if abs(coords[0] - lon) > radius_deg or abs(coords[1] - lat) > radius_deg:
                continue
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
        except (KeyError, TypeError, IndexError):
            continue

    return sorted(nearby, key=lambda x: x.get("distance_deg", 999))[:20]


def batch_intersect(properties: list[dict], hazard_file: str) -> dict[int, list[dict]]:
    geoms = _get_geometries(hazard_file)
    if not geoms:
        return {}

    results = {}
    for prop in properties:
        point = Point(prop["longitude"], prop["latitude"])
        matches = []
        for geom, props in geoms:
            try:
                if geom.contains(point):
                    matches.append(props)
            except (ValueError, TypeError):
                continue
        results[prop.get("id", 0)] = matches

    return results


def properties_to_geodataframe(properties: list[dict]) -> gpd.GeoDataFrame:
    df = pd.DataFrame(properties)
    geometry = gpd.points_from_xy(df["longitude"], df["latitude"])
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
