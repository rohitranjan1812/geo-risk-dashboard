import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path

import duckdb

from app.config import settings

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    address TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    tiv REAL DEFAULT 0,
    construction_type TEXT DEFAULT 'Unknown',
    occupancy TEXT DEFAULT 'Unknown',
    year_built INTEGER,
    stories INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hazard_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    peril TEXT NOT NULL,
    score REAL,
    raw_data TEXT,
    source TEXT,
    queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    records_fetched INTEGER DEFAULT 0,
    file_path TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS data_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL UNIQUE,
    description TEXT,
    last_scraped TIMESTAMP,
    record_count INTEGER DEFAULT 0,
    file_path TEXT,
    freshness_hours REAL,
    status TEXT DEFAULT 'stale'
);

CREATE INDEX IF NOT EXISTS idx_properties_coords ON properties(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_hazard_property ON hazard_data(property_id, peril);
CREATE INDEX IF NOT EXISTS idx_scrape_source ON scrape_log(source, started_at);
"""

SAMPLE_PROPERTIES = [
    ("Golden Gate Residence", "123 Market St, San Francisco, CA", 37.7749, -122.4194, 1500000, "Steel Frame", "Commercial", 1985, 12),
    ("Miami Beach Condo", "456 Ocean Dr, Miami Beach, FL", 25.7617, -80.1918, 800000, "Reinforced Concrete", "Residential", 2005, 8),
    ("French Quarter Hotel", "789 Bourbon St, New Orleans, LA", 29.9584, -90.0644, 2200000, "Masonry", "Hospitality", 1920, 3),
    ("Oklahoma Office Park", "100 Main St, Oklahoma City, OK", 35.4676, -97.5164, 5000000, "Steel Frame", "Commercial", 2010, 5),
    ("Houston Refinery", "200 Industrial Blvd, Houston, TX", 29.7604, -95.3698, 15000000, "Steel", "Industrial", 1995, 2),
    ("Charleston Historic Inn", "50 Church St, Charleston, SC", 32.7765, -79.9311, 1200000, "Wood Frame", "Hospitality", 1850, 2),
    ("Seattle Tech Campus", "300 Pike St, Seattle, WA", 47.6062, -122.3321, 8000000, "Steel Frame", "Commercial", 2018, 6),
    ("Memphis Warehouse", "400 Beale St, Memphis, TN", 35.1175, -89.9711, 3000000, "Concrete Tilt-Up", "Industrial", 2000, 1),
    ("Anchorage Office", "500 Northern Lights Blvd, Anchorage, AK", 61.2181, -149.9003, 2000000, "Steel Frame", "Commercial", 2015, 4),
    ("Puerto Rico Resort", "600 Condado Ave, San Juan, PR", 18.4655, -66.1057, 6000000, "Reinforced Concrete", "Hospitality", 2008, 10),
]


def get_sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.SQLITE_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def sqlite_session():
    conn = get_sqlite_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_duckdb_conn() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(settings.DUCKDB_PATH))


def init_database():
    with sqlite_session() as conn:
        conn.executescript(SQLITE_SCHEMA)

        count = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
        if count == 0:
            conn.executemany(
                """INSERT INTO properties
                   (name, address, latitude, longitude, tiv, construction_type, occupancy, year_built, stories)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                SAMPLE_PROPERTIES,
            )

        catalog_sources = [
            ("usgs_earthquake", "USGS Earthquake Catalog - real-time seismic events"),
            ("usgs_hazard", "USGS National Seismic Hazard Model - PGA grids"),
            ("fema_flood", "FEMA NFHL Flood Zones - flood hazard areas"),
            ("noaa_hurricane", "NOAA/NHC Hurricane Best Tracks - historical storms"),
        ]
        for source, desc in catalog_sources:
            conn.execute(
                """INSERT OR IGNORE INTO data_catalog (source, description)
                   VALUES (?, ?)""",
                (source, desc),
            )

    duck = get_duckdb_conn()
    duck.execute("""
        CREATE TABLE IF NOT EXISTS synthetic_properties (
            property_id BIGINT,
            latitude DOUBLE,
            longitude DOUBLE,
            tiv DOUBLE,
            construction_type TEXT,
            occupancy TEXT,
            year_built INTEGER,
            stories INTEGER
        )
    """)
    duck.execute("""
        CREATE TABLE IF NOT EXISTS risk_scores (
            property_id INTEGER,
            peril TEXT,
            score REAL,
            pga REAL,
            flood_zone TEXT,
            wind_speed REAL,
            composite_score REAL,
            scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    duck.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_results (
            portfolio_id TEXT,
            property_id INTEGER,
            latitude REAL,
            longitude REAL,
            tiv REAL,
            seismic_score REAL,
            flood_score REAL,
            wind_score REAL,
            composite_score REAL,
            rate_factor REAL,
            h3_index TEXT,
            scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    duck.execute("""
        CREATE TABLE IF NOT EXISTS cat_portfolios (
            portfolio_id TEXT,
            name TEXT,
            filter_criteria TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    duck.execute("""
        CREATE TABLE IF NOT EXISTS cat_portfolio_members (
            portfolio_id TEXT,
            property_id BIGINT
        )
    """)
    duck.execute("""
        CREATE TABLE IF NOT EXISTS cat_results (
            portfolio_id TEXT,
            property_id BIGINT,
            peril TEXT,
            model_id TEXT,
            aal DOUBLE,
            oep_100 DOUBLE,
            oep_250 DOUBLE,
            oep_500 DOUBLE,
            technical_rate DOUBLE,
            loaded_rate DOUBLE,
            marginal_pml DOUBLE,
            scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    target = int(getattr(settings, "SYNTHETIC_PROPERTIES_COUNT", 0) or 0)
    if target > 0:
        existing = duck.execute("SELECT COUNT(*) FROM synthetic_properties").fetchone()[0]
        if existing < target:
            duck.execute("DELETE FROM synthetic_properties")
            duck.execute(
                """
                INSERT INTO synthetic_properties
                SELECT
                    i AS property_id,
                    (24.0 + random() * 25.0) AS latitude,
                    (-125.0 + random() * 59.0) AS longitude,
                    exp(random() * 3.0 + 12.0) AS tiv,
                    CASE floor(random() * 5)
                        WHEN 0 THEN 'Wood Frame'
                        WHEN 1 THEN 'Masonry'
                        WHEN 2 THEN 'Reinforced Concrete'
                        WHEN 3 THEN 'Steel Frame'
                        ELSE 'Concrete Tilt-Up'
                    END AS construction_type,
                    CASE floor(random() * 5)
                        WHEN 0 THEN 'Residential'
                        WHEN 1 THEN 'Commercial'
                        WHEN 2 THEN 'Industrial'
                        WHEN 3 THEN 'Hospitality'
                        ELSE 'Healthcare'
                    END AS occupancy,
                    CAST(1950 + floor(random() * 75) AS INTEGER) AS year_built,
                    CAST(1 + floor(random() * 30) AS INTEGER) AS stories
                FROM range(1, ? + 1) t(i)
                """,
                [target],
            )

    duck.close()
