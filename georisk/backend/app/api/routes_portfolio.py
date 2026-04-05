import csv
import io
import json
import logging
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File

import duckdb

from app.config import settings
from app.models.database import sqlite_session, get_duckdb_conn
from app.models.schemas import PortfolioSummary, PortfolioPropertyResult
from app.services.risk_engine import score_property
from app.services.geocoder import geocode_address

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_portfolio(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    portfolio_id = str(uuid.uuid4())[:8]
    properties = []
    errors = []

    for i, row in enumerate(reader):
        try:
            lat = float(row.get("latitude", 0))
            lon = float(row.get("longitude", 0))
            if lat == 0 and lon == 0 and row.get("address"):
                geo = await geocode_address(row["address"])
                if geo:
                    lat, lon = geo["latitude"], geo["longitude"]
                else:
                    errors.append(f"Row {i+1}: Could not geocode address '{row.get('address')}'")
                    continue

            prop = {
                "name": row.get("name", f"Property {i+1}"),
                "address": row.get("address", ""),
                "latitude": lat,
                "longitude": lon,
                "tiv": float(row.get("tiv", row.get("TIV", 0))),
                "construction_type": row.get("construction_type", "Unknown"),
                "occupancy": row.get("occupancy", "Unknown"),
                "year_built": int(row["year_built"]) if row.get("year_built") else None,
                "stories": int(row.get("stories", 1)),
            }
            properties.append(prop)
        except (ValueError, KeyError) as e:
            errors.append(f"Row {i+1}: {str(e)}")

    with sqlite_session() as conn:
        for prop in properties:
            cursor = conn.execute(
                """INSERT INTO properties
                   (name, address, latitude, longitude, tiv, construction_type, occupancy, year_built, stories)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (prop["name"], prop["address"], prop["latitude"], prop["longitude"],
                 prop["tiv"], prop["construction_type"], prop["occupancy"],
                 prop.get("year_built"), prop["stories"]),
            )
            prop["id"] = cursor.lastrowid

    scored = []
    duck = get_duckdb_conn()
    for prop in properties:
        scorecard = score_property(prop)
        h3_idx = ""
        try:
            import h3
            h3_idx = h3.latlng_to_cell(prop["latitude"], prop["longitude"], 5)
        except Exception:
            pass

        duck.execute(
            """INSERT INTO portfolio_results
               (portfolio_id, property_id, latitude, longitude, tiv,
                seismic_score, flood_score, wind_score, composite_score, rate_factor, h3_index)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (portfolio_id, prop["id"], prop["latitude"], prop["longitude"], prop["tiv"],
             scorecard.seismic.score if scorecard.seismic else 0,
             scorecard.flood.score if scorecard.flood else 0,
             scorecard.wind.score if scorecard.wind else 0,
             scorecard.composite_score,
             1.0 + scorecard.composite_score / 100.0,
             h3_idx),
        )
        scored.append({
            "property_id": prop["id"],
            "name": prop["name"],
            "latitude": prop["latitude"],
            "longitude": prop["longitude"],
            "tiv": prop["tiv"],
            "seismic_score": scorecard.seismic.score if scorecard.seismic else 0,
            "flood_score": scorecard.flood.score if scorecard.flood else 0,
            "wind_score": scorecard.wind.score if scorecard.wind else 0,
            "composite_score": scorecard.composite_score,
            "rate_factor": 1.0 + scorecard.composite_score / 100.0,
            "h3_index": h3_idx,
        })
    duck.close()

    return {
        "portfolio_id": portfolio_id,
        "properties_loaded": len(scored),
        "errors": errors,
        "results": scored,
    }


@router.get("/{portfolio_id}/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(portfolio_id: str):
    duck = get_duckdb_conn()
    rows = duck.execute(
        "SELECT * FROM portfolio_results WHERE portfolio_id = ?",
        (portfolio_id,),
    ).fetchall()
    columns = [desc[0] for desc in duck.description]
    duck.close()

    if not rows:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    results = [dict(zip(columns, r)) for r in rows]
    total_tiv = sum(r["tiv"] for r in results)
    scores = [r["composite_score"] for r in results]

    tier_counts = {"Low": 0, "Moderate": 0, "High": 0, "Very High": 0, "Extreme": 0}
    for s in scores:
        if s < 20:
            tier_counts["Low"] += 1
        elif s < 40:
            tier_counts["Moderate"] += 1
        elif s < 60:
            tier_counts["High"] += 1
        elif s < 80:
            tier_counts["Very High"] += 1
        else:
            tier_counts["Extreme"] += 1

    h3_accum = {}
    for r in results:
        idx = r.get("h3_index", "unknown")
        if idx not in h3_accum:
            h3_accum[idx] = {"h3_index": idx, "count": 0, "total_tiv": 0, "avg_score": 0}
        h3_accum[idx]["count"] += 1
        h3_accum[idx]["total_tiv"] += r["tiv"]
        h3_accum[idx]["avg_score"] += r["composite_score"]

    for v in h3_accum.values():
        v["avg_score"] = round(v["avg_score"] / v["count"], 1) if v["count"] > 0 else 0

    top_accum = sorted(h3_accum.values(), key=lambda x: x["total_tiv"], reverse=True)[:10]

    return PortfolioSummary(
        portfolio_id=portfolio_id,
        total_properties=len(results),
        total_tiv=total_tiv,
        avg_composite_score=round(sum(scores) / len(scores), 1),
        max_composite_score=round(max(scores), 1),
        risk_distribution=tier_counts,
        peril_averages={
            "seismic": round(sum(r["seismic_score"] for r in results) / len(results), 1),
            "flood": round(sum(r["flood_score"] for r in results) / len(results), 1),
            "wind": round(sum(r["wind_score"] for r in results) / len(results), 1),
        },
        top_accumulations=top_accum,
    )


@router.get("/{portfolio_id}/properties", response_model=list[PortfolioPropertyResult])
async def get_portfolio_properties(portfolio_id: str):
    duck = get_duckdb_conn()
    rows = duck.execute(
        "SELECT * FROM portfolio_results WHERE portfolio_id = ? ORDER BY composite_score DESC",
        (portfolio_id,),
    ).fetchall()
    columns = [desc[0] for desc in duck.description]
    duck.close()

    results = []
    for r in rows:
        d = dict(zip(columns, r))
        score = d["composite_score"]
        tier = "Low" if score < 20 else "Moderate" if score < 40 else "High" if score < 60 else "Very High" if score < 80 else "Extreme"
        results.append(PortfolioPropertyResult(
            property_id=d["property_id"],
            latitude=d["latitude"],
            longitude=d["longitude"],
            tiv=d["tiv"],
            seismic_score=d["seismic_score"],
            flood_score=d["flood_score"],
            wind_score=d["wind_score"],
            composite_score=d["composite_score"],
            rate_factor=d["rate_factor"],
            risk_tier=tier,
            h3_index=d.get("h3_index"),
        ))

    return results


@router.get("/{portfolio_id}/export")
async def export_portfolio_csv(portfolio_id: str):
    from fastapi.responses import StreamingResponse

    duck = get_duckdb_conn()
    rows = duck.execute(
        "SELECT * FROM portfolio_results WHERE portfolio_id = ? ORDER BY composite_score DESC",
        (portfolio_id,),
    ).fetchall()
    columns = [desc[0] for desc in duck.description]
    duck.close()

    if not rows:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for r in rows:
        writer.writerow(dict(zip(columns, r)))

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=portfolio_{portfolio_id}.csv"},
    )


@router.get("/{portfolio_id}/accumulation-geojson")
async def get_accumulation_geojson(portfolio_id: str):
    duck = get_duckdb_conn()
    rows = duck.execute(
        "SELECT * FROM portfolio_results WHERE portfolio_id = ?",
        (portfolio_id,),
    ).fetchall()
    columns = [desc[0] for desc in duck.description]
    duck.close()

    features = []
    for r in rows:
        d = dict(zip(columns, r))
        features.append({
            "type": "Feature",
            "properties": {
                "property_id": d["property_id"],
                "tiv": d["tiv"],
                "composite_score": d["composite_score"],
                "seismic_score": d["seismic_score"],
                "flood_score": d["flood_score"],
                "wind_score": d["wind_score"],
                "rate_factor": d["rate_factor"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [d["longitude"], d["latitude"]],
            },
        })

    return {"type": "FeatureCollection", "features": features}
