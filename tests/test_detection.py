from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from smartops.api import create_app
from smartops.detection import CONFIG, fit_reference, observe
from tests.fixtures.session import build_session
from tests.test_postgres import database


FEATURES = [{"id": "cpu_r", "label": "CPU", "group": "cpu", "unit": "normalized"}]


def reference():
    return pd.DataFrame({"sample_index": range(200), "cpu_r": [.2] * 200})


def test_training_holdout_constant_features_and_insufficient_reference():
    train = reference()
    train.loc[160:, "cpu_r"] = .3
    profile = fit_reference(train, FEATURES, "source")
    feature = profile["features"]["cpu_r"]
    assert feature["center"] == pytest.approx(.2)
    assert feature["scale"] == CONFIG["scale_floor"]
    assert feature["threshold"] == pytest.approx(100)
    assert profile["fit_count"] == 160 and profile["validation_count"] == 40
    assert "label" not in train.columns
    with pytest.raises(ValueError):
        fit_reference(train.iloc[:50], FEATURES, "source")


def test_persistence_recovery_missing_data_and_batch_invariance():
    profile = fit_reference(reference(), FEATURES, "source")
    values = [.2, .9, .2, .9, .9, .9, np.nan, .2, .2, .2, .2, .2, .9, .9, .9]
    frame = pd.DataFrame({"sample_index": range(len(values)), "cpu_r": values})
    state, transitions = observe(profile, {}, frame)
    opens = [t for t in transitions if t["kind"] == "open"]
    recoveries = [t for t in transitions if t["kind"] == "recover"]
    assert [t["detected_index"] for t in opens] == [5, 14]
    assert opens[0]["start_index"] == 3
    assert recoveries[0]["closed_index"] == 11
    assert state["cpu_r"]["alert_id"] == opens[1]["id"]
    assert opens[0]["evidence"]["value"] == .9
    incremental, events = {}, []
    for i in range(len(frame)):
        incremental, emitted = observe(profile, incremental, frame.iloc[i:i + 1])
        events.extend(emitted)
    def without_ids(items):
        return [{k: v for k, v in t.items() if k != "id"} for t in items]
    assert without_ids(events) == without_ids(transitions)


@pytest.mark.integration
def test_alerts_are_atomic_persistent_causal_and_do_not_duplicate(database, tmp_path):
    engine, _ = database
    scenario = build_session(tmp_path)
    file = tmp_path / scenario["id"] / "metrics.parquet"
    frame = pd.read_parquet(file)
    frame.cpu_r = .2
    frame.loc[3:7, "cpu_r"] = .9
    frame.to_parquet(file, index=False)
    now = [0.0]
    app = create_app(engine=engine, monitoring_dir=tmp_path, worker_enabled=False, monotonic=lambda: now[0])
    with TestClient(app) as client:
        run = client.post("/api/v1/runs", json={"request_id": str(uuid4()), "scenario_id": scenario["id"], "speed": 1}).json()
        url = f"/api/v1/runs/{run['id']}"
        key = str(uuid4())
        command = {"command_id": key, "action": "start"}
        assert client.post(url + "/commands", json=command).status_code == 200
        assert client.post(url + "/commands", json=command).status_code == 200
        assert client.get(url + "/alerts").json()["total"] == 0
        now[0] = 4
        app.state.replay.tick()
        assert client.get(url + "/alerts").json()["total"] == 0
        now[0] = 5
        app.state.replay.tick()
        result = client.get(url + "/alerts").json()
        assert result["total"] == result["active_count"] == 1
        assert result["resource_counts"]["cpu"] == {"total": 1, "active": 1}
        assert result["resource_counts"]["memory"] == {"total": 0, "active": 0}
        assert result["feature_counts"]["cpu_r"] == 1
        empty_page = client.get(url + "/alerts?resource=cpu&offset=1&limit=1").json()
        assert empty_page["items"] == [] and empty_page["total"] == 1
        assert empty_page["resource_counts"] == result["resource_counts"]
        memory = client.get(url + "/alerts?resource=memory").json()
        assert memory["total"] == 0 and memory["items"] == []
        assert memory["active_count"] == 1  # global counter is independent of the filter
        assert memory["feature_counts"] == result["feature_counts"]
        assert client.get(url + "/alerts?resource=unknown").status_code == 422
        alert = result["items"][0]
        assert alert["detected_index"] == result["analyzed_index"] == 5
        assert alert["evidence"]["sample_index"] <= result["cursor_index"]
        assert alert["evidence"]["reference_median"] == pytest.approx(.2)
        app.state.replay.tick()
        assert client.get(url + "/alerts").json() == result
        now[0] = 12
        app.state.replay.tick()
        result = client.get(url + "/alerts").json()
        assert result["active_count"] == 0 and result["items"][0]["status"] == "recovered"
        assert result["items"][0]["closed_index"] == 12
        assert client.get(url).json()["analyzed_index"] == 12
    with TestClient(create_app(engine=engine, monitoring_dir=tmp_path, worker_enabled=False)) as restarted:
        assert restarted.get(url + "/alerts").json()["total"] == 1
        assert restarted.get(url).json()["status"] == "interrupted"


