from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from smartops.api import create_app


def test_health_reports_database_failure_without_leaking_driver_details():
    engine = Mock()
    engine.connect.side_effect = RuntimeError("private connection details")
    with TestClient(create_app(engine=engine)) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["api"] == "available"
    assert response.json()["database"] == "unavailable"
    assert "private" not in response.text


def test_stream_rejects_missing_database_before_sending_events():
    engine = Mock()
    engine.connect.side_effect = RuntimeError("private")
    with TestClient(create_app(engine=engine)) as client:
        response = client.get("/api/v1/system/events?samples=1")
    assert response.status_code == 503
    assert "text/event-stream" not in response.headers["content-type"]
    assert "private" not in response.text


def test_failed_probe_does_not_report_success(monkeypatch):
    def failing_session(*args, **kwargs):
        raise OperationalError("private sql", {}, Exception("private driver details"))

    monkeypatch.setattr("smartops.api.Session", failing_session)
    with TestClient(create_app(engine=Mock())) as client:
        response = client.post("/api/v1/system/probes")
    assert response.status_code == 503
    assert "persisted" not in response.json()
    assert "private" not in response.text
