"""Tests for app.services.diversification – portfolio risk metrics."""
import pytest

from app.services.diversification import compute_diversification, _herfindahl_index


# ---------------------------------------------------------------------------
# _herfindahl_index
# ---------------------------------------------------------------------------
class TestHerfindahl:
    def test_single_value(self):
        assert _herfindahl_index([100]) == pytest.approx(1.0)

    def test_equal_distribution(self):
        # 4 equal values → HHI = 4 * (1/4)^2 = 0.25
        assert _herfindahl_index([100, 100, 100, 100]) == pytest.approx(0.25)

    def test_concentrated(self):
        # One dominant → HHI close to 1
        hhi = _herfindahl_index([1000, 1, 1, 1])
        assert hhi > 0.9

    def test_empty(self):
        assert _herfindahl_index([]) == 0.0

    def test_all_zero(self):
        assert _herfindahl_index([0, 0, 0]) == 0.0


# ---------------------------------------------------------------------------
# compute_diversification
# ---------------------------------------------------------------------------
def _make_property_result(pid, pml_seismic, pml_flood, pml_wind,
                          aal_seismic=0, aal_flood=0, aal_wind=0, tiv=1_000_000):
    return {
        "property_id": pid,
        "tiv": tiv,
        "blended": {
            "seismic": {
                "blended_oep": {"250": pml_seismic},
                "blended_aal": aal_seismic,
            },
            "flood": {
                "blended_oep": {"250": pml_flood},
                "blended_aal": aal_flood,
            },
            "wind": {
                "blended_oep": {"250": pml_wind},
                "blended_aal": aal_wind,
            },
        },
    }


class TestComputeDiversification:
    def test_empty_returns_error(self):
        result = compute_diversification([])
        assert "error" in result

    def test_single_property(self):
        props = [_make_property_result(1, 100, 200, 50, 10, 20, 5)]
        result = compute_diversification(props, return_period=250)
        assert result["n_properties"] == 1
        assert result["portfolio_pml"] > 0
        assert result["diversification_benefit"] == 0.0  # no diversification with 1

    def test_multiple_properties_benefit(self):
        props = [
            _make_property_result(1, 1000, 500, 200, tiv=1_000_000),
            _make_property_result(2, 800, 600, 300, tiv=2_000_000),
            _make_property_result(3, 200, 100, 900, tiv=500_000),
        ]
        result = compute_diversification(props)
        assert result["n_properties"] == 3
        # Portfolio PML should be less than sum of standalone
        assert result["portfolio_pml"] < result["sum_standalone_pml"]
        assert result["diversification_benefit"] > 0
        assert result["diversification_pct"] > 0

    def test_hhi_populated(self):
        props = [
            _make_property_result(1, 100, 100, 100, tiv=1_000_000),
            _make_property_result(2, 100, 100, 100, tiv=1_000_000),
        ]
        result = compute_diversification(props)
        assert "hhi_concentration" in result
        # Two equal TIVs → HHI = 0.5
        assert result["hhi_concentration"] == pytest.approx(0.5, abs=0.01)

    def test_accounts_sorted_by_standalone(self):
        props = [
            _make_property_result(1, 100, 50, 50),
            _make_property_result(2, 500, 200, 100),
            _make_property_result(3, 300, 100, 80),
        ]
        result = compute_diversification(props)
        accounts = result["accounts"]
        for i in range(len(accounts) - 1):
            assert accounts[i]["standalone_pml"] >= accounts[i + 1]["standalone_pml"]
