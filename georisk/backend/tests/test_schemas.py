"""Tests for app.models.schemas – Pydantic model validation."""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.schemas import (
    PropertyBase,
    PropertyCreate,
    PropertyResponse,
    HazardScore,
    RiskScorecard,
    ScrapeStatus,
    ScrapeRequest,
    ScrapeResult,
    GeocodingResult,
    PortfolioSummary,
    PortfolioPropertyResult,
    EarthquakeEvent,
    FloodZoneResult,
    HurricaneTrack,
)


# ---------------------------------------------------------------------------
# PropertyBase / PropertyCreate
# ---------------------------------------------------------------------------
class TestPropertySchemas:
    def test_valid_property(self):
        p = PropertyCreate(latitude=37.77, longitude=-122.42)
        assert p.latitude == 37.77
        assert p.construction_type == "Unknown"
        assert p.stories == 1

    def test_latitude_bounds(self):
        with pytest.raises(ValidationError):
            PropertyCreate(latitude=91.0, longitude=0.0)
        with pytest.raises(ValidationError):
            PropertyCreate(latitude=-91.0, longitude=0.0)

    def test_longitude_bounds(self):
        with pytest.raises(ValidationError):
            PropertyCreate(latitude=0.0, longitude=181.0)
        with pytest.raises(ValidationError):
            PropertyCreate(latitude=0.0, longitude=-181.0)

    def test_tiv_nonnegative(self):
        with pytest.raises(ValidationError):
            PropertyCreate(latitude=0.0, longitude=0.0, tiv=-100)

    def test_optional_fields(self):
        p = PropertyCreate(latitude=0.0, longitude=0.0)
        assert p.name is None
        assert p.address is None
        assert p.year_built is None

    def test_property_response_has_id(self):
        pr = PropertyResponse(id=1, latitude=0.0, longitude=0.0)
        assert pr.id == 1


# ---------------------------------------------------------------------------
# HazardScore
# ---------------------------------------------------------------------------
class TestHazardScore:
    def test_valid_score(self):
        hs = HazardScore(peril="seismic", score=50.0)
        assert hs.peril == "seismic"

    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            HazardScore(peril="seismic", score=-1)
        with pytest.raises(ValidationError):
            HazardScore(peril="seismic", score=101)

    def test_optional_fields(self):
        hs = HazardScore(peril="flood", score=30.0)
        assert hs.raw_value is None
        assert hs.unit is None
        assert hs.source is None


# ---------------------------------------------------------------------------
# RiskScorecard
# ---------------------------------------------------------------------------
class TestRiskScorecard:
    def test_basic_scorecard(self):
        sc = RiskScorecard(property_id=1, latitude=37.0, longitude=-122.0)
        assert sc.composite_score == 0
        assert sc.risk_tier == "Unknown"

    def test_with_hazards(self):
        sc = RiskScorecard(
            property_id=1, latitude=37.0, longitude=-122.0,
            seismic=HazardScore(peril="seismic", score=70),
            flood=HazardScore(peril="flood", score=30),
            wind=HazardScore(peril="wind", score=10),
            composite_score=40,
            risk_tier="High",
        )
        assert sc.seismic.score == 70
        assert sc.risk_tier == "High"


# ---------------------------------------------------------------------------
# Other schemas
# ---------------------------------------------------------------------------
class TestOtherSchemas:
    def test_scrape_status_defaults(self):
        ss = ScrapeStatus(source="usgs_earthquake")
        assert ss.record_count == 0
        assert ss.status == "stale"

    def test_geocoding_result(self):
        gr = GeocodingResult(
            latitude=37.77, longitude=-122.42,
            matched_address="123 Main St", input_address="123 main",
        )
        assert gr.latitude == 37.77

    def test_earthquake_event(self):
        ee = EarthquakeEvent(
            id="us12345", magnitude=5.2, place="California",
            time=datetime.now(), latitude=37.0, longitude=-122.0, depth=10.0,
        )
        assert ee.magnitude == 5.2

    def test_flood_zone_result(self):
        fz = FloodZoneResult(flood_zone="AE", zone_description="High risk", sfha=True)
        assert fz.sfha is True

    def test_hurricane_track(self):
        ht = HurricaneTrack(
            storm_id="AL122005", name="KATRINA", year=2005,
            max_wind=150, category=5, track_points=[],
        )
        assert ht.category == 5

    def test_portfolio_property_result_defaults(self):
        ppr = PortfolioPropertyResult(property_id=1, tiv=1000,
                                       latitude=30.0, longitude=-90.0)
        assert ppr.composite_score == 0
        assert ppr.rate_factor == 1.0
