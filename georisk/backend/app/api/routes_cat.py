"""
CAT modelling API routes.
Provides stochastic simulation, location-level HVE drill-down,
EP curves, technical pricing, and diversification.
"""
import json
import logging
import uuid as _uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import io
import csv

from app.models.database import get_duckdb_conn, sqlite_session
from app.scrapers.usgs_seismic import estimate_pga_at_point
from app.scrapers.fema_flood import determine_flood_zone
from app.scrapers.noaa_hurricane import estimate_hurricane_risk
from app.services.vulnerability import (
    seismic_mdr, flood_mdr, wind_mdr, mdr_curve_points,
)
from app.services.stochastic import run_stochastic_for_location, blend_models
from app.services.pricing import compute_technical_price, build_ep_curve_data
from app.services.diversification import compute_diversification

logger = logging.getLogger(__name__)
router = APIRouter()

IMPORT_PORTFOLIO_ID_OFFSET = 900_000_000_000

def _delete_event_sets_for_session(duck, session_id: str) -> None:
    event_set_ids = [
        r[0]
        for r in duck.execute(
            "SELECT event_set_id FROM cat_event_sets WHERE session_id = ?",
            [session_id],
        ).fetchall()
    ]
    if not event_set_ids:
        duck.execute("DELETE FROM cat_event_sets WHERE session_id = ?", [session_id])
        return

    placeholders = ",".join(["?"] * len(event_set_ids))
    duck.execute(f"DELETE FROM cat_events WHERE event_set_id IN ({placeholders})", event_set_ids)
    duck.execute(f"DELETE FROM cat_annual_losses WHERE event_set_id IN ({placeholders})", event_set_ids)
    duck.execute("DELETE FROM cat_event_sets WHERE session_id = ?", [session_id])

def _latest_session_id_for_portfolio(duck, portfolio_id: str) -> str | None:
    row = duck.execute(
        """SELECT session_id
           FROM cat_sessions
           WHERE portfolio_id = ?
           ORDER BY created_at DESC
           LIMIT 1""",
        [portfolio_id],
    ).fetchone()
    return str(row[0]) if row and row[0] else None

def _csv_response(filename: str, header: list[str], rows: list[list]) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    for r in rows:
        writer.writerow(r)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


class RunModelRequest(BaseModel):
    portfolio_id: str
    n_years: int = 10000
    max_properties: int = 200


class RunModelResponse(BaseModel):
    session_id: str
    portfolio_id: str
    n_properties: int
    n_years: int
    portfolio_tiv: float
    portfolio_aal: float
    portfolio_technical_rate_pct: float
    portfolio_premium: float
    diversification: dict
    properties: list[dict]


class ImportPortfolioRequest(BaseModel):
    name: str | None = None
    max_properties: int = 500


