import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from smartops.api import create_app

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.integration


@pytest.fixture
def database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for real PostgreSQL integration tests")
    if not url.startswith("postgresql+psycopg://"):
        pytest.fail("Use the PostgreSQL Psycopg 3 dialect")
    # Only this generated schema is created/dropped. Existing tables are never cleared.
    schema = "smartops_test_" + uuid4().hex
    admin = create_engine(url, connect_args={"connect_timeout": 3})
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}", "connect_timeout": 3})
    config = Config(str(ROOT / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine, config
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_migration_write_read_and_sse_use_actual_postgresql(database):
    engine, _ = database
    with TestClient(create_app(engine=engine)) as client:
        assert client.get("/health").status_code == 200
        saved = client.post("/api/v1/system/probes")
        assert saved.status_code == 201
        assert saved.json()["persisted"] is True
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM integration_probes")) == 1
        stream = client.get("/api/v1/system/events?samples=2")
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        rows = [json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith("data: ")]
        assert [row["sequence"] for row in rows] == [1, 2]
        assert all(row["probe_count"] == 1 for row in rows)


def test_missing_migration_is_degraded_then_upgrade_recovers(database):
    engine, config = database
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    with TestClient(create_app(engine=engine)) as client:
        assert client.get("/health").status_code == 503
        assert client.post("/api/v1/system/probes").status_code == 503
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        assert client.get("/health").status_code == 200
