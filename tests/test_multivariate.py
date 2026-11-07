import json
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from smartops.api import create_app
from smartops.detection import fit_reference, observe
from smartops.multivariate import fit_multivariate
from tests.fixtures.session import build_session
from tests.test_postgres import database

FEATURES = [{"id": n, "label": n, "group": "cpu", "unit": "normalized"} for n in ["x", "y", "constant"]]


def training():
    x = .5 + .1 * np.sin(np.linspace(0, 20 * np.pi, 1000))
    return pd.DataFrame({"sample_index": range(1000), "x": x, "y": x, "constant": [.5] * 1000})


def test_joint_model_detects_broken_correlation_with_no_individual_outlier():
    frame = training()
    joint = fit_multivariate(frame, FEATURES, "source")
    baseline = fit_reference(frame, FEATURES, "source")
    unusual = pd.DataFrame({"sample_index": range(3), "x": [.65] * 3, "y": [.35] * 3, "constant": [.5] * 3})
    _, individual = observe(baseline, {}, unusual)
    _, combined = observe(joint, {}, unusual)
    assert not [t for t in individual if t["kind"] == "open"]
    opened = [t for t in combined if t["kind"] == "open"]
    assert len(opened) == 1 and opened[0]["detected_index"] == 2
    assert opened[0]["evidence"]["method"] == "pca-joint-v1"
    assert len(opened[0]["evidence"]["contributors"]) == 3
    assert joint["fit_count"] == 800 and joint["validation_count"] == 200
    restored = json.loads(json.dumps(joint, allow_nan=False, sort_keys=True))
    assert restored["fingerprint"] == joint["fingerprint"]
    assert [t["kind"] for t in observe(restored, {}, unusual)[1]] == [t["kind"] for t in combined]
    original_alert = next(t for t in combined if t["kind"] == "open")
    restored_alert = next(t for t in observe(restored, {}, unusual)[1] if t["kind"] == "open")
    assert original_alert["evidence"] == restored_alert["evidence"]


def test_joint_state_is_batch_invariant_and_handles_constant_reference_and_missing():
    frame = training()
    frame.loc[:, ["x", "y", "constant"]] = .5
    profile = fit_multivariate(frame, FEATURES, "source")
    assert profile["pca"]["rank"] == 0
    probe = pd.DataFrame({"sample_index": range(12), "x": [.9] * 3 + [np.nan] + [.5] * 8,
                          "y": [.9] * 3 + [.5] * 9, "constant": [.5] * 12})
    _, whole = observe(profile, {}, probe)
    state, partial = {}, []
    for index in range(len(probe)):
        state, events = observe(profile, state, probe.iloc[index:index + 1])
        partial.extend(events)
    cleaned = lambda events: [{k: v for k, v in e.items() if k != "id"} for e in events]
    assert cleaned(whole) == cleaned(partial)
    assert next(e["closed_index"] for e in whole if e["kind"] == "recover") == 8
    assert np.isfinite(profile["pca"]["q_threshold"])


@pytest.mark.integration
def test_detector_choice_is_persistent_idempotent_and_validated(database, tmp_path):
    engine, _ = database
    scenario = build_session(tmp_path)
    now = [0.]
    with TestClient(create_app(engine=engine, monitoring_dir=tmp_path, worker_enabled=False, monotonic=lambda: now[0])) as client:
        body = {"request_id": str(uuid4()), "scenario_id": scenario["id"], "speed": 10, "detector_name": "pca-joint-v1"}
        response = client.post("/api/v1/runs", json=body)
        assert response.status_code == 201
        run = response.json()
        assert run["detector_name"] == "pca-joint-v1"
        assert client.post("/api/v1/runs", json=body).status_code == 200
        assert client.post("/api/v1/runs", json={**body, "detector_name": "robust-mad-v1"}).status_code == 409
        assert client.post("/api/v1/runs", json={**body, "detector_name": "unknown"}).status_code == 422
        endpoint = f"/api/v1/runs/{run['id']}"
        started = client.post(endpoint + "/commands", json={"command_id": str(uuid4()), "action": "start"})
        assert started.json()["detector_version"] == "pca-joint-v1"
        now[0] = 1
        client.post(endpoint + "/commands", json={"command_id": str(uuid4()), "action": "pause"})
        alerts = client.get(endpoint + "/alerts").json()
        assert alerts["detector_version"] == "pca-joint-v1" and alerts["analyzed_index"] == 10
        assert alerts["total"] >= 1
