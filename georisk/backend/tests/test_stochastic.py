import numpy as np

from app.services.stochastic import run_stochastic_for_location


def test_oep_aep_differ_when_multiple_events_possible():
    lat, lon = 37.77, -122.42
    tiv = 1_000_000.0
    # Use a high-hazard setup to make multiple events per year more likely.
    raw = run_stochastic_for_location(
        lat, lon, tiv,
        construction="Wood Frame",
        occupancy="Residential",
        stories=1,
        pga=0.8,
        flood_zone="V",
        wind_prob=80.0,
        n_years=2000,
        seed=123,
        collect_events=False,
    )
    # Validate that at least one peril/model has OEP and AEP that are not identical for some RP.
    found_diff = False
    for peril_models in raw.values():
        for res in peril_models.values():
            for rp in [100, 250, 500]:
                o = float(res.oep.get(rp, 0.0))
                a = float(res.aep.get(rp, 0.0))
                if abs(o - a) > 1e-9:
                    found_diff = True
                    break
            if found_diff:
                break
        if found_diff:
            break
    assert found_diff, "Expected OEP and AEP to differ for at least one RP in a multi-event setting"


def test_event_sample_shape_when_collected():
    lat, lon = 29.76, -95.37
    raw = run_stochastic_for_location(
        lat, lon, tiv=5_000_000.0,
        construction="Steel Frame",
        occupancy="Commercial",
        stories=5,
        pga=0.4,
        flood_zone="AE",
        wind_prob=50.0,
        n_years=2000,
        seed=7,
        collect_events=True,
        top_k_events=10,
        random_k_events=10,
    )
    any_sample = False
    for peril_models in raw.values():
        for res in peril_models.values():
            if res.event_sample:
                any_sample = True
                ev = res.event_sample[0]
                assert {"year", "event_index", "intensity", "mean_dr", "dr", "loss"} <= set(ev.keys())
                assert isinstance(res.intensity_unit, str) and len(res.intensity_unit) > 0
                break
        if any_sample:
            break
    assert any_sample

