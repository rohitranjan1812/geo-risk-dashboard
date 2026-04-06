"""Tests for app.services.risk_engine – scoring & composition."""
import pytest

from app.services.risk_engine import (
    compute_composite,
    compute_seismic_score,
    compute_flood_score,
    compute_wind_score,
    score_property,
    SEISMIC_WEIGHT,
    FLOOD_WEIGHT,
    WIND_WEIGHT,
    CONSTRUCTION_MODIFIERS,
)


# ---------------------------------------------------------------------------
# compute_composite
# ---------------------------------------------------------------------------
class TestComputeComposite:
    def test_all_zero(self):
        score, tier = compute_composite(0, 0, 0)
        assert score == 0
        assert tier == "Low"

    def test_all_hundred(self):
        score, tier = compute_composite(100, 100, 100)
        assert score == 100
        assert tier == "Extreme"

    def test_weighted_correctly(self):
        score, _ = compute_composite(50, 50, 50)
        expected = 50 * SEISMIC_WEIGHT + 50 * FLOOD_WEIGHT + 50 * WIND_WEIGHT
        assert score == pytest.approx(expected, abs=0.2)

    def test_tier_boundaries(self):
        _, tier = compute_composite(19, 0, 0)
        assert tier == "Low"

        _, tier = compute_composite(57, 57, 57)
        assert tier == "High"

    def test_low_tier(self):
        score, tier = compute_composite(10, 10, 10)
        assert tier == "Low"

    def test_moderate_tier(self):
        score, tier = compute_composite(35, 35, 35)
        assert tier == "Moderate"

    def test_high_tier(self):
        score, tier = compute_composite(55, 55, 55)
        assert tier == "High"

    def test_very_high_tier(self):
        score, tier = compute_composite(80, 80, 80)
        assert tier == "Extreme"

    def test_exact_boundary_60(self):
        score, tier = compute_composite(60, 60, 60)
        assert tier == "Very High"


# ---------------------------------------------------------------------------
# compute_seismic_score
# ---------------------------------------------------------------------------
class TestComputeSeismicScore:
    def test_san_francisco_high_score(self):
        hs = compute_seismic_score(37.77, -122.42, "Unknown")
        assert hs.score > 50
        assert hs.peril == "seismic"

    def test_low_seismicity_area(self):
        hs = compute_seismic_score(38.5, -98.0, "Unknown")
        assert hs.score < 20

    def test_construction_modifier_applied(self):
        hs_wood = compute_seismic_score(37.77, -122.42, "Wood Frame")
        hs_steel = compute_seismic_score(37.77, -122.42, "Steel Frame")
        assert hs_wood.score >= hs_steel.score

    def test_description_populated(self):
        hs = compute_seismic_score(37.77, -122.42)
        assert hs.description is not None
        assert len(hs.description) > 0


# ---------------------------------------------------------------------------
# compute_flood_score
# ---------------------------------------------------------------------------
class TestComputeFloodScore:
    def test_high_risk_zone(self):
        hs = compute_flood_score(30.0, -90.0)
        assert hs.score >= 80

    def test_low_risk_area(self):
        hs = compute_flood_score(40.0, -100.0)
        assert hs.score <= 20

    def test_peril_is_flood(self):
        hs = compute_flood_score(30.0, -90.0)
        assert hs.peril == "flood"


# ---------------------------------------------------------------------------
# compute_wind_score
# ---------------------------------------------------------------------------
class TestComputeWindScore:
    def test_gulf_coast_high(self):
        hs = compute_wind_score(29.0, -90.0)
        assert hs.score > 40

    def test_inland_low(self):
        hs = compute_wind_score(40.0, -100.0)
        assert hs.score < 20

    def test_peril_is_wind(self):
        hs = compute_wind_score(30.0, -90.0)
        assert hs.peril == "wind"


# ---------------------------------------------------------------------------
# score_property (full scorecard)
# ---------------------------------------------------------------------------
class TestScoreProperty:
    def test_returns_scorecard(self):
        prop = {
            "id": 1,
            "latitude": 37.77,
            "longitude": -122.42,
            "construction_type": "Steel Frame",
            "address": "123 Market St",
        }
        sc = score_property(prop)
        assert sc.property_id == 1
        assert sc.seismic is not None
        assert sc.flood is not None
        assert sc.wind is not None
        assert 0 <= sc.composite_score <= 100
        assert sc.risk_tier in ["Low", "Moderate", "High", "Very High", "Extreme"]
        assert sc.scored_at is not None

    def test_missing_construction_defaults(self):
        prop = {"id": 2, "latitude": 30.0, "longitude": -90.0}
        sc = score_property(prop)
        assert sc.composite_score > 0

    def test_construction_modifiers_coverage(self):
        for ct in CONSTRUCTION_MODIFIERS:
            prop = {"id": 0, "latitude": 37.77, "longitude": -122.42,
                    "construction_type": ct}
            sc = score_property(prop)
            assert sc.seismic is not None
