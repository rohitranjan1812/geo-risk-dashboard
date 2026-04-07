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
    session_id = r.json().get("session_id")
    assert session_id

    r2 = client.get(f"/api/cat/event-sets?session_id={session_id}&property_id=1")
    assert r2.status_code == 200
    rows = r2.json()
    assert isinstance(rows, list)
    assert len(rows) > 0

