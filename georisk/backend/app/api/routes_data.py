import asyncio
import logging
from fastapi import APIRouter, HTTPException

from app.models.database import sqlite_session
from app.models.schemas import ScrapeStatus, ScrapeRequest, ScrapeResult
from app.scrapers.usgs_seismic import USGSEarthquakeScraper, USGSHazardZonesScraper
from app.scrapers.fema_flood import FEMAFloodScraper
from app.scrapers.noaa_hurricane import NOAAHurricaneScraper

logger = logging.getLogger(__name__)
router = APIRouter()

SCRAPER_MAP = {
    "usgs_earthquake": USGSEarthquakeScraper,
    "usgs_hazard": USGSHazardZonesScraper,
    "fema_flood": FEMAFloodScraper,
    "noaa_hurricane": NOAAHurricaneScraper,
}


@router.get("/catalog", response_model=list[ScrapeStatus])
async def get_data_catalog():
    with sqlite_session() as conn:
        rows = conn.execute("SELECT * FROM data_catalog ORDER BY source").fetchall()
        return [
            ScrapeStatus(
                source=r["source"],
                description=r["description"],
                last_scraped=r["last_scraped"],
                record_count=r["record_count"] or 0,
                freshness_hours=r["freshness_hours"],
                status=r["status"] or "stale",
            )
            for r in rows
        ]


@router.post("/scrape", response_model=ScrapeResult)
async def trigger_scrape(request: ScrapeRequest):
    scraper_cls = SCRAPER_MAP.get(request.source)
    if not scraper_cls:
        raise HTTPException(status_code=400, detail=f"Unknown source: {request.source}")

    scraper = scraper_cls()
    result = await scraper.run()

    return ScrapeResult(
        source=request.source,
        status=result.get("status", "error"),
        records_fetched=result.get("records", 0),
        message=result.get("error", "Scrape completed successfully"),
    )


@router.post("/scrape-all", response_model=list[ScrapeResult])
async def trigger_scrape_all():
    async def _run_one(source: str, scraper_cls):
        scraper = scraper_cls()
        result = await scraper.run()
        return ScrapeResult(
            source=source,
            status=result.get("status", "error"),
            records_fetched=result.get("records", 0),
            message=result.get("error", "Scrape completed successfully"),
        )

    tasks = [_run_one(source, cls) for source, cls in SCRAPER_MAP.items()]
    return await asyncio.gather(*tasks)


@router.get("/scrape-history")
async def get_scrape_history(source: str | None = None, limit: int = 20):
    with sqlite_session() as conn:
        if source:
            rows = conn.execute(
                "SELECT * FROM scrape_log WHERE source = ? ORDER BY started_at DESC LIMIT ?",
                (source, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM scrape_log ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
