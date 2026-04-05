import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "GeoRisk Live Dashboard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    CATALOG_DIR: Path = DATA_DIR / "catalog"
    DB_DIR: Path = DATA_DIR / "db"

    SQLITE_DB: Path = DB_DIR / "georisk.db"
    DUCKDB_PATH: Path = DB_DIR / "analytics.duckdb"

    USGS_EARTHQUAKE_API: str = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    USGS_DESIGNMAPS_API: str = "https://earthquake.usgs.gov/ws/designmaps/"
    FEMA_NFHL_API: str = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
    FEMA_CLAIMS_API: str = "https://www.fema.gov/api/open/v2/FimaNfipClaims"
    NHC_BESTTRACK_URL: str = "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2023-051124.txt"
    CENSUS_GEOCODER_API: str = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

    SCRAPE_INTERVAL_EARTHQUAKE_HOURS: int = 1
    SCRAPE_INTERVAL_FLOOD_HOURS: int = 24
    SCRAPE_INTERVAL_HURRICANE_HOURS: int = 6

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_prefix": "GEORISK_"}


settings = Settings()

for d in [settings.CATALOG_DIR, settings.DB_DIR]:
    d.mkdir(parents=True, exist_ok=True)
