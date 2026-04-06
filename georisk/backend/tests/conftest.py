"""Shared fixtures for backend tests."""
import os
import tempfile
from pathlib import Path

import pytest

# Override database paths BEFORE importing any app modules so that tests
# never touch the development databases.
_tmpdir = tempfile.mkdtemp(prefix="georisk_test_")
os.environ["GEORISK_SQLITE_DB"] = str(Path(_tmpdir) / "test.db")
os.environ["GEORISK_DUCKDB_PATH"] = str(Path(_tmpdir) / "test.duckdb")
os.environ["GEORISK_CATALOG_DIR"] = str(Path(_tmpdir) / "catalog")
os.environ["GEORISK_DB_DIR"] = _tmpdir
os.environ["GEORISK_SYNTHETIC_PROPERTIES_COUNT"] = "0"

# Ensure catalog directory exists
Path(os.environ["GEORISK_CATALOG_DIR"]).mkdir(parents=True, exist_ok=True)

from app.config import settings  # noqa: E402

# Patch settings to use test paths
settings.SQLITE_DB = Path(os.environ["GEORISK_SQLITE_DB"])
settings.DUCKDB_PATH = Path(os.environ["GEORISK_DUCKDB_PATH"])
settings.CATALOG_DIR = Path(os.environ["GEORISK_CATALOG_DIR"])
settings.DB_DIR = Path(_tmpdir)

from app.models.database import init_database  # noqa: E402


@pytest.fixture(autouse=True)
def _init_test_db():
    """Initialize a fresh database for each test."""
    init_database()
    yield
