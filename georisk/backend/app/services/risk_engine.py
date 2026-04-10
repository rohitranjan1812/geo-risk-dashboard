import logging
import time
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.models.database import sqlite_session
from app.models.schemas import RiskScorecard, HazardScore
from app.scrapers.usgs_seismic import estimate_pga_at_point
from app.scrapers.fema_flood import determine_flood_zone
from app.scrapers.noaa_hurricane import estimate_hurricane_risk

logger = logging.getLogger(__name__)

SEISMIC_WEIGHT = 0.35
FLOOD_WEIGHT = 0.35
WIND_WEIGHT = 0.30

# In-memory TTL cache for USGS PGA lookups — avoids N+1 network calls.
_pga_cache: dict[str, tuple[float, float]] = {}  # key -> (pga, timestamp)
_PGA_CACHE_TTL = 3600  # 1 hour

CONSTRUCTION_MODIFIERS = {
    "Wood Frame": 1.3,
    "Masonry": 1.1,
    "Concrete Tilt-Up": 1.0,
    "Reinforced Concrete": 0.8,
    "Steel Frame": 0.7,
    "Steel": 0.7,
    "Unknown": 1.0,
}

def _fetch_usgs_pgauh(lat: float, lon: float) -> tuple[float | None, str]:
    """
    Fetch point PGA (uniform hazard) from USGS DesignMaps web service.
    Returns (pga, source_string). pga is None on failure.
    """
    url = settings.USGS_DESIGNMAPS_API.rstrip("/") + "/uniform-hazard.json"
    params = {
        "latitude": lat,
        "longitude": lon,
        "referenceDocument": settings.USGS_UNIFORM_HAZARD_REFERENCE_DOCUMENT,
        "siteClass": settings.USGS_UNIFORM_HAZARD_SITE_CLASS,
    }
    try:
        resp = httpx.get(url, params=params, timeout=5.0, follow_redirects=True)
        resp.raise_for_status()
        payload = resp.json()
        pga = payload.get("response", {}).get("data", {}).get("pgauh")
        if isinstance(pga, (int, float)):
            return float(pga), f"USGS DesignMaps ({settings.USGS_UNIFORM_HAZARD_REFERENCE_DOCUMENT})"
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.debug("USGS pgauh fetch failed: %s", e)
    return None, "USGS simplified zones"


def compute_seismic_score(lat: float, lon: float, construction: str = "Unknown") -> HazardScore:
    pga = None
    source = "USGS simplified zones"

    # Cache per (lat,lon) rounded to 4 decimals to avoid repeated network calls.
    lat_key = round(lat, 4)
    lon_key = round(lon, 4)
    cache_key = f"{lat_key},{lon_key}"

    # Check in-memory TTL cache first (fast path for N+1 scoring loops).
    cached_entry = _pga_cache.get(cache_key)
    if cached_entry and (time.monotonic() - cached_entry[1]) < _PGA_CACHE_TTL:
        pga = cached_entry[0]
        source = "USGS DesignMaps (cached)"

    # Fall back to DB cache.
    if pga is None:
        with sqlite_session() as conn:
            row = conn.execute(
                """
                SELECT raw_data, source
                FROM hazard_data
                WHERE property_id IS NULL AND peril = 'seismic_pga' AND raw_data LIKE ?
                ORDER BY queried_at DESC
                LIMIT 1
                """,
                (f"%\"key\": \"{cache_key}\"%",),
            ).fetchone()
            if row:
                try:
                    import json
                    data = json.loads(row["raw_data"])
                    cached = data.get("pga")
                    if isinstance(cached, (int, float)):
                        pga = float(cached)
                        source = row["source"] or source
                        _pga_cache[cache_key] = (pga, time.monotonic())
                except (KeyError, ValueError, TypeError):
                    pass

    if pga is None:
        fetched, fetched_source = _fetch_usgs_pgauh(lat, lon)
        if fetched is not None:
            pga = fetched
            source = fetched_source
            _pga_cache[cache_key] = (pga, time.monotonic())
            with sqlite_session() as conn:
                import json
                conn.execute(
                    """
                    INSERT INTO hazard_data (property_id, peril, score, raw_data, source)
                    VALUES (NULL, 'seismic_pga', NULL, ?, ?)
                    """,
                    (
                        json.dumps({"key": cache_key, "latitude": lat, "longitude": lon, "pga": pga}),
                        source,
                    ),
                )

    if pga is None:
        pga = estimate_pga_at_point(lat, lon)

    base_score = min(100, pga * 140)

    modifier = CONSTRUCTION_MODIFIERS.get(construction, 1.0)
    adjusted = min(100, base_score * modifier)

    if adjusted < 10:
        desc = "Minimal seismic hazard"
    elif adjusted < 30:
        desc = "Low seismic hazard"
    elif adjusted < 50:
        desc = "Moderate seismic hazard"
    elif adjusted < 70:
        desc = "High seismic hazard"
    else:
        desc = "Very high seismic hazard"

    return HazardScore(
        peril="seismic",
        score=round(adjusted, 1),
        raw_value=pga,
        unit="g (PGA)",
        source=source,
        description=desc,
    )


