"""Tests for app.services.pricing – technical pricing & EP curves."""
import pytest

from app.services.pricing import (
    compute_technical_price,
    build_ep_curve_data,
    _estimate_cv_from_ep,
    DEFAULT_COST_OF_CAPITAL,
    DEFAULT_EXPENSE_LOAD,
)
from app.services.stochastic import (
    run_stochastic_for_location,
    blend_models,
    RETURN_PERIODS,
)


def _sample_blended(seed=42):
    results = run_stochastic_for_location(
        lat=30.0, lon=-90.0, tiv=1_000_000,
        construction="Masonry", occupancy="Residential", stories=1,
        pga=0.3, flood_zone="AE", wind_prob=50.0,
        n_years=500, seed=seed,
    )
    return blend_models(results)


# ---------------------------------------------------------------------------
# _estimate_cv_from_ep
# ---------------------------------------------------------------------------
class TestEstimateCv:
    def test_zero_aal(self):
        assert _estimate_cv_from_ep(0.0, 1000) == 0.0

    def test_positive_aal(self):
        cv = _estimate_cv_from_ep(1000, 5000)
        assert cv > 0

    def test_oep_below_aal_uses_half(self):
        cv = _estimate_cv_from_ep(1000, 500)
        # sigma_approx = max(500 - 1000, 1000 * 0.5) = 500
        assert cv == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# compute_technical_price
# ---------------------------------------------------------------------------
class TestComputeTechnicalPrice:
    def test_basic_structure(self):
        blended = _sample_blended()
        price = compute_technical_price(1_000_000, blended)
        assert "tiv" in price
        assert price["tiv"] == 1_000_000
        assert "total_aal" in price
        assert "technical_rate_pct" in price
        assert "total_premium" in price
        assert "peril_breakdown" in price
        assert "pml" in price

    def test_peril_breakdown_perils(self):
        blended = _sample_blended()
        price = compute_technical_price(1_000_000, blended)
        assert set(price["peril_breakdown"].keys()) == {"seismic", "flood", "wind"}

    def test_premium_nonnegative(self):
        blended = _sample_blended()
        price = compute_technical_price(1_000_000, blended)
        assert price["total_premium"] >= 0
        for peril_data in price["peril_breakdown"].values():
            assert peril_data["premium"] >= 0

    def test_total_premium_is_sum_of_perils(self):
        blended = _sample_blended()
        price = compute_technical_price(1_000_000, blended)
        total = sum(p["premium"] for p in price["peril_breakdown"].values())
        assert price["total_premium"] == pytest.approx(total, rel=0.01)

    def test_zero_tiv(self):
        blended = _sample_blended()
        price = compute_technical_price(0, blended)
        assert price["technical_rate_pct"] == 0.0
        assert price["total_premium"] == 0.0

    def test_custom_loads(self):
        blended = _sample_blended()
        price = compute_technical_price(
            1_000_000, blended,
            cost_of_capital=0.20, expense_load=0.30,
        )
        assert price["cost_of_capital_pct"] == 20.0
        assert price["expense_load_pct"] == 30.0

    def test_pml_return_periods(self):
        blended = _sample_blended()
        price = compute_technical_price(1_000_000, blended)
        for rp in RETURN_PERIODS:
            assert str(rp) in price["pml"]


# ---------------------------------------------------------------------------
# build_ep_curve_data
# ---------------------------------------------------------------------------
class TestBuildEPCurveData:
    def test_contains_all_perils(self):
        blended = _sample_blended()
        curves = build_ep_curve_data(blended)
        assert "seismic" in curves
        assert "flood" in curves
        assert "wind" in curves
        assert "all_perils" in curves

    def test_oep_aep_points_per_peril(self):
        blended = _sample_blended()
        curves = build_ep_curve_data(blended)
        for peril in ["seismic", "flood", "wind"]:
            assert len(curves[peril]["oep"]) == len(RETURN_PERIODS)
            assert len(curves[peril]["aep"]) == len(RETURN_PERIODS)

    def test_return_period_probability(self):
        blended = _sample_blended()
        curves = build_ep_curve_data(blended)
        for pt in curves["seismic"]["oep"]:
            rp = pt["return_period"]
            assert pt["probability"] == pytest.approx(1.0 / rp, abs=1e-5)

    def test_model_curves_present(self):
        blended = _sample_blended()
        curves = build_ep_curve_data(blended)
        for peril in ["seismic", "flood", "wind"]:
            assert "models" in curves[peril]
            assert len(curves[peril]["models"]) == 3
