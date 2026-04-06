"""Tests for app.services.stochastic – Monte Carlo engine & model blending."""
import numpy as np
import pytest

from app.services.stochastic import (
    RETURN_PERIODS,
    MODEL_PARAMS,
    DEFAULT_BLEND_WEIGHTS,
    LocationHazard,
    EventTableResult,
    _base_hazard_for_location,
    _build_result,
    run_stochastic_for_location,
    blend_models,
    _EventSampler,
)


# ---------------------------------------------------------------------------
# LocationHazard construction from inputs
# ---------------------------------------------------------------------------
class TestBaseHazardForLocation:
    def test_high_pga_high_eq_freq(self):
        h = _base_hazard_for_location(37.77, -122.42, 0.7, "X", 10.0)
        assert h.base_seismic_freq == 0.08
        assert h.base_seismic_pga == 0.7

    def test_moderate_pga(self):
        h = _base_hazard_for_location(35.0, -90.0, 0.3, "AE", 20.0)
        assert h.base_seismic_freq == 0.04

    def test_low_pga(self):
        h = _base_hazard_for_location(40.0, -74.0, 0.08, "X", 5.0)
        assert h.base_seismic_freq == 0.005

    def test_flood_zone_V(self):
        h = _base_hazard_for_location(0.0, 0.0, 0.05, "V", 0.0)
        assert h.base_flood_freq == 0.05
        assert h.base_flood_depth == 8.0

    def test_flood_zone_X(self):
        h = _base_hazard_for_location(0.0, 0.0, 0.05, "X", 0.0)
        assert h.base_flood_freq == 0.002
        assert h.base_flood_depth == 0.5

    def test_high_wind_prob(self):
        h = _base_hazard_for_location(0.0, 0.0, 0.05, "X", 80.0)
        assert h.base_wind_speed == 120.0

    def test_moderate_wind_prob(self):
        h = _base_hazard_for_location(0.0, 0.0, 0.05, "X", 40.0)
        assert h.base_wind_speed == 95.0

    def test_pga_zero_gets_minimum(self):
        h = _base_hazard_for_location(0.0, 0.0, 0.0, "X", 0.0)
        assert h.base_seismic_pga == 0.01  # min clamp


# ---------------------------------------------------------------------------
# _build_result
# ---------------------------------------------------------------------------
class TestBuildResult:
    def test_aal_is_mean(self):
        losses = np.array([100, 200, 300, 0, 0])
        r = _build_result("seismic", "test", 5, losses)
        assert r.aal == pytest.approx(120.0)

    def test_return_periods_populated(self):
        losses = np.zeros(10000)
        losses[0] = 50000
        r = _build_result("flood", "m1", 10000, losses)
        for rp in RETURN_PERIODS:
            assert rp in r.oep

    def test_all_zero_losses(self):
        losses = np.zeros(1000)
        r = _build_result("wind", "m1", 1000, losses)
        assert r.aal == 0.0
        for rp in RETURN_PERIODS:
            assert r.oep[rp] == 0.0


# ---------------------------------------------------------------------------
# EventSampler
# ---------------------------------------------------------------------------
class TestEventSampler:
    def test_top_k_captures_largest(self):
        rng = np.random.default_rng(42)
        s = _EventSampler(rng, top_k=3, random_k=0)
        for i in range(10):
            s.consider(float(i), {"value": i})
        top = s.sampled()
        top_vals = [r["value"] for r in top]
        assert 9 in top_vals
        assert 8 in top_vals
        assert 7 in top_vals

    def test_random_k_reservoir(self):
        rng = np.random.default_rng(42)
        s = _EventSampler(rng, top_k=0, random_k=5)
        for i in range(100):
            s.consider(float(i), {"value": i})
        sampled = s.sampled()
        assert len(sampled) == 5


