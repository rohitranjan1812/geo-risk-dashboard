import json
import logging
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class USGSEarthquakeScraper(BaseScraper):
    SOURCE_NAME = "usgs_earthquake"
    RATE_LIMIT_DELAY = 0.5

    async def scrape(self, days_back: int = 30, min_magnitude: float = 2.5) -> dict:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days_back)

        params = {
            "format": "geojson",
            "starttime": start_time.strftime("%Y-%m-%d"),
            "endtime": end_time.strftime("%Y-%m-%d"),
            "minmagnitude": min_magnitude,
            "orderby": "time",
            "limit": 5000,
        }

        response = await self.fetch_with_retry(settings.USGS_EARTHQUAKE_API, params=params)
        data = response.json()

        features = data.get("features", [])
        record_count = len(features)

        filepath = self.save_geojson(data, "earthquakes_recent.geojson")

        significant = [f for f in features if f["properties"].get("mag", 0) >= 5.0]
        if significant:
            self.save_geojson(
                {"type": "FeatureCollection", "features": significant},
                "earthquakes_significant.geojson",
            )

        return {
            "status": "success",
            "source": self.SOURCE_NAME,
            "records": record_count,
            "file_path": str(filepath),
            "time_range": f"{start_time.date()} to {end_time.date()}",
            "significant_count": len(significant),
        }


class USGSHazardZonesScraper(BaseScraper):
    """
    Maintains our locally-bundled seismic hazard zones GeoJSON and updates the data catalog
    so the UI shows `usgs_hazard` as fresh.
    """

    SOURCE_NAME = "usgs_hazard"
    RATE_LIMIT_DELAY = 0.0

    async def scrape(self) -> dict:
        geojson = get_seismic_hazard_zones()
        filepath = self.save_geojson(geojson, "seismic_hazard_zones.geojson")
        records = len(geojson.get("features", []))
        return {
            "status": "success",
            "source": self.SOURCE_NAME,
            "records": records,
            "file_path": str(filepath),
        }


SEISMIC_HAZARD_ZONES = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"zone": "Very High", "pga_range": "0.6g+", "risk_level": 5, "color": "#d32f2f"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-124.5, 40.0], [-119.0, 40.0], [-119.0, 34.0],
                    [-121.0, 34.0], [-124.5, 37.0], [-124.5, 40.0],
                ]],
            },
        },
        {
            "type": "Feature",
            "properties": {"zone": "High", "pga_range": "0.4-0.6g", "risk_level": 4, "color": "#f57c00"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-125.0, 49.0], [-121.0, 49.0], [-121.0, 42.0],
                    [-124.0, 42.0], [-125.0, 46.0], [-125.0, 49.0],
                ]],
            },
        },
        {
            "type": "Feature",
            "properties": {"zone": "Moderate-High", "pga_range": "0.2-0.4g", "risk_level": 3, "color": "#fbc02d"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-92.0, 38.0], [-88.0, 38.0], [-88.0, 34.0],
                    [-92.0, 34.0], [-92.0, 38.0],
                ]],
            },
        },
        {
            "type": "Feature",
            "properties": {"zone": "Moderate", "pga_range": "0.1-0.2g", "risk_level": 2, "color": "#1976d2"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-83.0, 37.0], [-79.0, 37.0], [-79.0, 33.0],
                    [-83.0, 33.0], [-83.0, 37.0],
                ]],
            },
        },
        {
            "type": "Feature",
            "properties": {"zone": "High (Alaska)", "pga_range": "0.4g+", "risk_level": 4, "color": "#f57c00"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-165.0, 64.0], [-145.0, 64.0], [-145.0, 55.0],
                    [-165.0, 55.0], [-165.0, 64.0],
                ]],
            },
        },
    ],
}


def get_seismic_hazard_zones() -> dict:
    filepath = settings.CATALOG_DIR / "seismic_hazard_zones.geojson"
    if not filepath.exists():
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(SEISMIC_HAZARD_ZONES, f)
    else:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    return SEISMIC_HAZARD_ZONES


def estimate_pga_at_point(lat: float, lon: float) -> float:
    from shapely.geometry import Point, shape

    # Build pre-parsed geometry list once and cache it.
    global _seismic_geom_cache
    if "_seismic_geom_cache" not in globals() or _seismic_geom_cache is None:
        _seismic_geom_cache = []
        for feature in SEISMIC_HAZARD_ZONES["features"]:
            _seismic_geom_cache.append(
                (shape(feature["geometry"]), feature["properties"]["risk_level"])
            )

    point = Point(lon, lat)
    pga_map = {5: 0.7, 4: 0.5, 3: 0.3, 2: 0.15, 1: 0.05}
    for polygon, level in _seismic_geom_cache:
        if polygon.contains(point):
            return pga_map.get(level, 0.05)
    return 0.05

_seismic_geom_cache = None
