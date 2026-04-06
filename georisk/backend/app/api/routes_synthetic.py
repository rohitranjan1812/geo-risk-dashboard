import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.database import get_duckdb_conn
from app.scrapers.usgs_seismic import estimate_pga_at_point
from app.scrapers.fema_flood import determine_flood_zone
from app.scrapers.noaa_hurricane import estimate_hurricane_risk

logger = logging.getLogger(__name__)
router = APIRouter()


def _score_one(lat: float, lon: float, construction_type: str) -> tuple[float, float, float, float, str]:
    # Local-only scoring (no external USGS calls) so we can handle big volumes quickly.
    pga = estimate_pga_at_point(lat, lon)
    seismic = min(100.0, pga * 140.0)

    flood_info = determine_flood_zone(lat, lon)
    zone_scores = {"V": 95, "VE": 95, "A": 80, "AE": 85, "AH": 75, "AO": 70, "B": 35, "X": 15, "C": 10, "D": 40}
    flood = float(zone_scores.get(flood_info["flood_zone"], 15))

    wind_info = estimate_hurricane_risk(lat, lon)
    wind = float(min(100.0, wind_info["max_wind_prob"] * 1.2))

    composite = round(seismic * 0.35 + flood * 0.35 + wind * 0.30, 1)
    tier = "Low" if composite < 20 else "Moderate" if composite < 40 else "High" if composite < 60 else "Very High" if composite < 80 else "Extreme"
    return seismic, flood, wind, composite, tier


@router.get("/summary")
async def synthetic_summary(sample_n: int = Query(20000, ge=1000, le=200000)):
    duck = get_duckdb_conn()
    total = duck.execute("SELECT COUNT(*) FROM synthetic_properties").fetchone()[0]
    if total == 0:
        duck.close()
        raise HTTPException(status_code=404, detail="No synthetic properties seeded. Set GEORISK_SYNTHETIC_PROPERTIES_COUNT and restart.")

    n = min(int(sample_n), int(total))
    # DuckDB SAMPLE currently requires constants in the clause; use ORDER BY random() LIMIT instead.
    rows = duck.execute(
        f"""
        SELECT latitude, longitude, tiv, construction_type
        FROM synthetic_properties
        ORDER BY random()
        LIMIT {n}
        """
    ).fetchall()
    duck.close()

    totals = {"tiv": 0.0, "seismic": 0.0, "flood": 0.0, "wind": 0.0, "composite": 0.0}
    tier_counts = {"Low": 0, "Moderate": 0, "High": 0, "Very High": 0, "Extreme": 0}

    for lat, lon, tiv, ctype in rows:
        seismic, flood, wind, composite, tier = _score_one(float(lat), float(lon), str(ctype))
        totals["tiv"] += float(tiv)
        totals["seismic"] += seismic
        totals["flood"] += flood
        totals["wind"] += wind
        totals["composite"] += composite
        tier_counts[tier] += 1

    denom = max(1, len(rows))
    return {
        "total_seeded": int(total),
        "sampled": int(denom),
        "sample_total_tiv": totals["tiv"],
        "avg_scores": {
            "seismic": round(totals["seismic"] / denom, 1),
            "flood": round(totals["flood"] / denom, 1),
            "wind": round(totals["wind"] / denom, 1),
            "composite": round(totals["composite"] / denom, 1),
        },
        "risk_distribution": tier_counts,
        "note": "Distribution/averages computed from a random sample using local-only hazard estimators (no external calls).",
    }


@router.get("/sample-points")
async def synthetic_sample_points(limit: int = Query(2000, ge=100, le=50000)):
    duck = get_duckdb_conn()
    total = duck.execute("SELECT COUNT(*) FROM synthetic_properties").fetchone()[0]
    if total == 0:
        duck.close()
        raise HTTPException(status_code=404, detail="No synthetic properties seeded.")

    n = int(limit)
    rows = duck.execute(
        f"""
        SELECT latitude, longitude, tiv, construction_type, occupancy, year_built, stories
        FROM synthetic_properties
        ORDER BY random()
        LIMIT {n}
        """
    ).fetchall()
    duck.close()

    features = []
    for i, (lat, lon, tiv, ctype, occ, yb, st) in enumerate(rows):
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": i + 1,
                    "tiv": float(tiv),
                    "construction_type": str(ctype),
                    "occupancy": str(occ),
                    "year_built": int(yb),
                    "stories": int(st),
                },
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


