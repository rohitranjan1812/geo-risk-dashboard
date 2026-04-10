import json
import logging

import httpx

from app.config import settings
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

FLOOD_ZONE_DESCRIPTIONS = {
    "A": ("Zone A", "High risk - 1% annual chance flood (100-year)", True),
    "AE": ("Zone AE", "High risk with BFE determined", True),
    "AH": ("Zone AH", "High risk - shallow flooding 1-3ft", True),
    "AO": ("Zone AO", "High risk - sheet flow 1-3ft", True),
    "V": ("Zone V", "High risk - coastal with velocity hazard", True),
    "VE": ("Zone VE", "High risk - coastal with BFE and velocity", True),
    "X": ("Zone X", "Moderate to low risk - 0.2% annual chance", False),
    "B": ("Zone B (legacy)", "Moderate risk - shaded Zone X", False),
    "C": ("Zone C (legacy)", "Minimal risk - unshaded Zone X", False),
    "D": ("Zone D", "Undetermined risk - possible flood hazard", False),
}


class FEMAFloodScraper(BaseScraper):
    SOURCE_NAME = "fema_flood"
    TIMEOUT = 120.0
    RATE_LIMIT_DELAY = 2.0

    async def scrape(self) -> dict:
        all_features = []

        sample_areas = [
            {"xmin": -90.5, "ymin": 29.5, "xmax": -89.5, "ymax": 30.5, "name": "New Orleans"},
            {"xmin": -80.5, "ymin": 25.5, "xmax": -79.5, "ymax": 26.5, "name": "Miami"},
            {"xmin": -96.0, "ymin": 29.0, "xmax": -95.0, "ymax": 30.0, "name": "Houston"},
            {"xmin": -80.0, "ymin": 32.5, "xmax": -79.5, "ymax": 33.0, "name": "Charleston"},
        ]

        layer_id = 28

        for area in sample_areas:
            try:
                result_offset = 0
                page_size = 200
                while True:
                    params = {
                        "where": "1=1",
                        "geometry": json.dumps({
                            "xmin": area["xmin"], "ymin": area["ymin"],
                            "xmax": area["xmax"], "ymax": area["ymax"],
                            "spatialReference": {"wkid": 4326},
                        }),
                        "geometryType": "esriGeometryEnvelope",
                        "spatialRel": "esriSpatialRelIntersects",
                        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE",
                        "returnGeometry": "true",
                        "outSR": "4326",
                        "f": "geojson",
                        "resultRecordCount": page_size,
                        "resultOffset": result_offset,
                    }

                    url = f"{settings.FEMA_NFHL_API}/{layer_id}/query"
                    response = await self.fetch_with_retry(url, params=params)
                    data = response.json()

                    features = data.get("features", [])
                    for f in features:
                        f["properties"]["query_area"] = area["name"]
                    all_features.extend(features)

                    # Stop paginating when we get fewer than page_size (last page).
                    if len(features) < page_size:
                        break
                    result_offset += page_size

                logger.info("FEMA flood: %s returned %d features", area["name"],
                            sum(1 for ft in all_features if ft["properties"].get("query_area") == area["name"]))

            except (httpx.HTTPError, OSError, ValueError, KeyError) as e:
                logger.warning("FEMA flood query failed for %s: %s", area['name'], e)

        geojson = {"type": "FeatureCollection", "features": all_features}
        filepath = self.save_geojson(geojson, "fema_flood_zones_scraped.geojson")

        return {
            "status": "success",
            "source": self.SOURCE_NAME,
            "records": len(all_features),
            "file_path": str(filepath),
        }


