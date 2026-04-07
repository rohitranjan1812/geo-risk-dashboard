from app.services.diversification import compute_diversification


def test_diversification_basic_outputs():
    props = [
        {
            "property_id": 1,
            "tiv": 1_000_000.0,
            "blended": {
                "seismic": {"blended_oep": {"250": 100_000.0}, "blended_aal": 5_000.0},
                "flood": {"blended_oep": {"250": 50_000.0}, "blended_aal": 2_000.0},
                "wind": {"blended_oep": {"250": 75_000.0}, "blended_aal": 3_000.0},
            },
        },
        {
            "property_id": 2,
            "tiv": 2_000_000.0,
            "blended": {
                "seismic": {"blended_oep": {"250": 120_000.0}, "blended_aal": 6_000.0},
                "flood": {"blended_oep": {"250": 60_000.0}, "blended_aal": 2_500.0},
                "wind": {"blended_oep": {"250": 90_000.0}, "blended_aal": 3_500.0},
            },
        },
    ]
    out = compute_diversification(props, return_period=250)
    assert out["n_properties"] == 2
    assert out["portfolio_pml"] > 0
    assert "accounts" in out and len(out["accounts"]) == 2

