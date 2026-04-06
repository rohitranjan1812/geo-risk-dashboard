"""Tests for security hardening changes."""
import os
import json
import pytest
from pydantic import ValidationError


class TestPathTraversal:
    """Test that load_geojson blocks directory traversal."""

    def test_blocks_parent_directory_traversal(self):
        from app.services.geo_processor import load_geojson

        result = load_geojson("../../../etc/passwd")
        assert result is None

    def test_blocks_absolute_path(self):
        from app.services.geo_processor import load_geojson

        result = load_geojson("/etc/passwd")
        assert result is None

    def test_blocks_dot_dot_sequence(self):
        from app.services.geo_processor import load_geojson

        result = load_geojson("../../backend/app/config.py")
        assert result is None

    def test_allows_valid_filename(self):
        from app.services.geo_processor import load_geojson

        # Non-existent but safe filename should return None (file not found)
        result = load_geojson("valid_file.geojson")
        assert result is None

    def test_allows_valid_file_with_content(self, tmp_path):
        from app.config import settings

        catalog_dir = settings.CATALOG_DIR
        os.makedirs(catalog_dir, exist_ok=True)
        test_file = catalog_dir / "test_valid.geojson"
        test_data = {"type": "FeatureCollection", "features": []}
        test_file.write_text(json.dumps(test_data))

        from app.services.geo_processor import load_geojson

        result = load_geojson("test_valid.geojson")
        assert result is not None
        assert result["type"] == "FeatureCollection"

        # Cleanup
        test_file.unlink(missing_ok=True)


class TestCSVSanitization:
    """Test that CSV formula injection is prevented."""

    def test_sanitize_formula_with_equals(self):
        from app.api.routes_portfolio import _sanitize_csv_cell

        assert _sanitize_csv_cell("=CMD('calc')") == "'=CMD('calc')"

    def test_sanitize_formula_with_plus(self):
        from app.api.routes_portfolio import _sanitize_csv_cell

        assert _sanitize_csv_cell("+1+1") == "'+1+1"

    def test_sanitize_formula_with_minus(self):
        from app.api.routes_portfolio import _sanitize_csv_cell

        assert _sanitize_csv_cell("-1+1") == "'-1+1"

    def test_sanitize_formula_with_at(self):
        from app.api.routes_portfolio import _sanitize_csv_cell

        assert _sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"

    def test_sanitize_formula_with_tab(self):
        from app.api.routes_portfolio import _sanitize_csv_cell

        assert _sanitize_csv_cell("\tcmd") == "'\tcmd"

    def test_sanitize_formula_with_cr(self):
        from app.api.routes_portfolio import _sanitize_csv_cell

        assert _sanitize_csv_cell("\rcmd") == "'\rcmd"

    def test_safe_string_unchanged(self):
        from app.api.routes_portfolio import _sanitize_csv_cell

        assert _sanitize_csv_cell("normal text") == "normal text"

    def test_number_unchanged(self):
        from app.api.routes_portfolio import _sanitize_csv_cell

        assert _sanitize_csv_cell(42) == 42

    def test_empty_string_unchanged(self):
        from app.api.routes_portfolio import _sanitize_csv_cell

        assert _sanitize_csv_cell("") == ""

    def test_none_unchanged(self):
        from app.api.routes_portfolio import _sanitize_csv_cell

        assert _sanitize_csv_cell(None) is None


class TestFileUploadSecurity:
    """Test file upload size and type validation."""

    @pytest.mark.anyio
    async def test_rejects_non_csv_file(self, client):
        from httpx import AsyncClient

        response = await client.post(
            "/api/portfolio/upload",
            files={"file": ("test.txt", b"data", "text/plain")},
        )
        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_rejects_no_filename(self, client):
        response = await client.post(
            "/api/portfolio/upload",
            files={"file": ("test.json", b"data", "application/json")},
        )
        assert response.status_code == 400

    @pytest.mark.anyio
    async def test_rejects_oversized_file(self, client):
        large_content = b"x" * (10 * 1024 * 1024 + 1)  # Just over 10 MB
        response = await client.post(
            "/api/portfolio/upload",
            files={"file": ("test.csv", large_content, "text/csv")},
        )
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()


class TestDebugMode:
    """Test that debug mode defaults to False."""

    def test_debug_defaults_to_false(self):
        from app.config import Settings

        s = Settings()
        assert s.DEBUG is False


class TestCORSConfig:
    """Test CORS configuration is restricted."""

    def test_cors_methods_not_wildcard(self):
        from app.main import app

        for middleware in app.user_middleware:
            if hasattr(middleware, "kwargs"):
                methods = middleware.kwargs.get("allow_methods", [])
                if methods:
                    assert "*" not in methods, "CORS should not allow wildcard methods"


class TestFilterRequestValidation:
    """Test that FilterRequest validates page/page_size bounds."""

    def test_default_values(self):
        from app.api.routes_synthetic import FilterRequest

        f = FilterRequest()
        assert f.page == 1
        assert f.page_size == 100

    def test_rejects_zero_page(self):
        from app.api.routes_synthetic import FilterRequest

        with pytest.raises(ValidationError):
            FilterRequest(page=0)

    def test_rejects_negative_page(self):
        from app.api.routes_synthetic import FilterRequest

        with pytest.raises(ValidationError):
            FilterRequest(page=-1)

    def test_rejects_oversized_page_size(self):
        from app.api.routes_synthetic import FilterRequest

        with pytest.raises(ValidationError):
            FilterRequest(page_size=5000)

    def test_rejects_zero_page_size(self):
        from app.api.routes_synthetic import FilterRequest

        with pytest.raises(ValidationError):
            FilterRequest(page_size=0)
