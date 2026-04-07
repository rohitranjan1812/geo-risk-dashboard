import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _set_test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Ensure each test run uses isolated SQLite + DuckDB paths.
    This avoids touching developer-local databases and makes tests deterministic.
    """
    base = tmp_path / "db"
    base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GEORISK_SQLITE_DB", str(base / "georisk_test.sqlite"))
    monkeypatch.setenv("GEORISK_DUCKDB_PATH", str(base / "georisk_test.duckdb"))
    monkeypatch.setenv("GEORISK_SYNTHETIC_PROPERTIES_COUNT", "0")
    yield

