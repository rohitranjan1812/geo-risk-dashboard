import logging
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.risk_engine import (
    compute_seismic_score, compute_flood_score, compute_wind_score, compute_composite,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class ScenarioInput(BaseModel):
    latitude: float
    longitude: float
    construction_type: str = "Unknown"
    seismic_weight: float = 0.35
    flood_weight: float = 0.35
    wind_weight: float = 0.30
    pga_override: float | None = None
    flood_zone_override: str | None = None
    wind_prob_override: float | None = None


class ScenarioResult(BaseModel):
    base_case: dict
    scenario: dict
    delta: dict


@router.post("/what-if", response_model=ScenarioResult)
async def run_what_if_scenario(inp: ScenarioInput):
    seismic_base = compute_seismic_score(inp.latitude, inp.longitude, inp.construction_type)
    flood_base = compute_flood_score(inp.latitude, inp.longitude)
    wind_base = compute_wind_score(inp.latitude, inp.longitude)
    comp_base, tier_base = compute_composite(seismic_base.score, flood_base.score, wind_base.score)

    seismic_adj = seismic_base.score
    flood_adj = flood_base.score
    wind_adj = wind_base.score

    if inp.pga_override is not None:
        seismic_adj = min(100, inp.pga_override * 140)

    if inp.flood_zone_override:
        zone_scores = {"V": 95, "VE": 95, "A": 80, "AE": 85, "X": 15, "D": 40}
        flood_adj = zone_scores.get(inp.flood_zone_override, flood_base.score)

    if inp.wind_prob_override is not None:
        wind_adj = min(100, inp.wind_prob_override * 1.2)

    total_w = inp.seismic_weight + inp.flood_weight + inp.wind_weight
    norm_s = inp.seismic_weight / total_w
    norm_f = inp.flood_weight / total_w
    norm_w = inp.wind_weight / total_w

    comp_scenario = round(seismic_adj * norm_s + flood_adj * norm_f + wind_adj * norm_w, 1)
    tier_scenario = (
        "Low" if comp_scenario < 20 else
        "Moderate" if comp_scenario < 40 else
        "High" if comp_scenario < 60 else
        "Very High" if comp_scenario < 80 else
        "Extreme"
    )

    return ScenarioResult(
        base_case={
            "seismic": seismic_base.score,
            "flood": flood_base.score,
            "wind": wind_base.score,
            "composite": comp_base,
            "tier": tier_base,
        },
        scenario={
            "seismic": round(seismic_adj, 1),
            "flood": round(flood_adj, 1),
            "wind": round(wind_adj, 1),
            "composite": comp_scenario,
            "tier": tier_scenario,
            "weights": {"seismic": round(norm_s, 2), "flood": round(norm_f, 2), "wind": round(norm_w, 2)},
        },
        delta={
            "seismic": round(seismic_adj - seismic_base.score, 1),
            "flood": round(flood_adj - flood_base.score, 1),
            "wind": round(wind_adj - wind_base.score, 1),
            "composite": round(comp_scenario - comp_base, 1),
        },
    )


@router.get("/compare-properties")
async def compare_properties(ids: str = Query(..., description="Comma-separated property IDs")):
    from app.models.database import sqlite_session
    from app.services.risk_engine import score_property

    prop_ids = [int(x.strip()) for x in ids.split(",")]
    results = []

    with sqlite_session() as conn:
        for pid in prop_ids:
            row = conn.execute("SELECT * FROM properties WHERE id = ?", (pid,)).fetchone()
            if row:
                prop = dict(row)
                scorecard = score_property(prop)
                results.append({
                    "property_id": pid,
                    "name": prop.get("name"),
                    "address": prop.get("address"),
                    "tiv": prop.get("tiv", 0),
                    "seismic": scorecard.seismic.score if scorecard.seismic else 0,
                    "flood": scorecard.flood.score if scorecard.flood else 0,
                    "wind": scorecard.wind.score if scorecard.wind else 0,
                    "composite": scorecard.composite_score,
                    "tier": scorecard.risk_tier,
                })

    return {"properties": results, "count": len(results)}