def compute_flood_score(lat: float, lon: float) -> HazardScore:
    flood_info = determine_flood_zone(lat, lon)

    zone_scores = {
        "V": 95, "VE": 95,
        "A": 80, "AE": 85, "AH": 75, "AO": 70,
        "B": 35, "X": 15,
        "C": 10, "D": 40,
    }

    zone = flood_info["flood_zone"]
    score = zone_scores.get(zone, 15)

    return HazardScore(
        peril="flood",
        score=float(score),
        raw_value=None,
        unit=f"Zone {zone}",
        source=flood_info["source"],
        description=flood_info["zone_description"],
    )


def compute_wind_score(lat: float, lon: float) -> HazardScore:
    hurricane_info = estimate_hurricane_risk(lat, lon)

    wind_prob = hurricane_info["max_wind_prob"]
    score = min(100, wind_prob * 1.2)

    if score < 10:
        desc = "Minimal hurricane/wind hazard"
    elif score < 30:
        desc = "Low wind hazard"
    elif score < 50:
        desc = "Moderate wind hazard - occasional tropical storm exposure"
    elif score < 70:
        desc = "High wind hazard - significant hurricane exposure"
    else:
        desc = "Very high wind hazard - major hurricane corridor"

    return HazardScore(
        peril="wind",
        score=round(score, 1),
        raw_value=wind_prob,
        unit="% probability",
        source=hurricane_info["source"],
        description=desc,
    )


def compute_composite(seismic: float, flood: float, wind: float) -> tuple[float, str]:
    composite = (
        seismic * SEISMIC_WEIGHT
        + flood * FLOOD_WEIGHT
        + wind * WIND_WEIGHT
    )
    composite = round(composite, 1)

    if composite < 20:
        tier = "Low"
    elif composite < 40:
        tier = "Moderate"
    elif composite < 60:
        tier = "High"
    elif composite < 80:
        tier = "Very High"
    else:
        tier = "Extreme"

    return composite, tier


def score_property(prop: dict) -> RiskScorecard:
    lat = prop["latitude"]
    lon = prop["longitude"]
    construction = prop.get("construction_type", "Unknown")

    seismic = compute_seismic_score(lat, lon, construction)
    flood = compute_flood_score(lat, lon)
    wind = compute_wind_score(lat, lon)

    composite, tier = compute_composite(seismic.score, flood.score, wind.score)

    return RiskScorecard(
        property_id=prop.get("id", 0),
        latitude=lat,
        longitude=lon,
        address=prop.get("address"),
        seismic=seismic,
        flood=flood,
        wind=wind,
        composite_score=composite,
        risk_tier=tier,
        scored_at=datetime.now(timezone.utc),
    )
