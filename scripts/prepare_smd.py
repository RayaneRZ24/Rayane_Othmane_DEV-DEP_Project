"""Prepare SMD observations and keep all evaluation annotations out of monitoring."""
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def write_parquet(path, frame):
    temporary = path.with_suffix(".tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def prepare(root=ROOT):
    config = json.loads((root / "config/dataset.json").read_text(encoding="utf-8"))
    dictionary = json.loads((root / config["feature_dictionary"]).read_text(encoding="utf-8"))["features"]
    features = [{"id": f["source_name"], "label": f["label"], "group": f["group"], "unit": "normalized"} for f in dictionary]
    names = [f["id"] for f in features]
    if config["name"] != "SMD" or len(names) != config["expected_dimensions"] or len(set(names)) != len(names):
        raise ValueError("Invalid SMD dictionary")
    raw = root / config["raw_directory"]
    train_files = sorted((raw / "train").glob("machine-*.txt"))
    if len(train_files) != config["expected_machines"]:
        raise ValueError("Incomplete SMD machine inventory")
    public = root / "data/monitoring-smd"
    private = root / "data/evaluation-smd"
    scenarios, total_train, total_test = [], 0, 0
    for source in train_files:
        machine = source.stem
        identifier = str(uuid5(NAMESPACE_URL, f"SMD/{config['revision']}/{machine}/test/schema2"))
        folder, evaluation = public / identifier, private / identifier
        folder.mkdir(parents=True, exist_ok=True)
        evaluation.mkdir(parents=True, exist_ok=True)
        frames = {}
        for split in ["train", "test"]:
            frame = pd.read_csv(raw / split / source.name, header=None)
            values = frame.to_numpy(dtype=float)
            if frame.shape[1] != len(names) or not len(frame) or not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
                raise ValueError(f"Invalid SMD metrics: {machine}/{split}")
            frame.columns = names
            frame.insert(0, "sample_index", np.arange(len(frame), dtype="int64"))
            frames[split] = frame
        labels = pd.read_csv(raw / "test_label" / source.name, header=None).iloc[:, 0]
        if len(labels) != len(frames["test"]) or not labels.isin([0, 1]).all():
            raise ValueError("Invalid or misaligned evaluation labels")
        write_parquet(folder / "metrics.parquet", frames["test"])
        write_parquet(folder / "reference.parquet", frames["train"])
        write_parquet(evaluation / "labels.parquet", pd.DataFrame({"sample_index": np.arange(len(labels)), "is_anomaly": labels}))
        interpretations = (raw / "interpretation_label" / source.name).read_text(encoding="utf-8")
        (evaluation / "interpretation.txt").write_text(interpretations, encoding="utf-8")
        write_json(evaluation / "source.json", {"machine_id": machine, "scenario_id": identifier, "revision": config["revision"]})
        scenarios.append({"id": identifier, "machine_id": machine, "display_name": machine,
                          "start_index": 0, "end_index": len(labels) - 1, "sample_count": len(labels),
                          "reference_samples": len(frames["train"]), "features": features})
        total_train += len(frames["train"])
        total_test += len(frames["test"])
    if total_train != config["expected_train_rows"] or total_test != config["expected_test_rows"]:
        raise ValueError("SMD row counts differ from the audited release")
    write_json(public / "registry.json", {"schema_version": 2, "dataset": "SMD", "axis": "sample_index",
                                          "source_revision": config["revision"], "scenarios": scenarios})
    print(f"Prepared {len(scenarios)} machines, {total_train} training and {total_test} replay observations; annotations isolated.")
    return scenarios


if __name__ == "__main__":
    # Verify all original files before publishing a production registry.
    from download_smd import verify
    verify(json.loads((ROOT / "config/dataset.json").read_text(encoding="utf-8")))
    prepare()
