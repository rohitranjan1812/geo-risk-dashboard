import logging
from fastapi import APIRouter, HTTPException, Query

from app.models.database import sqlite_session
from app.models.schemas import PropertyCreate, PropertyResponse, RiskScorecard
from app.services.geocoder import geocode_address
from app.services.risk_engine import score_property

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=list[PropertyResponse])
async def list_properties():
    with sqlite_session() as conn:
        rows = conn.execute("SELECT * FROM properties ORDER BY id").fetchall()
        return [dict(r) for r in rows]


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(property_id: int):
    with sqlite_session() as conn:
        row = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Property not found")
        return dict(row)


@router.post("/", response_model=PropertyResponse)
async def create_property(prop: PropertyCreate):
    with sqlite_session() as conn:
        cursor = conn.execute(
            """INSERT INTO properties
               (name, address, latitude, longitude, tiv, construction_type, occupancy, year_built, stories)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (prop.name, prop.address, prop.latitude, prop.longitude, prop.tiv,
             prop.construction_type, prop.occupancy, prop.year_built, prop.stories),
        )
        new_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM properties WHERE id = ?", (new_id,)).fetchone()
        return dict(row)


@router.delete("/{property_id}")
async def delete_property(property_id: int):
    with sqlite_session() as conn:
        conn.execute("DELETE FROM hazard_data WHERE property_id = ?", (property_id,))
        result = conn.execute("DELETE FROM properties WHERE id = ?", (property_id,))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Property not found")
    return {"status": "deleted", "property_id": property_id}


@router.get("/{property_id}/risk", response_model=RiskScorecard)
async def get_property_risk(property_id: int):
    with sqlite_session() as conn:
        row = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Property not found")

    return score_property(dict(row))


@router.post("/lookup-address")
async def lookup_by_address(address: str = Query(..., description="Full US address")):
    geo = await geocode_address(address)
    if not geo:
        raise HTTPException(status_code=404, detail="Address not found")

    with sqlite_session() as conn:
        cursor = conn.execute(
            """INSERT INTO properties
               (name, address, latitude, longitude)
               VALUES (?, ?, ?, ?)""",
            (None, geo["matched_address"], geo["latitude"], geo["longitude"]),
        )
        prop_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM properties WHERE id = ?", (prop_id,)).fetchone()

    prop_dict = dict(row)
    scorecard = score_property(prop_dict)
    return {"property": prop_dict, "risk": scorecard.model_dump()}
