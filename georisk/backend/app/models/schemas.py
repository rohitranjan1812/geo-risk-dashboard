from datetime import datetime
from pydantic import BaseModel, Field


class PropertyBase(BaseModel):
    name: str | None = None
    address: str | None = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    tiv: float = Field(default=0, ge=0)
    construction_type: str = "Unknown"
    occupancy: str = "Unknown"
    year_built: int | None = None
    stories: int = 1


class PropertyCreate(PropertyBase):
    pass


class PropertyResponse(PropertyBase):
    id: int
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class HazardScore(BaseModel):
    peril: str
    score: float = Field(..., ge=0, le=100)
    raw_value: float | None = None
    unit: str | None = None
    source: str | None = None
    description: str | None = None


class RiskScorecard(BaseModel):
    property_id: int
    latitude: float
    longitude: float
    address: str | None = None
    seismic: HazardScore | None = None
    flood: HazardScore | None = None
    wind: HazardScore | None = None
    composite_score: float = 0
    risk_tier: str = "Unknown"
    scored_at: datetime | None = None


class ScrapeStatus(BaseModel):
    source: str
    description: str | None = None
    last_scraped: datetime | None = None
    record_count: int = 0
    freshness_hours: float | None = None
    status: str = "stale"


class ScrapeRequest(BaseModel):
    source: str


class ScrapeResult(BaseModel):
    source: str
    status: str
    records_fetched: int = 0
    message: str = ""


class GeocodingResult(BaseModel):
    latitude: float
    longitude: float
    matched_address: str
    input_address: str


class PortfolioUpload(BaseModel):
    portfolio_id: str | None = None
    properties: list[PropertyCreate]


class PortfolioSummary(BaseModel):
    portfolio_id: str
    total_properties: int
    total_tiv: float
    avg_composite_score: float
    max_composite_score: float
    risk_distribution: dict[str, int]
    peril_averages: dict[str, float]
    top_accumulations: list[dict]


class PortfolioPropertyResult(BaseModel):
    property_id: int
    name: str | None = None
    address: str | None = None
    latitude: float
    longitude: float
    tiv: float
    seismic_score: float = 0
    flood_score: float = 0
    wind_score: float = 0
    composite_score: float = 0
    rate_factor: float = 1.0
    risk_tier: str = "Unknown"
    h3_index: str | None = None


class EarthquakeEvent(BaseModel):
    id: str
    magnitude: float
    place: str
    time: datetime
    latitude: float
    longitude: float
    depth: float
    event_type: str = "earthquake"
    url: str | None = None


class FloodZoneResult(BaseModel):
    flood_zone: str
    zone_description: str
    sfha: bool
    bfe: float | None = None
    source: str = "FEMA NFHL"


class HurricaneTrack(BaseModel):
    storm_id: str
    name: str
    year: int
    max_wind: float
    min_pressure: float | None = None
    category: int
    track_points: list[dict]
