import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from smartops.api import create_app
from smartops.replay import ReplayClock, ReplayError, ReplayManager
from smartops.telemetry import Registry
from tests.fixtures.session import build_session
from tests.test_postgres import database


def test_sample_clock_speed_and_fractional_resume():
    slow, fast = ReplayClock(1, 0), ReplayClock(10, 0)
    assert slow.elapsed_samples(10) == fast.elapsed_samples(1) == 10
    fractional = ReplayClock(1, 0)
    assert fractional.elapsed_samples(.4) == 0
    assert fractional.elapsed_samples(1.1) == 1
    fractional.last = 100
    assert fractional.elapsed_samples(100.9) == 1


def test_reader_preserves_missing_values_and_rejects_label_columns(tmp_path):
    scenario = build_session(tmp_path)
    data = Registry(tmp_path).load(scenario["id"])
    metrics, _ = data.metric_page("cpu_r", 0, 4, 0, 50)
    assert metrics[-1] == {"sample_index": 4, "value": None, "observed": False}
    with pytest.raises(KeyError):
        data.metric_page("is_anomaly", 0, 4, 0, 50)
    data.metrics["is_anomaly"] = 1
    data.metrics.to_parquet(tmp_path / scenario["id"] / "metrics.parquet", index=False)
    with pytest.raises(ValueError, match="schema"):
        Registry(tmp_path).load(scenario["id"])


@pytest.mark.integration
def test_replay_pause_pagination_no_future_or_annotations(database, tmp_path):
    engine, _ = database
    scenario = build_session(tmp_path)
    now = [0.0]
    app = create_app(engine=engine, monitoring_dir=tmp_path, worker_enabled=False, monotonic=lambda: now[0])
    with TestClient(app) as client:
        body = {"request_id": str(uuid4()), "scenario_id": scenario["id"], "speed": 10}
        created = client.post("/api/v1/runs", json=body)
        run = created.json()
        assert created.status_code == 201
        assert client.post("/api/v1/runs", json=body).status_code == 200
        assert client.post("/api/v1/runs", json={**body, "speed": 20}).status_code == 409
        identifier = run["id"]
        endpoint = f"/api/v1/runs/{identifier}"
        url = endpoint + "/metrics?feature=cpu_r&to_index=99999"
        assert client.get(url).json()["items"] == []
        assert client.get(endpoint + "/metrics?feature=is_anomaly").status_code == 404
        assert client.get(endpoint + "/metrics?feature=cpu_r&from_index=-1").status_code == 422

        def command(action, key=None):
            return client.post(endpoint + "/commands", json={"command_id": key or str(uuid4()), "action": action})

        key = str(uuid4())
        assert command("start", key).json()["cursor_index"] == 0
        assert command("start", key).status_code == 200
        now[0] = 1
        app.state.replay.tick()
        page = client.get(url).json()
        assert page["effective_to_index"] == 10
        assert max(x["sample_index"] for x in page["items"]) <= 10
        paused = command("pause").json()
        before = client.get(url).json()
        now[0] = 100
        app.state.replay.tick()
        assert client.get(url).json() == before
        assert client.get(endpoint).json()["cursor_index"] == paused["cursor_index"]

        first = client.get(url + "&limit=2").json()
        assert first["next_cursor"]
        assert command("resume").status_code == 200
        now[0] = 101
        app.state.replay.tick()
        second = client.get(endpoint + "/metrics", params={"feature": "cpu_r", "to_index": 99999, "limit": 2, "cursor": first["next_cursor"]}).json()
        assert second["effective_to_index"] == first["effective_to_index"]
        assert {x["sample_index"] for x in first["items"]}.isdisjoint(x["sample_index"] for x in second["items"])
        assert client.get(endpoint + "/metrics", params={"feature": "cpu_r", "to_index": 99999, "cursor": "tampered"}).status_code == 409
        assert client.get(endpoint + "/metrics", params={"feature": "mem_u", "to_index": 99999, "cursor": first["next_cursor"]}).status_code == 409
        frozen = client.get(url).json()
        data = app.state.replay.cache
        data.metrics.loc[data.metrics.sample_index > frozen["effective_to_index"], "cpu_r"] = .99
        assert client.get(url).json() == frozen
        public = client.get("/api/v1/scenarios").text + json.dumps(run)
        assert all(word not in public for word in ["is_anomaly", "test_label", "interpretation_label", "raw_directory"])
        assert "cursor_ms" not in public
        assert client.get(endpoint + "/logs").status_code == 404

        stream = client.get(endpoint + "/events?samples=1")
        assert "event: run.updated" in stream.text
        event_id = next(line[4:] for line in stream.text.splitlines() if line.startswith("id: "))
        command("stop")
        resumed = client.get(endpoint + "/events?samples=1", headers={"Last-Event-ID": event_id})
        assert '"stopped"' in resumed.text


@pytest.mark.integration
def test_single_active_run_completion_and_restart_recovery(database, tmp_path):
    engine, _ = database
    scenario = build_session(tmp_path)
    now = [0.0]
    manager = ReplayManager(engine, tmp_path, monotonic=lambda: now[0])
    one, _ = manager.create(uuid4(), scenario["id"], 60)
    two, _ = manager.create(uuid4(), scenario["id"], 10)
    manager.command(one["id"], uuid4(), "start")
    with pytest.raises(ReplayError) as conflict:
        manager.command(two["id"], uuid4(), "start")
    assert conflict.value.status == 409
    now[0] = 20
    manager.tick()
    assert manager.read(one["id"])["status"] == "completed"
    assert manager.read(one["id"])["cursor_index"] == scenario["end_index"]
    manager.command(two["id"], uuid4(), "start")
    restarted = ReplayManager(engine, tmp_path)
    assert restarted.read(two["id"])["status"] == "interrupted"
