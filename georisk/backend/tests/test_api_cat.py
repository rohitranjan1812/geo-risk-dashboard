from fastapi.testclient import TestClient

from app.main import app
from app.models.database import init_database, get_duckdb_conn


def _seed_min_cat_portfolio() -> str:
    init_database()
    duck = get_duckdb_conn()
    # Seed a few synthetic properties and build a portfolio
    duck.execute("DELETE FROM synthetic_properties")
    duck.execute(
        """
        INSERT INTO synthetic_properties
        VALUES
          (1, 37.77, -122.42, 1000000, 'Wood Frame', 'Residential', 1990, 1),
          (2, 29.76, -95.37, 2000000, 'Steel Frame', 'Commercial', 2005, 5),
          (3, 25.76, -80.19, 1500000, 'Reinforced Concrete', 'Residential', 2010, 8)
        """
    )
    duck.execute("DELETE FROM cat_portfolios")
    duck.execute("DELETE FROM cat_portfolio_members")
    duck.execute("INSERT INTO cat_portfolios (portfolio_id, name, filter_criteria) VALUES ('ptest', 'ptest', '{}')")
    duck.execute("INSERT INTO cat_portfolio_members (portfolio_id, property_id) VALUES ('ptest', 1), ('ptest', 2), ('ptest', 3)")
    duck.close()
    return "ptest"


def test_cat_run_model_and_event_sets():
    portfolio_id = _seed_min_cat_portfolio()
    client = TestClient(app)
    r = client.post("/api/cat/run-model", json={"portfolio_id": portfolio_id, "n_years": 2000, "max_properties": 3})
    assert r.status_code == 200
    body = r.json()
    session_id = body.get("session_id")
    assert session_id

    # /run-model must now also return EP curves so the frontend does not need
    # a second full-simulation round-trip ("stuck during analysis" fix).
    assert "ep_curves" in body and body["ep_curves"], "run-model must return ep_curves"
    curves = body["ep_curves"]
    for peril in ("seismic", "flood", "wind", "all_perils"):
        assert peril in curves, f"missing peril curve: {peril}"
    assert isinstance(curves["all_perils"].get("oep"), list) and curves["all_perils"]["oep"]

    assert "diversification" in body

    r2 = client.get(f"/api/cat/event-sets?session_id={session_id}&property_id=1")
    assert r2.status_code == 200
    rows = r2.json()
    assert isinstance(rows, list)
    assert len(rows) > 0


def test_ep_curve_and_diversification_served_from_session_cache():
    """After /run-model persists a session, /ep-curve and /diversification
    should serve from the persisted cat_results without re-simulating.

    We assert the endpoints respond well under a tight timeout — a fresh
    stochastic simulation would be orders of magnitude slower than a
    cat_results lookup."""
    import time
    portfolio_id = _seed_min_cat_portfolio()
    client = TestClient(app)
    r = client.post("/api/cat/run-model", json={"portfolio_id": portfolio_id, "n_years": 2000, "max_properties": 3})
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    t0 = time.perf_counter()
    rep = client.get(f"/api/cat/ep-curve/{portfolio_id}", params={"session_id": session_id})
    ep_elapsed = time.perf_counter() - t0
    assert rep.status_code == 200
    ep = rep.json()
    assert "all_perils" in ep and ep["all_perils"].get("oep")

    t0 = time.perf_counter()
    rdv = client.get(f"/api/cat/diversification/{portfolio_id}", params={"session_id": session_id})
    dv_elapsed = time.perf_counter() - t0
    assert rdv.status_code == 200
    dv = rdv.json()
    assert "portfolio_pml" in dv

    # Session-cached reads must be dramatically faster than a fresh simulation
    # (which for 3 properties × 2000 years takes ~1–2 s even on fast CPUs).
    # Use a generous 1.5 s cap so this stays reliable on slow CI.
    assert ep_elapsed < 1.5, f"/ep-curve with session_id took {ep_elapsed:.2f}s — not using cache?"
    assert dv_elapsed < 1.5, f"/diversification with session_id took {dv_elapsed:.2f}s — not using cache?"


def test_get_session_hydrates_full_ui_payload():
    """GET /cat/sessions/{id} must return ep_curves, diversification and a
    flat property_rows list so that 'Load Session' in the UI shows the full
    dashboard without firing another simulation."""
    portfolio_id = _seed_min_cat_portfolio()
    client = TestClient(app)
    r = client.post("/api/cat/run-model", json={"portfolio_id": portfolio_id, "n_years": 2000, "max_properties": 3})
    session_id = r.json()["session_id"]

    r2 = client.get(f"/api/cat/sessions/{session_id}")
    assert r2.status_code == 200
    body = r2.json()
    assert body.get("ep_curves") and body["ep_curves"].get("all_perils")
    assert body.get("diversification") and "portfolio_pml" in body["diversification"]
    assert isinstance(body.get("property_rows"), list) and body["property_rows"]
    # Flat rows use the run-model response shape.
    row = body["property_rows"][0]
    for key in ("property_id", "tiv", "total_aal", "technical_rate_pct", "pml_250"):
        assert key in row, f"property_rows[0] missing {key}"


def test_compare_uses_persisted_session_data():
    """Comparing sessions must not re-run stochastic simulations — it should
    consume persisted cat_results so it responds quickly even for many sessions."""
    import time
    portfolio_id = _seed_min_cat_portfolio()
    client = TestClient(app)
    sids = []
    for _ in range(2):
        r = client.post("/api/cat/run-model", json={"portfolio_id": portfolio_id, "n_years": 2000, "max_properties": 3})
        sids.append(r.json()["session_id"])

    t0 = time.perf_counter()
    rc = client.get(f"/api/cat/compare?session_ids={','.join(sids)}")
    elapsed = time.perf_counter() - t0
    assert rc.status_code == 200
    body = rc.json()
    assert set(body["ep_curves"].keys()) == set(sids)
    # Two independent simulations would take several seconds combined; the
    # persisted-path should be well under 1 s even on slow CI.
    assert elapsed < 1.5, f"/compare took {elapsed:.2f}s — not using persisted session data?"