@router.post("/import-portfolio/{portfolio_id}")
async def import_uploaded_portfolio(portfolio_id: str, req: ImportPortfolioRequest):
    duck = get_duckdb_conn()
    prow = duck.execute(
        """SELECT property_id
           FROM portfolio_results
           WHERE portfolio_id = ?
           ORDER BY composite_score DESC
           LIMIT ?""",
        [portfolio_id, int(req.max_properties)],
    ).fetchall()
    property_ids = [int(r[0]) for r in (prow or [])]
    if not property_ids:
        duck.close()
        raise HTTPException(status_code=404, detail="Uploaded portfolio not found or empty")

    # Pull richer exposure attributes from SQLite properties table.
    props: list[dict] = []
    with sqlite_session() as conn:
        for pid in property_ids:
            row = conn.execute("SELECT * FROM properties WHERE id = ?", (pid,)).fetchone()
            if not row:
                continue
            d = dict(row)
            props.append(d)

    if not props:
        duck.close()
        raise HTTPException(status_code=404, detail="No matching properties found in SQLite for this portfolio")

    cat_name = req.name or f"Uploaded Portfolio {portfolio_id}"
    exists = duck.execute(
        "SELECT COUNT(*) FROM cat_portfolios WHERE portfolio_id = ?",
        [portfolio_id],
    ).fetchone()[0]
    if int(exists) == 0:
        duck.execute(
            "INSERT INTO cat_portfolios (portfolio_id, name, filter_criteria) VALUES (?, ?, ?)",
            [portfolio_id, cat_name, json.dumps({"source": "uploaded_portfolio", "portfolio_id": portfolio_id})],
        )

    # Rebuild members.
    duck.execute("DELETE FROM cat_portfolio_members WHERE portfolio_id = ?", [portfolio_id])

    member_rows: list[list] = []
    synth_rows: list[list] = []
    id_map: dict[int, int] = {}
    for p in props:
        src_id = int(p["id"])
        cat_id = int(IMPORT_PORTFOLIO_ID_OFFSET + src_id)
        id_map[src_id] = cat_id
        member_rows.append([portfolio_id, cat_id])
        synth_rows.append([
            cat_id,
            float(p.get("latitude", 0.0)),
            float(p.get("longitude", 0.0)),
            float(p.get("tiv", 0.0)),
            str(p.get("construction_type", "Unknown")),
            str(p.get("occupancy", "Unknown")),
            int(p.get("year_built") or 0) if p.get("year_built") is not None else None,
            int(p.get("stories") or 1),
        ])

    duck.executemany(
        "INSERT INTO cat_portfolio_members (portfolio_id, property_id) VALUES (?, ?)",
        member_rows,
    )
    # Best-effort upsert: remove any existing rows for these imported IDs.
    placeholders = ",".join(["?"] * len(synth_rows))
    if synth_rows:
        ids_only = [r[0] for r in synth_rows]
        duck.execute(f"DELETE FROM synthetic_properties WHERE property_id IN ({placeholders})", ids_only)
        duck.executemany(
            """INSERT INTO synthetic_properties
               (property_id, latitude, longitude, tiv, construction_type, occupancy, year_built, stories)
               VALUES (?,?,?,?,?,?,?,?)""",
            synth_rows,
        )

    duck.close()
    return {
        "portfolio_id": portfolio_id,
        "name": cat_name,
        "n_properties": len(member_rows),
        "id_offset": IMPORT_PORTFOLIO_ID_OFFSET,
        "id_map_sample": dict(list(id_map.items())[:10]),
    }


@router.get("/export/results/{portfolio_id}")
async def export_cat_results_csv(portfolio_id: str, session_id: str | None = None):
    duck = get_duckdb_conn()
    sid = session_id or _latest_session_id_for_portfolio(duck, portfolio_id)
    if not sid:
        duck.close()
        raise HTTPException(status_code=404, detail="No CAT sessions found for this portfolio.")

    rows = duck.execute(
        """SELECT property_id,
                  SUM(aal) AS total_aal,
                  SUM(CASE WHEN peril='seismic' THEN aal END) AS seismic_aal,
                  SUM(CASE WHEN peril='flood' THEN aal END) AS flood_aal,
                  SUM(CASE WHEN peril='wind' THEN aal END) AS wind_aal,
                  SUM(CASE WHEN peril='seismic' THEN oep_250 END) AS seismic_oep_250,
                  SUM(CASE WHEN peril='flood' THEN oep_250 END) AS flood_oep_250,
                  SUM(CASE WHEN peril='wind' THEN oep_250 END) AS wind_oep_250,
                  SUM(CASE WHEN peril='seismic' THEN oep_500 END) AS seismic_oep_500,
                  SUM(CASE WHEN peril='flood' THEN oep_500 END) AS flood_oep_500,
                  SUM(CASE WHEN peril='wind' THEN oep_500 END) AS wind_oep_500
           FROM cat_results
           WHERE portfolio_id = ? AND session_id = ?
           GROUP BY property_id
           ORDER BY total_aal DESC""",
        [portfolio_id, sid],
    ).fetchall()
    duck.close()

    header = [
        "session_id",
        "portfolio_id",
        "property_id",
        "total_aal",
        "seismic_aal",
        "flood_aal",
        "wind_aal",
        "seismic_oep_250",
        "flood_oep_250",
        "wind_oep_250",
        "seismic_oep_500",
        "flood_oep_500",
        "wind_oep_500",
    ]
    out_rows = [[sid, portfolio_id, *list(r)] for r in rows]
    return _csv_response(f"cat_results_{portfolio_id}_{sid}.csv", header, out_rows)


