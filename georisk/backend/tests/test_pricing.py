from app.services.pricing import compute_technical_price


def test_pricing_outputs_expected_keys():
    blended = {
        "seismic": {"blended_aal": 10_000.0, "blended_oep": {"250": 200_000.0, "500": 350_000.0, "100": 120_000.0}},
        "flood": {"blended_aal": 5_000.0, "blended_oep": {"250": 150_000.0, "500": 250_000.0, "100": 80_000.0}},
        "wind": {"blended_aal": 7_500.0, "blended_oep": {"250": 180_000.0, "500": 300_000.0, "100": 90_000.0}},
        "all_perils": {"total_aal": 22_500.0, "total_oep": {"250": 530_000.0, "500": 900_000.0, "100": 290_000.0}},
    }
    out = compute_technical_price(10_000_000.0, blended)
    assert "total_aal" in out
    assert "technical_rate_pct" in out
    assert "peril_breakdown" in out
    assert "pml" in out
    assert out["total_aal"] > 0