# ---------------------------------------------------------------------------
# run_stochastic_for_location (deterministic with seed)
# ---------------------------------------------------------------------------
class TestRunStochastic:
    def test_reproducible_with_seed(self):
        kwargs = dict(
            lat=37.77, lon=-122.42, tiv=1_000_000,
            construction="Wood Frame", occupancy="Residential", stories=2,
            pga=0.7, flood_zone="X", wind_prob=10.0,
            n_years=500, seed=123,
        )
        r1 = run_stochastic_for_location(**kwargs)
        r2 = run_stochastic_for_location(**kwargs)
        # Same seed → identical AAL
        for peril in ["seismic", "flood", "wind"]:
            for model in r1[peril]:
                assert r1[peril][model].aal == r2[peril][model].aal

    def test_returns_three_perils(self):
        r = run_stochastic_for_location(
            lat=30.0, lon=-90.0, tiv=500_000,
            construction="Masonry", occupancy="Commercial", stories=1,
            pga=0.3, flood_zone="AE", wind_prob=50.0,
            n_years=100, seed=0,
        )
        assert set(r.keys()) == {"seismic", "flood", "wind"}

    def test_three_models_per_peril(self):
        r = run_stochastic_for_location(
            lat=30.0, lon=-90.0, tiv=500_000,
            construction="Masonry", occupancy="Commercial", stories=1,
            pga=0.3, flood_zone="AE", wind_prob=50.0,
            n_years=100, seed=0,
        )
        for peril in r:
            assert set(r[peril].keys()) == {"conservative", "best_estimate", "optimistic"}

    def test_collect_events_flag(self):
        r = run_stochastic_for_location(
            lat=30.0, lon=-90.0, tiv=500_000,
            construction="Masonry", occupancy="Commercial", stories=1,
            pga=0.3, flood_zone="AE", wind_prob=50.0,
            n_years=200, seed=42, collect_events=True,
            top_k_events=5, random_k_events=5,
        )
        # At least one peril/model should have sampled events
        has_events = any(
            len(r[peril][model].event_sample) > 0
            for peril in r for model in r[peril]
        )
        assert has_events

    def test_aal_nonnegative(self):
        r = run_stochastic_for_location(
            lat=25.76, lon=-80.19, tiv=800_000,
            construction="Reinforced Concrete", occupancy="Residential", stories=8,
            pga=0.05, flood_zone="VE", wind_prob=70.0,
            n_years=200, seed=7,
        )
        for peril in r:
            for model in r[peril]:
                assert r[peril][model].aal >= 0


# ---------------------------------------------------------------------------
# blend_models
# ---------------------------------------------------------------------------
class TestBlendModels:
    def _make_results(self, seed=42):
        return run_stochastic_for_location(
            lat=30.0, lon=-90.0, tiv=1_000_000,
            construction="Masonry", occupancy="Residential", stories=1,
            pga=0.3, flood_zone="AE", wind_prob=50.0,
            n_years=200, seed=seed,
        )

    def test_blended_keys(self):
        results = self._make_results()
        b = blend_models(results)
        assert "seismic" in b
        assert "flood" in b
        assert "wind" in b
        assert "all_perils" in b

    def test_blended_aal_is_weighted_average(self):
        results = self._make_results()
        b = blend_models(results)
        for peril in ["seismic", "flood", "wind"]:
            models = results[peril]
            expected = sum(
                models[m].aal * DEFAULT_BLEND_WEIGHTS[m] for m in models
            )
            assert b[peril]["blended_aal"] == pytest.approx(expected, rel=0.01)

    def test_total_aal_is_sum_of_perils(self):
        results = self._make_results()
        b = blend_models(results)
        total = sum(b[p]["blended_aal"] for p in ["seismic", "flood", "wind"])
        assert b["all_perils"]["total_aal"] == pytest.approx(total, rel=0.01)

    def test_custom_weights(self):
        results = self._make_results()
        custom = {"conservative": 1.0, "best_estimate": 0.0, "optimistic": 0.0}
        b = blend_models(results, weights=custom)
        for peril in ["seismic", "flood", "wind"]:
            cons_aal = results[peril]["conservative"].aal
            assert b[peril]["blended_aal"] == pytest.approx(cons_aal, rel=0.01)

    def test_oep_return_periods_present(self):
        results = self._make_results()
        b = blend_models(results)
        for peril in ["seismic", "flood", "wind"]:
            for rp in RETURN_PERIODS:
                assert str(rp) in b[peril]["blended_oep"]
