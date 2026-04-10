import json
import logging

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.scrapers.usgs_seismic import get_seismic_hazard_zones
from app.scrapers.fema_flood import get_flood_zones_geojson
from app.scrapers.noaa_hurricane import get_hurricane_tracks_geojson

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/layers")
async def list_available_layers():
    layers = [
        {
            "id": "earthquakes",
            "name": "Recent Earthquakes",
            "type": "point",
            "source": "usgs_earthquake",
            "file": "earthquakes_recent.geojson",
            "available": (settings.CATALOG_DIR / "earthquakes_recent.geojson").exists(),
        },
        {
            "id": "seismic_zones",
            "name": "Seismic Hazard Zones",
            "type": "polygon",
            "source": "usgs_hazard",
            "file": "seismic_hazard_zones.geojson",
            "available": True,
        },
        {
            "id": "flood_zones",
            "name": "Flood Hazard Zones",
            "type": "polygon",
            "source": "fema_flood",
            "file": "flood_zones.geojson",
            "available": True,
        },
        {
            "id": "hurricane_tracks",
            "name": "Historical Hurricane Tracks",
            "type": "line",
            "source": "noaa_hurricane",
            "file": "hurricane_tracks.geojson",
            "available": True,
        },
    ]
    return layers


@router.get("/layer/{layer_id}")
async def get_layer_geojson(layer_id: str):
    if layer_id == "earthquakes":
        filepath = settings.CATALOG_DIR / "earthquakes_recent.geojson"
        if not filepath.exists():
            return {"type": "FeatureCollection", "features": []}
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)

    if layer_id == "seismic_zones":
        return get_seismic_hazard_zones()

    if layer_id == "flood_zones":
        return get_flood_zones_geojson()

    if layer_id == "hurricane_tracks":
        return get_hurricane_tracks_geojson()

    raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")


@router.get("/properties-geojson")
async def get_properties_geojson():
    from app.models.database import sqlite_session

    with sqlite_session() as conn:
        rows = conn.execute("SELECT * FROM properties").fetchall()

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "id": r["id"],
                "name": r["name"],
                "address": r["address"],
                "tiv": r["tiv"],
                "construction_type": r["construction_type"],
                "occupancy": r["occupancy"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [r["longitude"], r["latitude"]],
            },
        })

    return {"type": "FeatureCollection", "features": features}