US_FLOOD_ZONES = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"zone": "AE", "description": "High risk - coastal/riverine with BFE", "sfha": True, "risk_level": 5, "color": "#1565c0"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-90.3, 30.1], [-89.8, 30.1], [-89.8, 29.8], [-90.3, 29.8], [-90.3, 30.1]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"zone": "VE", "description": "High risk - coastal velocity zone", "sfha": True, "risk_level": 5, "color": "#0d47a1"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-80.3, 25.9], [-80.1, 25.9], [-80.1, 25.7], [-80.3, 25.7], [-80.3, 25.9]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"zone": "A", "description": "High risk - 100-year floodplain", "sfha": True, "risk_level": 4, "color": "#1976d2"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-95.8, 30.0], [-95.0, 30.0], [-95.0, 29.5], [-95.8, 29.5], [-95.8, 30.0]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"zone": "AE", "description": "High risk - riverine with BFE", "sfha": True, "risk_level": 4, "color": "#1565c0"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-80.0, 33.0], [-79.7, 33.0], [-79.7, 32.7], [-80.0, 32.7], [-80.0, 33.0]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"zone": "X", "description": "Moderate to low risk - 500-year", "sfha": False, "risk_level": 2, "color": "#90caf9"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-122.5, 37.9], [-122.3, 37.9], [-122.3, 37.7], [-122.5, 37.7], [-122.5, 37.9]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"zone": "A", "description": "High risk - 100-year (Mississippi corridor)", "sfha": True, "risk_level": 4, "color": "#1976d2"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-91.0, 36.0], [-89.5, 36.0], [-89.5, 34.5], [-91.0, 34.5], [-91.0, 36.0]]],
            },
        },
    ],
}


def get_flood_zones_geojson() -> dict:
    filepath = settings.CATALOG_DIR / "flood_zones.geojson"
    if filepath.exists():
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(US_FLOOD_ZONES, f)
    return US_FLOOD_ZONES


_flood_geom_cache = None
_flood_scraped_geom_cache = None


def determine_flood_zone(lat: float, lon: float) -> dict:
    from shapely.geometry import Point, shape

    global _flood_geom_cache, _flood_scraped_geom_cache

    point = Point(lon, lat)

    # Build cached geometry lists on first call.
    scraped_path = settings.CATALOG_DIR / "fema_flood_zones_scraped.geojson"
    if _flood_scraped_geom_cache is None and scraped_path.exists():
        try:
            with open(scraped_path, encoding="utf-8") as f:
                scraped = json.load(f)
            _flood_scraped_geom_cache = []
            for feature in scraped.get("features", []):
                try:
                    _flood_scraped_geom_cache.append(
                        (shape(feature["geometry"]), feature.get("properties", {}))
                    )
                except (ValueError, TypeError):
                    continue
        except (OSError, json.JSONDecodeError):
            _flood_scraped_geom_cache = []

    if _flood_scraped_geom_cache:
        for geom, props in _flood_scraped_geom_cache:
            try:
                if geom.contains(point):
                    zone = props.get("FLD_ZONE", "X")
                    info = FLOOD_ZONE_DESCRIPTIONS.get(zone, ("Unknown", "Unknown zone", False))
                    return {
                        "flood_zone": zone,
                        "zone_description": info[1],
                        "sfha": info[2],
                        "bfe": props.get("STATIC_BFE"),
                        "source": "FEMA NFHL (scraped)",
                    }
            except (ValueError, TypeError):
                continue

    if _flood_geom_cache is None:
        _flood_geom_cache = []
        for feature in US_FLOOD_ZONES["features"]:
            try:
                _flood_geom_cache.append(
                    (shape(feature["geometry"]), feature["properties"])
                )
            except (ValueError, TypeError):
                continue

    for polygon, props in _flood_geom_cache:
        if polygon.contains(point):
            return {
                "flood_zone": props["zone"],
                "zone_description": props["description"],
                "sfha": props["sfha"],
                "bfe": None,
                "source": "Simplified hazard zones",
            }

    return {
        "flood_zone": "X",
        "zone_description": "Minimal flood hazard",
        "sfha": False,
        "bfe": None,
        "source": "Default (outside mapped zones)",
    }
