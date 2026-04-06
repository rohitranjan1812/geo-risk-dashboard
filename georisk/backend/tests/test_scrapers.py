"""Tests for scraper helper functions (no network calls)."""
import pytest

from app.scrapers.usgs_seismic import estimate_pga_at_point, SEISMIC_HAZARD_ZONES
from app.scrapers.fema_flood import determine_flood_zone, FLOOD_ZONE_DESCRIPTIONS
from app.scrapers.noaa_hurricane import (
    wind_to_category,
    estimate_hurricane_risk,
    HURRICANE_TRACKS_SAMPLE,
)


# ---------------------------------------------------------------------------
# USGS PGA estimation
# ---------------------------------------------------------------------------
class TestEstimatePGA:
    def test_san_francisco_very_high(self):
        pga = estimate_pga_at_point(37.77, -122.42)
        assert pga == 0.7  # Very High zone

    def test_seattle_high(self):
        pga = estimate_pga_at_point(47.6, -122.3)
        assert pga == 0.5  # Pacific NW

    def test_memphis_moderate_high(self):
        pga = estimate_pga_at_point(35.5, -90.0)
        assert pga == 0.3  # New Madrid zone

    def test_outside_zones_returns_baseline(self):
        # Middle of Kansas – not in any zone
        pga = estimate_pga_at_point(38.5, -98.0)
        assert pga == 0.05

    def test_anchorage_alaska(self):
        pga = estimate_pga_at_point(61.2, -150.0)
        assert pga == 0.5  # Alaska high zone


# ---------------------------------------------------------------------------
# Flood zone determination
# ---------------------------------------------------------------------------
class TestDetermineFloodZone:
    def test_new_orleans_area(self):
        # Inside the AE zone polygon
        result = determine_flood_zone(30.0, -90.0)
        assert result["flood_zone"] == "AE"
        assert result["sfha"] is True

    def test_miami_coastal(self):
        result = determine_flood_zone(25.8, -80.2)
        assert result["flood_zone"] == "VE"
        assert result["sfha"] is True

    def test_outside_all_zones(self):
        result = determine_flood_zone(40.0, -100.0)
        assert result["flood_zone"] == "X"
        assert result["sfha"] is False

    def test_zone_descriptions_complete(self):
        for zone, (name, desc, sfha) in FLOOD_ZONE_DESCRIPTIONS.items():
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert isinstance(sfha, bool)


# ---------------------------------------------------------------------------
# Hurricane / Wind
# ---------------------------------------------------------------------------
class TestWindToCategory:
    def test_cat5(self):
        assert wind_to_category(140) == 5

    def test_cat4(self):
        assert wind_to_category(120) == 4

    def test_cat3(self):
        assert wind_to_category(100) == 3

    def test_cat2(self):
        assert wind_to_category(90) == 2

    def test_cat1(self):
        assert wind_to_category(70) == 1

    def test_tropical_storm(self):
        assert wind_to_category(50) == 0

    def test_boundary_values(self):
        assert wind_to_category(137) == 5
        assert wind_to_category(136) == 4
        assert wind_to_category(113) == 4
        assert wind_to_category(112) == 3
        assert wind_to_category(96) == 3
        assert wind_to_category(95) == 2
        assert wind_to_category(83) == 2
        assert wind_to_category(82) == 1
        assert wind_to_category(64) == 1
        assert wind_to_category(63) == 0


class TestEstimateHurricaneRisk:
    def test_gulf_coast_high_risk(self):
        r = estimate_hurricane_risk(29.0, -90.0)
        assert r["max_wind_prob"] > 50
        assert r["source"] == "Historical track analysis"

    def test_inland_low_risk(self):
        r = estimate_hurricane_risk(40.0, -100.0)
        assert r["max_wind_prob"] == 5.0
        assert r["source"] == "Outside hurricane belt"

    def test_miami_high_risk(self):
        r = estimate_hurricane_risk(25.8, -80.2)
        assert r["max_wind_prob"] > 40

    def test_northeast_coast(self):
        r = estimate_hurricane_risk(40.0, -74.0)
        assert r["max_wind_prob"] > 5

    def test_track_density_increases_risk(self):
        # Gulf coast near Katrina track
        r = estimate_hurricane_risk(29.5, -89.5)
        assert r["track_density"] > 0