@router.get("/accumulation-hex")
async def synthetic_accumulation_hex(resolution: int = Query(5, ge=3, le=7), sample_n: int = Query(200000, ge=10000, le=1000000), top_k: int = Query(200, ge=10, le=2000)):
    try:
        import h3
    except Exception:
        raise HTTPException(status_code=500, detail="h3 dependency missing on backend.")

    duck = get_duckdb_conn()
    total = duck.execute("SELECT COUNT(*) FROM synthetic_properties").fetchone()[0]
    if total == 0:
        duck.close()
        raise HTTPException(status_code=404, detail="No synthetic properties seeded.")

    n = min(int(sample_n), int(total))
    rows = duck.execute(
        f"""
        SELECT latitude, longitude, tiv
        FROM synthetic_properties
        ORDER BY random()
        LIMIT {n}
        """
    ).fetchall()
    duck.close()

    bins: dict[str, dict] = {}
    for lat, lon, tiv in rows:
        idx = h3.latlng_to_cell(float(lat), float(lon), int(resolution))
        b = bins.get(idx)
        if not b:
            bins[idx] = {"h3_index": idx, "count": 1, "total_tiv": float(tiv)}
        else:
            b["count"] += 1
            b["total_tiv"] += float(tiv)

    top = sorted(bins.values(), key=lambda x: x["total_tiv"], reverse=True)[: int(top_k)]

    features = []
    for b in top:
        boundary = h3.cell_to_boundary(b["h3_index"])
        coords = [[lng, lat] for lat, lng in boundary]
        coords.append(coords[0])
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "h3_index": b["h3_index"],
                    "count": int(b["count"]),
                    "total_tiv": b["total_tiv"],
                    "sampled_rows": n,
                    "resolution": int(resolution),
                },
                "geometry": {"type": "Polygon", "coordinates": [coords]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


class FilterRequest(BaseModel):
    bbox: list[float] | None = None
    tiv_min: float | None = None
    tiv_max: float | None = None
    construction_types: list[str] | None = None
    occupancies: list[str] | None = None
    year_built_min: int | None = None
    year_built_max: int | None = None
    stories_min: int | None = None
    stories_max: int | None = None
    page: int = 1
    page_size: int = 100


def _build_where(f: FilterRequest) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []
    if f.bbox and len(f.bbox) == 4:
        clauses.append("longitude >= ? AND longitude <= ? AND latitude >= ? AND latitude <= ?")
        params.extend([f.bbox[0], f.bbox[2], f.bbox[1], f.bbox[3]])
    if f.tiv_min is not None:
        clauses.append("tiv >= ?"); params.append(f.tiv_min)
    if f.tiv_max is not None:
        clauses.append("tiv <= ?"); params.append(f.tiv_max)
    if f.construction_types:
        placeholders = ",".join(["?"] * len(f.construction_types))
        clauses.append(f"construction_type IN ({placeholders})")
        params.extend(f.construction_types)
    if f.occupancies:
        placeholders = ",".join(["?"] * len(f.occupancies))
        clauses.append(f"occupancy IN ({placeholders})")
        params.extend(f.occupancies)
    if f.year_built_min is not None:
        clauses.append("year_built >= ?"); params.append(f.year_built_min)
    if f.year_built_max is not None:
        clauses.append("year_built <= ?"); params.append(f.year_built_max)
    if f.stories_min is not None:
        clauses.append("stories >= ?"); params.append(f.stories_min)
    if f.stories_max is not None:
        clauses.append("stories <= ?"); params.append(f.stories_max)
    where = " AND ".join(clauses) if clauses else "1=1"
    return where, params


@router.post("/filter")
async def filter_synthetic(f: FilterRequest):
    where, params = _build_where(f)
    duck = get_duckdb_conn()
    count_row = duck.execute(f"SELECT COUNT(*) FROM synthetic_properties WHERE {where}", params).fetchone()
    total = int(count_row[0]) if count_row else 0
    offset = (f.page - 1) * f.page_size
    rows = duck.execute(
        f"""SELECT property_id, latitude, longitude, tiv, construction_type,
                   occupancy, year_built, stories
            FROM synthetic_properties WHERE {where}
            ORDER BY tiv DESC LIMIT {f.page_size} OFFSET {offset}""",
        params,
    ).fetchall()
    duck.close()
    return {
        "total": total, "page": f.page, "page_size": f.page_size,
        "pages": max(1, (total + f.page_size - 1) // f.page_size),
        "results": [
            {"property_id": int(r[0]), "latitude": float(r[1]), "longitude": float(r[2]),
             "tiv": float(r[3]), "construction_type": str(r[4]), "occupancy": str(r[5]),
             "year_built": int(r[6]), "stories": int(r[7])}
            for r in rows
        ],
    }


class BuildPortfolioRequest(BaseModel):
    name: str = "Untitled Portfolio"
    property_ids: list[int] | None = None
    filter: FilterRequest | None = None
    max_properties: int = 500


@router.post("/build-portfolio")
async def build_portfolio(req: BuildPortfolioRequest):
    import uuid as _uuid
    portfolio_id = str(_uuid.uuid4())[:8]
    duck = get_duckdb_conn()
    duck.execute(
        "INSERT INTO cat_portfolios (portfolio_id, name, filter_criteria) VALUES (?, ?, ?)",
        [portfolio_id, req.name, json.dumps(req.filter.model_dump() if req.filter else {})],
    )
    if req.property_ids:
        for pid in req.property_ids[:req.max_properties]:
            duck.execute("INSERT INTO cat_portfolio_members (portfolio_id, property_id) VALUES (?, ?)", [portfolio_id, pid])
        count = min(len(req.property_ids), req.max_properties)
    elif req.filter:
        where, params = _build_where(req.filter)
        duck.execute(
            f"""INSERT INTO cat_portfolio_members (portfolio_id, property_id)
                SELECT ?, property_id FROM synthetic_properties
                WHERE {where} ORDER BY tiv DESC LIMIT {req.max_properties}""",
            [portfolio_id] + params,
        )
        count = duck.execute("SELECT COUNT(*) FROM cat_portfolio_members WHERE portfolio_id = ?", [portfolio_id]).fetchone()[0]
    else:
        duck.close()
        raise HTTPException(status_code=400, detail="Provide property_ids or filter criteria")
    duck.close()
    return {"portfolio_id": portfolio_id, "name": req.name, "n_properties": int(count)}


@router.get("/portfolio/{portfolio_id}/properties")
async def get_cat_portfolio_properties(portfolio_id: str, page: int = Query(1, ge=1), page_size: int = Query(100, ge=10, le=500)):
    duck = get_duckdb_conn()
    total = duck.execute("SELECT COUNT(*) FROM cat_portfolio_members WHERE portfolio_id = ?", [portfolio_id]).fetchone()[0]
    offset = (page - 1) * page_size
    rows = duck.execute(
        f"""SELECT p.property_id, p.latitude, p.longitude, p.tiv,
                   p.construction_type, p.occupancy, p.year_built, p.stories
            FROM cat_portfolio_members m
            JOIN synthetic_properties p ON m.property_id = p.property_id
            WHERE m.portfolio_id = ?
            ORDER BY p.tiv DESC LIMIT {page_size} OFFSET {offset}""",
        [portfolio_id],
    ).fetchall()
    duck.close()
    return {
        "portfolio_id": portfolio_id, "total": int(total), "page": page, "page_size": page_size,
        "results": [
            {"property_id": int(r[0]), "latitude": float(r[1]), "longitude": float(r[2]),
             "tiv": float(r[3]), "construction_type": str(r[4]), "occupancy": str(r[5]),
             "year_built": int(r[6]), "stories": int(r[7])}
            for r in rows
        ],
    }


@router.get("/portfolios")
async def list_portfolios():
    duck = get_duckdb_conn()
    rows = duck.execute(
        """SELECT p.portfolio_id, p.name, p.created_at, COUNT(m.property_id) as n_props
           FROM cat_portfolios p
           LEFT JOIN cat_portfolio_members m ON p.portfolio_id = m.portfolio_id
           GROUP BY p.portfolio_id, p.name, p.created_at
           ORDER BY p.created_at DESC"""
    ).fetchall()
    duck.close()
    return [{"portfolio_id": r[0], "name": r[1], "created_at": str(r[2]) if r[2] else None, "n_properties": int(r[3])} for r in rows]


class SeedRequest(BaseModel):
    count: int = 100000
    bbox: list[float] | None = None
    tiv_min: float = 50000
    tiv_max: float = 20000000
    construction_types: list[str] | None = None
    occupancies: list[str] | None = None


@router.post("/seed")
async def seed_synthetic(req: SeedRequest):
    import time
    t0 = time.time()
    duck = get_duckdb_conn()
    duck.execute("DELETE FROM synthetic_properties")

    lat_min, lat_max = 24.0, 49.0
    lon_min, lon_max = -125.0, -66.0
    if req.bbox and len(req.bbox) == 4:
        lon_min, lat_min, lon_max, lat_max = req.bbox

    ct_list = req.construction_types or ["Wood Frame", "Masonry", "Reinforced Concrete", "Steel Frame", "Concrete Tilt-Up"]
    occ_list = req.occupancies or ["Residential", "Commercial", "Industrial", "Hospitality", "Healthcare"]
    ct_cases = " ".join([f"WHEN {i} THEN '{c}'" for i, c in enumerate(ct_list)])
    occ_cases = " ".join([f"WHEN {i} THEN '{o}'" for i, o in enumerate(occ_list)])
    n_ct = len(ct_list)
    n_occ = len(occ_list)

    tiv_log_min = f"ln({max(req.tiv_min, 1)})"
    tiv_log_max = f"ln({max(req.tiv_max, 2)})"

    duck.execute(f"""
        INSERT INTO synthetic_properties
        SELECT
            i AS property_id,
            ({lat_min} + random() * {lat_max - lat_min}) AS latitude,
            ({lon_min} + random() * {lon_max - lon_min}) AS longitude,
            exp({tiv_log_min} + random() * ({tiv_log_max} - {tiv_log_min})) AS tiv,
            CASE CAST(floor(random() * {n_ct}) AS INTEGER) {ct_cases} END AS construction_type,
            CASE CAST(floor(random() * {n_occ}) AS INTEGER) {occ_cases} END AS occupancy,
            CAST(1950 + floor(random() * 75) AS INTEGER) AS year_built,
            CAST(1 + floor(random() * 30) AS INTEGER) AS stories
        FROM range(1, {int(req.count)} + 1) t(i)
    """)
    actual = duck.execute("SELECT COUNT(*) FROM synthetic_properties").fetchone()[0]
    duck.close()
    elapsed = round(time.time() - t0, 2)
    return {"count": int(actual), "elapsed_seconds": elapsed}


@router.get("/stats")
async def synthetic_stats():
    duck = get_duckdb_conn()
    row = duck.execute("""
        SELECT COUNT(*) as cnt,
               MIN(tiv) as tiv_min, MAX(tiv) as tiv_max, AVG(tiv) as tiv_avg,
               MIN(latitude) as lat_min, MAX(latitude) as lat_max,
               MIN(longitude) as lon_min, MAX(longitude) as lon_max
        FROM synthetic_properties
    """).fetchone()
    duck.close()
    if not row or row[0] == 0:
        return {"count": 0}
    return {
        "count": int(row[0]),
        "tiv_min": round(float(row[1]), 2), "tiv_max": round(float(row[2]), 2), "tiv_avg": round(float(row[3]), 2),
        "lat_min": round(float(row[4]), 4), "lat_max": round(float(row[5]), 4),
        "lon_min": round(float(row[6]), 4), "lon_max": round(float(row[7]), 4),
    }


@router.get("/portfolio/{portfolio_id}/geojson")
async def portfolio_geojson(portfolio_id: str, limit: int = Query(5000, ge=100, le=50000)):
    duck = get_duckdb_conn()
    rows = duck.execute(
        f"""SELECT p.property_id, p.latitude, p.longitude, p.tiv,
                   p.construction_type, p.occupancy, p.year_built, p.stories
            FROM cat_portfolio_members m
            JOIN synthetic_properties p ON m.property_id = p.property_id
            WHERE m.portfolio_id = ?
            ORDER BY p.tiv DESC LIMIT {limit}""",
        [portfolio_id],
    ).fetchall()
    duck.close()
    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "id": int(r[0]), "tiv": float(r[3]),
                "construction_type": str(r[4]), "occupancy": str(r[5]),
                "year_built": int(r[6]), "stories": int(r[7]),
                "composite_score": 0, "seismic_score": 0, "flood_score": 0, "wind_score": 0,
                "aal": 0, "technical_rate": 0, "dominant_peril": "unknown",
            },
            "geometry": {"type": "Point", "coordinates": [float(r[2]), float(r[1])]},
        })
    return {"type": "FeatureCollection", "features": features}