@pytest.mark.integration
def test_missing_training_reference_refuses_analysis_instead_of_using_test(database, tmp_path):
    engine, _ = database
    scenario = build_session(tmp_path)
    (tmp_path / scenario["id"] / "reference.parquet").unlink()
    with TestClient(create_app(engine=engine, monitoring_dir=tmp_path, worker_enabled=False)) as client:
        run = client.post("/api/v1/runs", json={"request_id": str(uuid4()), "scenario_id": scenario["id"], "speed": 1}).json()
        response = client.post(f"/api/v1/runs/{run['id']}/commands", json={"command_id": str(uuid4()), "action": "start"})
        assert response.status_code == 503 and response.json()["error"]["code"] == "REFERENCE_UNAVAILABLE"
        assert client.get(f"/api/v1/runs/{run['id']}").json()["cursor_index"] is None


@pytest.mark.integration
def test_failed_alert_commit_rolls_back_cursor_and_evidence(database, tmp_path, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    from smartops.storage import Alert
    engine, _ = database
    scenario = build_session(tmp_path)
    file = tmp_path / scenario["id"] / "metrics.parquet"
    frame = pd.read_parquet(file)
    frame.cpu_r = .2
    frame.loc[3:7, "cpu_r"] = .9
    frame.to_parquet(file, index=False)
    now = [0.]
    app = create_app(engine=engine, monitoring_dir=tmp_path, worker_enabled=False, monotonic=lambda: now[0])
    with TestClient(app) as client:
        run = client.post("/api/v1/runs", json={"request_id": str(uuid4()), "scenario_id": scenario["id"], "speed": 1}).json()
        url = f"/api/v1/runs/{run['id']}"
        assert client.post(url + "/commands", json={"command_id": str(uuid4()), "action": "start"}).status_code == 200
        original = Session.commit
        original_flush = Session.flush
        def track_alert_flush(session, *args, **kwargs):
            if any(isinstance(item, Alert) for item in session.new):
                session.info["alert_transaction"] = True
            return original_flush(session, *args, **kwargs)
        def fail_alert_transaction(session):
            if session.info.get("alert_transaction"):
                raise SQLAlchemyError("private transaction failure")
            return original(session)
        monkeypatch.setattr(Session, "flush", track_alert_flush)
        monkeypatch.setattr(Session, "commit", fail_alert_transaction)
        now[0] = 5
        response = client.post(url + "/commands", json={"command_id": str(uuid4()), "action": "pause"})
        assert response.status_code == 503 and "private" not in response.text
        saved = client.get(url).json()
        assert saved["cursor_index"] == saved["analyzed_index"] == 0
        assert saved["status"] == "interrupted"
        assert client.get(url + "/alerts").json()["total"] == 0
