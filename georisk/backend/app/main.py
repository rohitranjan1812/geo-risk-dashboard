import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.database import init_database
from app.api.routes_property import router as property_router
from app.api.routes_portfolio import router as portfolio_router
from app.api.routes_data import router as data_router
from app.api.routes_map import router as map_router
from app.api.routes_scenarios import router as scenarios_router
from app.api.routes_synthetic import router as synthetic_router
from app.api.routes_cat import router as cat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = None


def setup_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.scrapers.usgs_seismic import USGSEarthquakeScraper, USGSHazardZonesScraper
    from app.scrapers.fema_flood import FEMAFloodScraper
    from app.scrapers.noaa_hurricane import NOAAHurricaneScraper

    sched = AsyncIOScheduler()

    async def run_earthquake_scrape():
        scraper = USGSEarthquakeScraper()
        await scraper.run()

    async def run_flood_scrape():
        scraper = FEMAFloodScraper()
        await scraper.run()

    async def run_hurricane_scrape():
        scraper = NOAAHurricaneScraper()
        await scraper.run()

    sched.add_job(run_earthquake_scrape, "interval", hours=settings.SCRAPE_INTERVAL_EARTHQUAKE_HOURS, id="earthquake_scrape")
    async def run_usgs_hazard_scrape():
        scraper = USGSHazardZonesScraper()
        await scraper.run()

    # Keep locally-bundled hazard zones marked fresh (weekly).
    sched.add_job(run_usgs_hazard_scrape, "interval", hours=24 * 7, id="usgs_hazard_scrape")
    sched.add_job(run_flood_scrape, "interval", hours=settings.SCRAPE_INTERVAL_FLOOD_HOURS, id="flood_scrape")
    sched.add_job(run_hurricane_scrape, "interval", hours=settings.SCRAPE_INTERVAL_HURRICANE_HOURS, id="hurricane_scrape")

    return sched


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global scheduler  # noqa: PLW0603
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    init_database()
    logger.info("Database initialized")

    try:
        scheduler = setup_scheduler()
        scheduler.start()
        logger.info("Scheduler started")
    except (ImportError, RuntimeError, OSError):
        logger.exception("Failed to start scheduler")

    yield

    if scheduler is not None:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Live geo-risk intelligence platform with quantitative hazard assessment",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(property_router, prefix="/api/properties", tags=["Properties"])
app.include_router(portfolio_router, prefix="/api/portfolio", tags=["Portfolio"])
app.include_router(data_router, prefix="/api/data", tags=["Data Catalog"])
app.include_router(map_router, prefix="/api/map", tags=["Map Layers"])
app.include_router(scenarios_router, prefix="/api/scenarios", tags=["Scenarios"])
app.include_router(synthetic_router, prefix="/api/synthetic", tags=["Synthetic Properties"])
app.include_router(cat_router, prefix="/api/cat", tags=["CAT Modelling"])


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
