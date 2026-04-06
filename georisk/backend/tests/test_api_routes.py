"""Integration tests for FastAPI endpoints (property, health, scenarios)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "version" in body


# ---------------------------------------------------------------------------
# Properties CRUD
# ---------------------------------------------------------------------------
class TestPropertiesAPI:
    def test_list_properties(self, client):
        resp = client.get("/api/properties/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Sample properties are loaded by init_database
        assert len(data) >= 10

    def test_get_property(self, client):
        resp = client.get("/api/properties/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 1
        assert "latitude" in body
        assert "longitude" in body

    def test_get_property_not_found(self, client):
        resp = client.get("/api/properties/99999")
        assert resp.status_code == 404

    def test_create_property(self, client):
        payload = {
            "latitude": 34.05,
            "longitude": -118.25,
            "tiv": 2_000_000,
            "construction_type": "Masonry",
            "occupancy": "Residential",
            "stories": 3,
        }
        resp = client.post("/api/properties/", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["latitude"] == 34.05
        assert body["tiv"] == 2_000_000
        assert "id" in body

    def test_delete_property(self, client):
        # Create then delete
        resp = client.post("/api/properties/", json={
            "latitude": 40.0, "longitude": -74.0,
        })
        pid = resp.json()["id"]
        resp = client.delete(f"/api/properties/{pid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_not_found(self, client):
        resp = client.delete("/api/properties/99999")
        assert resp.status_code == 404

    def test_get_property_risk(self, client):
        resp = client.get("/api/properties/1/risk")
        assert resp.status_code == 200
        body = resp.json()
        assert "composite_score" in body
        assert "risk_tier" in body
        assert body["seismic"] is not None
        assert body["flood"] is not None
        assert body["wind"] is not None


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
class TestScenariosAPI:
    def test_what_if_basic(self, client):
        payload = {
            "latitude": 37.77,
            "longitude": -122.42,
            "construction_type": "Wood Frame",
        }
        resp = client.post("/api/scenarios/what-if", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "base_case" in body
        assert "scenario" in body
        assert "delta" in body

    def test_what_if_with_overrides(self, client):
        payload = {
            "latitude": 37.77,
            "longitude": -122.42,
            "pga_override": 0.1,
            "flood_zone_override": "VE",
            "wind_prob_override": 80.0,
        }
        resp = client.post("/api/scenarios/what-if", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        scenario = body["scenario"]
        assert scenario["flood"] == 95  # VE → 95

    def test_what_if_custom_weights(self, client):
        payload = {
            "latitude": 30.0,
            "longitude": -90.0,
            "seismic_weight": 0.1,
            "flood_weight": 0.8,
            "wind_weight": 0.1,
        }
        resp = client.post("/api/scenarios/what-if", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        # Weights should be normalised
        weights = body["scenario"]["weights"]
        assert pytest.approx(sum(weights.values()), abs=0.01) == 1.0

    def test_compare_properties(self, client):
        resp = client.get("/api/scenarios/compare-properties?ids=1,2,3")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 3
        assert len(body["properties"]) == 3


# ---------------------------------------------------------------------------
# Data Catalog
# ---------------------------------------------------------------------------
class TestDataCatalogAPI:
    def test_catalog(self, client):
        resp = client.get("/api/data/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        sources = [d["source"] for d in data]
        assert "usgs_earthquake" in sources

    def test_scrape_history(self, client):
        resp = client.get("/api/data/scrape-history")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Map Layers
# ---------------------------------------------------------------------------
class TestMapLayersAPI:
    def test_list_layers(self, client):
        resp = client.get("/api/map/layers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_properties_geojson(self, client):
        resp = client.get("/api/map/properties-geojson")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) >= 10
