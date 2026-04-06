import os
import tempfile

# Override database paths BEFORE importing the app to avoid side effects on dev data.
_tmp_dir = tempfile.mkdtemp()
os.environ["GEORISK_SQLITE_DB"] = os.path.join(_tmp_dir, "test.db")
os.environ["GEORISK_DUCKDB_PATH"] = os.path.join(_tmp_dir, "test.duckdb")
os.environ["GEORISK_CATALOG_DIR"] = os.path.join(_tmp_dir, "catalog")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.database import init_database


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    os.makedirs(os.environ["GEORISK_CATALOG_DIR"], exist_ok=True)
    init_database()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")