@router.get("/portfolio/{portfolio_id}/scored-geojson")
async def portfolio_scored_geojson(portfolio_id: str, limit: int = Query(5000, ge=100, le=50000)):
    duck = get_duckdb_conn()
    rows = duck.execute(
        f"""SELECT p.property_id, p.latitude, p.longitude, p.tiv,
                   p.construction_type, p.occupancy,
                   COALESCE(SUM(CASE WHEN cr.peril='seismic' THEN cr.aal END), 0) as s_aal,
                   COALESCE(SUM(CASE WHEN cr.peril='flood' THEN cr.aal END), 0) as f_aal,
                   COALESCE(SUM(CASE WHEN cr.peril='wind' THEN cr.aal END), 0) as w_aal,
                   COALESCE(SUM(cr.aal), 0) as total_aal
            FROM cat_portfolio_members m
            JOIN synthetic_properties p ON m.property_id = p.property_id
            LEFT JOIN cat_results cr ON cr.property_id = p.property_id AND cr.portfolio_id = m.portfolio_id
            WHERE m.portfolio_id = ?
            GROUP BY p.property_id, p.latitude, p.longitude, p.tiv, p.construction_type, p.occupancy
            ORDER BY total_aal DESC LIMIT {limit}""",
        [portfolio_id],
    ).fetchall()
    duck.close()
    features = []
    for r in rows:
        tiv = float(r[3])
        s_aal, f_aal, w_aal, total_aal = float(r[6]), float(r[7]), float(r[8]), float(r[9])
        tech_rate = total_aal / tiv * 100 if tiv > 0 else 0
        s_score = min(100, s_aal / tiv * 10000) if tiv > 0 else 0
        f_score = min(100, f_aal / tiv * 10000) if tiv > 0 else 0
        w_score = min(100, w_aal / tiv * 10000) if tiv > 0 else 0
        composite = s_score * 0.35 + f_score * 0.35 + w_score * 0.30
        perils = {"seismic": s_aal, "flood": f_aal, "wind": w_aal}
        dominant = max(perils, key=perils.get) if total_aal > 0 else "unknown"
        features.append({
            "type": "Feature",
            "properties": {
                "id": int(r[0]), "tiv": tiv,
                "construction_type": str(r[4]), "occupancy": str(r[5]),
                "composite_score": round(composite, 1),
                "seismic_score": round(s_score, 1), "flood_score": round(f_score, 1), "wind_score": round(w_score, 1),
                "aal": round(total_aal, 2), "technical_rate": round(tech_rate, 4),
                "dominant_peril": dominant,
            },
            "geometry": {"type": "Point", "coordinates": [float(r[2]), float(r[1])]},
        })
    return {"type": "FeatureCollection", "features": features}

