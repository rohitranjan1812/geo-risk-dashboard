# GeoRisk Live Dashboard

A full-stack geo-risk intelligence platform that scrapes public US hazard data, catalogs it locally, and delivers interactive quantitative risk assessment through a graphical web dashboard.

## Quick Start

### Backend (Python/FastAPI)
```bash
cd georisk/backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
API docs: http://localhost:8000/docs

### Frontend (React/TypeScript/Vite)
```bash
cd georisk/frontend
npm install
npm run dev
```
Dashboard: http://localhost:5173

## User Journeys

### 1. Property Explorer (Engineer)
- Search any US address or click a sample property on the map
- Get a risk scorecard with seismic, flood, and wind hazard scores (0-100)
- View hazard map overlays (seismic zones, flood areas, hurricane tracks)
- Run what-if scenarios by adjusting risk weights and hazard overrides

### 2. Portfolio Manager (Insurer)
- Upload a CSV of properties (or load the built-in sample portfolio)
- Each property is geocoded and scored against all hazard layers
- View accumulation heatmap, risk distribution charts, peril averages
- Export scored portfolio with rate factors as CSV

### 3. Data Monitor
- View scrape status and data freshness for each source
- Manually trigger scrapes for any data source
- Automated hourly/daily scraping via APScheduler

## Data Sources

| Source | Data | Update Frequency |
|--------|------|-----------------|
| USGS Earthquake Catalog | Recent seismic events (M2.5+) | Hourly |
| USGS National Seismic Hazard Model | PGA hazard zones | Static (model editions) |
| FEMA NFHL | Flood zones via ArcGIS REST | Daily |
| NOAA/NHC HURDAT2 | Historical hurricane best tracks | Every 6 hours |

## Architecture

- **Backend**: FastAPI + SQLite (metadata) + DuckDB (analytics)
- **Scrapers**: httpx with retry/rate-limit logic + APScheduler
- **Geo processing**: GeoPandas, Shapely, PyProj
- **Frontend**: React + TypeScript + Vite
- **Maps**: MapLibre GL JS with multi-layer rendering
- **Charts**: Recharts (pie, bar, radar)
- **Geocoding**: US Census Geocoder API (free, no key)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/properties/` | GET/POST | List or create properties |
| `/api/properties/{id}/risk` | GET | Risk scorecard for a property |
| `/api/properties/lookup-address` | POST | Geocode + score an address |
| `/api/portfolio/upload` | POST | Upload CSV portfolio |
| `/api/portfolio/{id}/summary` | GET | Portfolio analytics summary |
| `/api/portfolio/{id}/export` | GET | Download scored CSV |
| `/api/data/catalog` | GET | Data source status |
| `/api/data/scrape` | POST | Trigger a scrape |
| `/api/map/layers` | GET | Available map layers |
| `/api/map/layer/{id}` | GET | GeoJSON for a layer |
| `/api/scenarios/what-if` | POST | What-if risk scenario |
| `/api/scenarios/compare-properties` | GET | Compare multiple properties |

## Risk Scoring

Each property receives 0-100 scores for three perils:

- **Seismic**: Based on PGA (Peak Ground Acceleration) from USGS hazard zones, adjusted by construction type
- **Flood**: Based on FEMA flood zone designation (V/VE zones = highest, X = lowest)
- **Wind**: Based on proximity to hurricane-prone coastlines and historical track density

Composite score = weighted average (default: 35% seismic, 35% flood, 30% wind)

Risk tiers: Low (<20), Moderate (20-40), High (40-60), Very High (60-80), Extreme (80+)