@router.get("/export/ep-curve/{portfolio_id}")
async def export_ep_curve_csv(portfolio_id: str, session_id: str | None = None):
    duck = get_duckdb_conn()
    sid = session_id or _latest_session_id_for_portfolio(duck, portfolio_id)
    duck.close()
    if not sid:
        raise HTTPException(status_code=404, detail="No CAT sessions found for this portfolio.")

    # Reuse existing EP curve computation (aggregates stochastically from members).
    curves = await get_ep_curve(portfolio_id, n_years=5000, max_properties=100)

    header = ["session_id", "portfolio_id", "peril", "curve_type", "return_period", "probability", "loss", "model_id", "model_weight"]
    rows: list[list] = []
    for peril, pdata in curves.items():
        if peril == "all_perils":
            for pt in pdata.get("oep", []):
                rows.append([sid, portfolio_id, peril, "oep", pt.get("return_period"), pt.get("probability"), pt.get("loss"), "", ""])
            continue

        for pt in pdata.get("oep", []):
            rows.append([sid, portfolio_id, peril, "oep", pt.get("return_period"), pt.get("probability"), pt.get("loss"), "", ""])
        for pt in pdata.get("aep", []):
            rows.append([sid, portfolio_id, peril, "aep", pt.get("return_period"), pt.get("probability"), pt.get("loss"), "", ""])
        for m in pdata.get("models", []) or []:
            for pt in m.get("oep", []) or []:
                rows.append([sid, portfolio_id, peril, "model_oep", pt.get("return_period"), "", pt.get("loss"), m.get("model_id"), m.get("weight")])

    return _csv_response(f"cat_ep_curve_{portfolio_id}_{sid}.csv", header, rows)


@router.get("/export/event-set/{event_set_id}")
async def export_event_set_csv(event_set_id: str):
    duck = get_duckdb_conn()
    meta = duck.execute(
        "SELECT session_id, portfolio_id, property_id, peril, model_id FROM cat_event_sets WHERE event_set_id = ?",
        [event_set_id],
    ).fetchone()
    if not meta:
        duck.close()
        raise HTTPException(status_code=404, detail="Event set not found")

    events = duck.execute(
        """SELECT year, event_index, intensity, intensity_unit, mean_dr, dr, loss
           FROM cat_events
           WHERE event_set_id = ?
           ORDER BY loss DESC, year ASC, event_index ASC""",
        [event_set_id],
    ).fetchall()
    duck.close()

    header = [
        "event_set_id",
        "session_id",
        "portfolio_id",
        "property_id",
        "peril",
        "model_id",
        "year",
        "event_index",
        "intensity",
        "intensity_unit",
        "mean_dr",
        "dr",
        "loss",
    ]
    sid, pid, prop_id, peril, model_id = meta
    rows = [[event_set_id, sid, pid, prop_id, peril, model_id, *list(r)] for r in events]
    return _csv_response(f"cat_event_set_{event_set_id}.csv", header, rows)


@router.get("/event-sets")
async def list_event_sets(
    session_id: str,
    property_id: int | None = None,
    peril: str | None = None,
    model_id: str | None = None,
):
    duck = get_duckdb_conn()
    clauses = ["session_id = ?"]
    params: list = [session_id]
    if property_id is not None:
        clauses.append("property_id = ?")
        params.append(int(property_id))
    if peril:
        clauses.append("peril = ?")
        params.append(str(peril))
    if model_id:
        clauses.append("model_id = ?")
        params.append(str(model_id))

    where = " AND ".join(clauses)
    rows = duck.execute(
        f"""SELECT event_set_id, session_id, portfolio_id, property_id, peril, model_id,
                   n_years, seed, params_used, created_at, notes
            FROM cat_event_sets
            WHERE {where}
            ORDER BY property_id, peril, model_id""",
        params,
    ).fetchall()
    cols = [d[0] for d in duck.description] if duck.description else []
    duck.close()
    return [dict(zip(cols, r)) for r in rows]


@router.get("/event-set/{event_set_id}")
async def get_event_set(event_set_id: str, include_annual_losses: bool = True, include_events: bool = True):
    duck = get_duckdb_conn()
    meta = duck.execute(
        """SELECT event_set_id, session_id, portfolio_id, property_id, peril, model_id,
                  n_years, seed, params_used, created_at, notes
           FROM cat_event_sets WHERE event_set_id = ?""",
        [event_set_id],
    ).fetchone()
    if not meta:
        duck.close()
        raise HTTPException(status_code=404, detail="Event set not found")

    mcols = [d[0] for d in duck.description] if duck.description else []
    meta_d = dict(zip(mcols, meta))

    annual_losses = None
    if include_annual_losses:
        al = duck.execute(
            "SELECT year, annual_loss FROM cat_annual_losses WHERE event_set_id = ? ORDER BY year",
            [event_set_id],
        ).fetchall()
        annual_losses = [{"year": int(y), "annual_loss": float(v)} for y, v in al]

    events = None
    if include_events:
        ev = duck.execute(
            """SELECT year, event_index, intensity, intensity_unit, mean_dr, dr, loss
               FROM cat_events WHERE event_set_id = ?
               ORDER BY loss DESC, year ASC, event_index ASC""",
            [event_set_id],
        ).fetchall()
        events = [
            {
                "year": int(r[0]),
                "event_index": int(r[1]),
                "intensity": float(r[2]),
                "intensity_unit": str(r[3]),
                "mean_dr": float(r[4]),
                "dr": float(r[5]),
                "loss": float(r[6]),
            }
            for r in ev
        ]

    duck.close()
    return {"meta": meta_d, "annual_losses": annual_losses, "events": events}


