import logging
from datetime import datetime, timezone

from app.models.schemas import RiskScorecard, HazardScore
from app.scrapers.usgs_seismic import estimate_pga_at_point
from app.scrapers.fema_flood import determine_flood_zone
from app.scrapers.noaa_hurricane import estimate_hurricane_risk

logger = logging.getLogger(__name__)

SEISMIC_WEIGHT = 0.35
FLOOD_WEIGHT = 0.35
WIND_WEIGHT = 0.30

CONSTRUCTION_MODIFIERS = {
    "Wood Frame": 1.3,
    "Masonry": 1.1,
    "Concrete Tilt-Up": 1.0,
    "Reinforced Concrete": 0.8,
    "Steel Frame": 0.7,
    "Steel": 0.7,
    "Unknown": 1.0,
}


def compute_seismic_score(lat: float, lon: float, construction: str = "Unknown") -> HazardScore:
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
        source="USGS NSHM",
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
