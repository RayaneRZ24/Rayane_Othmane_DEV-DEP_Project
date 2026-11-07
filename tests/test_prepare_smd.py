import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.prepare_smd import prepare
from smartops.telemetry import Registry

ROOT = Path(__file__).resolve().parents[1]


def test_prepare_smd_preserves_partitions_and_isolates_annotations(tmp_path):
    config = json.loads((ROOT / "config/dataset.json").read_text())
    config.update(expected_machines=1, expected_train_rows=3, expected_test_rows=5)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/dataset.json").write_text(json.dumps(config))
    dictionary = (ROOT / config["feature_dictionary"]).read_bytes()
    (tmp_path / config["feature_dictionary"]).write_bytes(dictionary)
    raw = tmp_path / config["raw_directory"]
    for split, count in [("train", 3), ("test", 5)]:
        (raw / split).mkdir(parents=True)
        pd.DataFrame(np.full((count, 38), .2 if split == "train" else .7)).to_csv(raw / split / "machine-1-1.txt", header=False, index=False)
    for split, content in [("test_label", "0\n1\n1\n0\n0\n"), ("interpretation_label", "1-3:1\n")]:
        (raw / split).mkdir()
        (raw / split / "machine-1-1.txt").write_text(content)
    scenarios = prepare(tmp_path)
    identifier = scenarios[0]["id"]
    public = tmp_path / "data/monitoring-smd"
    series = Registry(public).load(identifier)
    assert len(series.metrics) == 5 and series.metrics.cpu_r.eq(.7).all()
    assert pd.read_parquet(public / identifier / "reference.parquet").cpu_r.eq(.2).all()
    assert set(series.metrics.columns) == {"sample_index", *[f["id"] for f in scenarios[0]["features"]]}
    assert sorted(p.name for p in (public / identifier).iterdir()) == ["metrics.parquet", "reference.parquet"]
    private = tmp_path / "data/evaluation-smd" / identifier
    assert pd.read_parquet(private / "labels.parquet").is_anomaly.tolist() == [0, 1, 1, 0, 0]
    before = series.metrics.copy()
    (raw / "test_label/machine-1-1.txt").write_text("1\n0\n0\n1\n1\n")
    assert prepare(tmp_path)[0]["id"] == identifier
    pd.testing.assert_frame_equal(Registry(public).load(identifier).metrics, before)
    assert all(word not in (public / "registry.json").read_text() for word in ["is_anomaly", "test_label", "interpretation_label"])