@router.get("/event-set/{event_set_id}/events")
async def get_event_set_events(
    event_set_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=50, le=2000),
    year_min: int | None = None,
    year_max: int | None = None,
    loss_min: float | None = None,
    loss_max: float | None = None,
    intensity_min: float | None = None,
    intensity_max: float | None = None,
):
    duck = get_duckdb_conn()
    clauses = ["event_set_id = ?"]
    params: list = [event_set_id]
    if year_min is not None:
        clauses.append("year >= ?"); params.append(int(year_min))
    if year_max is not None:
        clauses.append("year <= ?"); params.append(int(year_max))
    if loss_min is not None:
        clauses.append("loss >= ?"); params.append(float(loss_min))
    if loss_max is not None:
        clauses.append("loss <= ?"); params.append(float(loss_max))
    if intensity_min is not None:
        clauses.append("intensity >= ?"); params.append(float(intensity_min))
    if intensity_max is not None:
        clauses.append("intensity <= ?"); params.append(float(intensity_max))

    where = " AND ".join(clauses)
    total = duck.execute(f"SELECT COUNT(*) FROM cat_events WHERE {where}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = duck.execute(
        f"""SELECT year, event_index, intensity, intensity_unit, mean_dr, dr, loss
            FROM cat_events
            WHERE {where}
            ORDER BY loss DESC, year ASC, event_index ASC
            LIMIT {page_size} OFFSET {offset}""",
        params,
    ).fetchall()
    duck.close()
    return {
        "event_set_id": event_set_id,
        "total": int(total),
        "page": int(page),
        "page_size": int(page_size),
        "pages": max(1, (int(total) + int(page_size) - 1) // int(page_size)),
        "results": [
            {
                "year": int(r[0]),
                "event_index": int(r[1]),
                "intensity": float(r[2]),
                "intensity_unit": str(r[3]),
                "mean_dr": float(r[4]),
                "dr": float(r[5]),
                "loss": float(r[6]),
            }
            for r in rows
        ],
    }


@router.post("/run-model")
async def run_cat_model(req: RunModelRequest) -> RunModelResponse:
    duck = get_duckdb_conn()
    rows = duck.execute(
        """SELECT m.property_id, p.latitude, p.longitude, p.tiv,
                  p.construction_type, p.occupancy, p.stories
           FROM cat_portfolio_members m
           JOIN synthetic_properties p ON m.property_id = p.property_id
           WHERE m.portfolio_id = ?
           ORDER BY p.tiv DESC
           LIMIT ?""",
        [req.portfolio_id, req.max_properties],
    ).fetchall()

    if not rows:
        duck.close()
        raise HTTPException(status_code=404, detail="Portfolio not found or empty")

    session_id = str(_uuid.uuid4())[:8]
    now_ts = datetime.now(timezone.utc).isoformat()
    pname_row = duck.execute("SELECT name FROM cat_portfolios WHERE portfolio_id = ?", [req.portfolio_id]).fetchone()
    session_name = pname_row[0] if pname_row else req.portfolio_id

    all_results = []
    for pid, lat, lon, tiv, ctype, occ, stories in rows:
        lat, lon, tiv = float(lat), float(lon), float(tiv)
        pga = estimate_pga_at_point(lat, lon)
        flood_info = determine_flood_zone(lat, lon)
        wind_info = estimate_hurricane_risk(lat, lon)

        raw = run_stochastic_for_location(
            lat, lon, tiv, str(ctype), str(occ), int(stories),
            pga, flood_info["flood_zone"], wind_info["max_wind_prob"],
            n_years=req.n_years, seed=int(pid) % (2**31),
            collect_events=True,
            top_k_events=150,
            random_k_events=150,
        )
        blended = blend_models(raw)
        pricing = compute_technical_price(tiv, blended)

        # Persist event sets (metadata + annual loss series + sampled events).
        # Cap stored annual series to keep DuckDB writes bounded on large n_years × many properties.
        # Simulation still uses full req.n_years for AAL/EP; only persisted audit series is truncated.
        max_annual_years = min(int(req.n_years), 2000)
        for peril, models in raw.items():
            for model_id, res in models.items():
                event_set_id = str(_uuid.uuid4())
                duck.execute(
                    """INSERT INTO cat_event_sets
                       (event_set_id, session_id, portfolio_id, property_id, peril, model_id,
                        n_years, seed, params_used, created_at, notes)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    [
                        event_set_id,
                        session_id,
                        req.portfolio_id,
                        int(pid),
                        str(peril),
                        str(model_id),
                        int(res.n_years),
                        int(pid) % (2**31),
                        json.dumps(res.params_used or {}),
                        now_ts,
                        "annual_losses stored up to 2000 years; events are sampled (top+random)",
                    ],
                )

                if max_annual_years > 0 and getattr(res, "annual_losses", None) is not None:
                    annual = res.annual_losses[:max_annual_years]
                    annual_rows = [(event_set_id, int(yi), float(loss_val)) for yi, loss_val in enumerate(annual, start=1)]
                    duck.executemany(
                        "INSERT INTO cat_annual_losses (event_set_id, year, annual_loss) VALUES (?,?,?)",
                        annual_rows,
                    )

                if res.event_sample:
                    intensity_unit = str(getattr(res, "intensity_unit", "") or "")
                    event_rows = [
                        (
                            event_set_id,
                            int(ev.get("year", 0) or 0),
                            int(ev.get("event_index", 0) or 0),
                            float(ev.get("intensity", 0.0) or 0.0),
                            intensity_unit,
                            float(ev.get("mean_dr", 0.0) or 0.0),
                            float(ev.get("dr", 0.0) or 0.0),
                            float(ev.get("loss", 0.0) or 0.0),
                        )
                        for ev in (res.event_sample or [])
                    ]
                    duck.executemany(
                        """INSERT INTO cat_events
                           (event_set_id, year, event_index, intensity, intensity_unit, mean_dr, dr, loss)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        event_rows,
                    )

        all_results.append({
            "property_id": int(pid),
            "latitude": lat, "longitude": lon,
            "tiv": tiv, "construction_type": str(ctype),
            "occupancy": str(occ), "stories": int(stories),
            "blended": blended,
            "pricing": pricing,
        })

    diversification = compute_diversification(all_results, return_period=250)

    portfolio_aal = sum(r["pricing"]["total_aal"] for r in all_results)
    portfolio_tiv = sum(r["tiv"] for r in all_results)
    portfolio_premium = sum(r["pricing"]["total_premium"] for r in all_results)

    for r in all_results:
        for peril in ["seismic", "flood", "wind"]:
            pb = r["pricing"]["peril_breakdown"].get(peril, {})
            duck.execute(
                """INSERT INTO cat_results
                   (session_id, portfolio_id, property_id, peril, model_id, aal,
                    oep_100, oep_250, oep_500, technical_rate, loaded_rate,
                    marginal_pml)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                [session_id, req.portfolio_id, r["property_id"], peril, "blended",
                 pb.get("aal", 0),
                 pb.get("oep_100", 0), pb.get("oep_250", 0), pb.get("oep_500", 0),
                 pb.get("technical_rate_pct", 0), pb.get("loaded_rate_pct", 0), 0],
            )
    duck.execute(
        """INSERT INTO cat_sessions (session_id, portfolio_id, name, status, portfolio_tiv,
           portfolio_aal, portfolio_premium, n_properties, model_config, created_at, completed_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        [session_id, req.portfolio_id, session_name, "modelled",
         round(portfolio_tiv, 2), round(portfolio_aal, 2), round(portfolio_premium, 2),
         len(all_results), json.dumps({"n_years": req.n_years, "max_properties": req.max_properties}),
         now_ts, now_ts],
    )
    duck.close()

    return {
        "session_id": session_id,
        "portfolio_id": req.portfolio_id,
        "n_properties": len(all_results),
        "n_years": req.n_years,
        "portfolio_tiv": round(portfolio_tiv, 2),
        "portfolio_aal": round(portfolio_aal, 2),
        "portfolio_technical_rate_pct": round(portfolio_aal / portfolio_tiv * 100, 4) if portfolio_tiv > 0 else 0,
        "portfolio_premium": round(portfolio_premium, 2),
        "diversification": diversification,
        "properties": [
            {
                "property_id": r["property_id"],
                "tiv": r["tiv"],
                "total_aal": r["pricing"]["total_aal"],
                "technical_rate_pct": r["pricing"]["technical_rate_pct"],
                "total_loaded_rate_pct": r["pricing"]["total_loaded_rate_pct"],
                "total_premium": r["pricing"]["total_premium"],
                "pml_250": float(r["pricing"]["pml"].get("250", 0)),
            }
            for r in all_results
        ],
    }


@router.get("/location-detail/{property_id}")
async def location_detail(property_id: int, n_years: int = Query(10000, ge=1000, le=50000)):
    duck = get_duckdb_conn()
    row = duck.execute(
        "SELECT * FROM synthetic_properties WHERE property_id = ?",
        [property_id],
    ).fetchone()
    cols = [d[0] for d in duck.description] if duck.description else []
    duck.close()

    if not row:
        with sqlite_session() as conn:
            srow = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
            if not srow:
                raise HTTPException(status_code=404, detail="Property not found")
            prop = dict(srow)
    else:
        prop = dict(zip(cols, row))
        prop["id"] = prop.get("property_id", property_id)

    lat = float(prop.get("latitude", 0))
    lon = float(prop.get("longitude", 0))
    tiv = float(prop.get("tiv", 0))
    ctype = str(prop.get("construction_type", "Unknown"))
    occ = str(prop.get("occupancy", "Residential"))
    stories = int(prop.get("stories", 1))

    pga = estimate_pga_at_point(lat, lon)
    flood_info = determine_flood_zone(lat, lon)
    wind_info = estimate_hurricane_risk(lat, lon)

    exposure = {
        "property_id": property_id,
        "latitude": lat, "longitude": lon,
        "tiv": tiv, "construction_type": ctype,
        "occupancy": occ, "stories": stories,
        "year_built": prop.get("year_built"),
    }

    hazard = {
        "seismic": {"pga_g": pga, "source": "USGS"},
        "flood": {"zone": flood_info["flood_zone"], "description": flood_info["zone_description"],
                  "sfha": flood_info["sfha"], "estimated_depth_ft": 3.0 if flood_info["sfha"] else 0.5},
        "wind": {"max_wind_prob": wind_info["max_wind_prob"],
                 "track_density": wind_info["track_density"],
                 "estimated_speed_mph": wind_info["max_wind_prob"] * 1.5 + 40},
    }

    vulnerability = {
        "seismic": {
            "mdr": seismic_mdr(pga, ctype).__dict__,
            "curve": mdr_curve_points("seismic", construction=ctype),
        },
        "flood": {
            "mdr": flood_mdr(hazard["flood"]["estimated_depth_ft"], stories, occ).__dict__,
            "curve": mdr_curve_points("flood", occupancy=occ, stories=stories),
        },
        "wind": {
            "mdr": wind_mdr(hazard["wind"]["estimated_speed_mph"], ctype).__dict__,
            "curve": mdr_curve_points("wind", construction=ctype),
        },
    }

    raw = run_stochastic_for_location(
        lat, lon, tiv, ctype, occ, stories,
        pga, flood_info["flood_zone"], wind_info["max_wind_prob"],
        n_years=n_years, seed=property_id % (2**31),
    )
    blended = blend_models(raw)
    pricing = compute_technical_price(tiv, blended)
    ep_curves = build_ep_curve_data(blended)

    return {
        "exposure": exposure,
        "hazard": hazard,
        "vulnerability": vulnerability,
        "loss": pricing,
        "ep_curves": ep_curves,
        "blended_summary": blended,
    }


@router.get("/ep-curve/{portfolio_id}")
async def get_ep_curve(portfolio_id: str, n_years: int = Query(10000, ge=1000, le=50000), max_properties: int = Query(100, ge=10, le=500)):
    duck = get_duckdb_conn()
    rows = duck.execute(
        """SELECT m.property_id, p.latitude, p.longitude, p.tiv,
                  p.construction_type, p.occupancy, p.stories
           FROM cat_portfolio_members m
           JOIN synthetic_properties p ON m.property_id = p.property_id
           WHERE m.portfolio_id = ?
           ORDER BY p.tiv DESC LIMIT ?""",
        [portfolio_id, max_properties],
    ).fetchall()
    duck.close()

    if not rows:
        raise HTTPException(status_code=404, detail="Portfolio not found or empty")

    agg_blended = {"seismic": None, "flood": None, "wind": None}

    for pid, lat, lon, tiv, ctype, occ, stories in rows:
        lat, lon, tiv = float(lat), float(lon), float(tiv)
        pga = estimate_pga_at_point(lat, lon)
        flood_info = determine_flood_zone(lat, lon)
        wind_info = estimate_hurricane_risk(lat, lon)

        raw = run_stochastic_for_location(
            lat, lon, tiv, str(ctype), str(occ), int(stories),
            pga, flood_info["flood_zone"], wind_info["max_wind_prob"],
            n_years=n_years, seed=int(pid) % (2**31),
        )
        blended = blend_models(raw)

        for peril in ["seismic", "flood", "wind"]:
            pdata = blended.get(peril, {})
            if agg_blended[peril] is None:
                agg_blended[peril] = {
                    "blended_aal": pdata.get("blended_aal", 0),
                    "blended_oep": dict(pdata.get("blended_oep", {})),
                    "blended_aep": dict(pdata.get("blended_aep", {})),
                    "models": pdata.get("models", []),
                }
            else:
                agg_blended[peril]["blended_aal"] += pdata.get("blended_aal", 0)
                for rp_str, val in pdata.get("blended_oep", {}).items():
                    agg_blended[peril]["blended_oep"][rp_str] = agg_blended[peril]["blended_oep"].get(rp_str, 0) + val
                for rp_str, val in pdata.get("blended_aep", {}).items():
                    agg_blended[peril]["blended_aep"][rp_str] = agg_blended[peril]["blended_aep"].get(rp_str, 0) + val

    from app.services.stochastic import RETURN_PERIODS
    total_oep = {}
    for rp in RETURN_PERIODS:
        total_oep[str(rp)] = round(sum(agg_blended[p]["blended_oep"].get(str(rp), 0) for p in ["seismic", "flood", "wind"] if agg_blended[p]), 2)

    agg_blended["all_perils"] = {
        "total_aal": round(sum(agg_blended[p]["blended_aal"] for p in ["seismic", "flood", "wind"] if agg_blended[p]), 2),
        "total_oep": total_oep,
    }

    return build_ep_curve_data(agg_blended)


@router.get("/pricing/{portfolio_id}")
async def get_pricing(portfolio_id: str, session_id: str | None = None):
    duck = get_duckdb_conn()
    sid = session_id or _latest_session_id_for_portfolio(duck, portfolio_id)
    if not sid:
        duck.close()
        raise HTTPException(status_code=404, detail="No CAT sessions found for this portfolio.")
    rows = duck.execute(
        """SELECT property_id, peril, aal, oep_100, oep_250, oep_500,
                  technical_rate, loaded_rate
           FROM cat_results WHERE portfolio_id = ? AND session_id = ? ORDER BY aal DESC""",
        [portfolio_id, sid],
    ).fetchall()
    cols = [d[0] for d in duck.description] if duck.description else []
    duck.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No CAT results. Run the model first.")

    by_property: dict[int, dict] = {}
    for r in rows:
        d = dict(zip(cols, r))
        pid = d["property_id"]
        if pid not in by_property:
            by_property[pid] = {"property_id": pid, "perils": {}, "total_aal": 0, "total_premium_proxy": 0}
        by_property[pid]["perils"][d["peril"]] = {
            "aal": round(d["aal"], 2),
            "oep_250": round(d["oep_250"], 2),
            "technical_rate_pct": round(d["technical_rate"], 4),
            "loaded_rate_pct": round(d["loaded_rate"], 4),
        }
        by_property[pid]["total_aal"] += d["aal"]

    return {"portfolio_id": portfolio_id, "accounts": list(by_property.values())}


@router.get("/diversification/{portfolio_id}")
async def get_diversification(portfolio_id: str, return_period: int = Query(250)):
    duck = get_duckdb_conn()
    rows = duck.execute(
        """SELECT m.property_id, p.latitude, p.longitude, p.tiv,
                  p.construction_type, p.occupancy, p.stories
           FROM cat_portfolio_members m
           JOIN synthetic_properties p ON m.property_id = p.property_id
           WHERE m.portfolio_id = ?
           ORDER BY p.tiv DESC LIMIT 200""",
        [portfolio_id],
    ).fetchall()
    duck.close()

    if not rows:
        raise HTTPException(status_code=404, detail="Portfolio empty")

    property_results = []
    for pid, lat, lon, tiv, ctype, occ, stories in rows:
        lat, lon, tiv = float(lat), float(lon), float(tiv)
        pga = estimate_pga_at_point(lat, lon)
        flood_info = determine_flood_zone(lat, lon)
        wind_info = estimate_hurricane_risk(lat, lon)

        raw = run_stochastic_for_location(
            lat, lon, tiv, str(ctype), str(occ), int(stories),
            pga, flood_info["flood_zone"], wind_info["max_wind_prob"],
            n_years=5000, seed=int(pid) % (2**31),
        )
        blended = blend_models(raw)
        property_results.append({
            "property_id": int(pid), "tiv": tiv, "blended": blended,
        })

    return compute_diversification(property_results, return_period=return_period)


@router.get("/sessions")
async def list_sessions():
    duck = get_duckdb_conn()
    rows = duck.execute(
        """SELECT session_id, portfolio_id, name, status, portfolio_tiv,
                  portfolio_aal, portfolio_premium, n_properties, model_config,
                  created_at, completed_at
           FROM cat_sessions ORDER BY created_at DESC"""
    ).fetchall()
    cols = [d[0] for d in duck.description] if duck.description else []
    duck.close()
    return [dict(zip(cols, r)) for r in rows]

@router.get("/compare")
async def compare_sessions(session_ids: str = Query(..., description="Comma-separated session_ids (2-3 recommended)")):
    ids = [s.strip() for s in (session_ids or "").split(",") if s.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 session_ids")
    if len(ids) > 3:
        ids = ids[:3]

    duck = get_duckdb_conn()
    placeholders = ",".join(["?"] * len(ids))
    sessions = duck.execute(
        f"""SELECT session_id, portfolio_id, name, status, portfolio_tiv, portfolio_aal, portfolio_premium,
                   n_properties, created_at, completed_at
            FROM cat_sessions
            WHERE session_id IN ({placeholders})
            ORDER BY created_at DESC""",
        ids,
    ).fetchall()
    scols = [d[0] for d in duck.description] if duck.description else []
    session_rows = [dict(zip(scols, r)) for r in sessions]
    if not session_rows:
        duck.close()
        raise HTTPException(status_code=404, detail="No matching sessions found")

    curves: dict[str, dict] = {}
    for s in session_rows:
        pid = str(s["portfolio_id"])
        curves[str(s["session_id"])] = await get_ep_curve(pid, n_years=5000, max_properties=100)

    duck.close()
    return {"sessions": session_rows, "ep_curves": curves}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    duck = get_duckdb_conn()
    row = duck.execute("SELECT * FROM cat_sessions WHERE session_id = ?", [session_id]).fetchone()
    if not row:
        duck.close()
        raise HTTPException(status_code=404, detail="Session not found")
    cols = [d[0] for d in duck.description]
    session = dict(zip(cols, row))
    pid = session["portfolio_id"]

    results = duck.execute(
        """SELECT property_id, peril, aal, oep_100, oep_250, oep_500, technical_rate, loaded_rate
           FROM cat_results WHERE portfolio_id = ? AND session_id = ? ORDER BY aal DESC""",
        [pid, session_id],
    ).fetchall()
    rcols = [d[0] for d in duck.description]

    props = duck.execute(
        """SELECT p.property_id, p.latitude, p.longitude, p.tiv, p.construction_type, p.occupancy
           FROM cat_portfolio_members m
           JOIN synthetic_properties p ON m.property_id = p.property_id
           WHERE m.portfolio_id = ?
           ORDER BY p.tiv DESC LIMIT 500""",
        [pid],
    ).fetchall()
    duck.close()

    return {
        "session": session,
        "results": [dict(zip(rcols, r)) for r in results],
        "properties": [
            {"property_id": int(p[0]), "latitude": float(p[1]), "longitude": float(p[2]),
             "tiv": float(p[3]), "construction_type": str(p[4]), "occupancy": str(p[5])}
            for p in props
        ],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    duck = get_duckdb_conn()
    row = duck.execute("SELECT portfolio_id FROM cat_sessions WHERE session_id = ?", [session_id]).fetchone()
    if not row:
        duck.close()
        raise HTTPException(status_code=404, detail="Session not found")
    _delete_event_sets_for_session(duck, session_id)
    duck.execute("DELETE FROM cat_results WHERE session_id = ?", [session_id])
    duck.execute("DELETE FROM cat_sessions WHERE session_id = ?", [session_id])
    duck.close()
    return {"status": "deleted", "session_id": session_id}
