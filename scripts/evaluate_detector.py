"""Evaluate the frozen baseline; labels are loaded only after predictions exist."""
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from smartops.detection import CONFIG, VERSION, observe
from smartops.telemetry import Registry

ROOT = Path(__file__).resolve().parents[1]


def predict(data, profile):
    mask = np.zeros(len(data.metrics), dtype=bool)
    state, active, count = {}, {}, 0
    for begin in range(0, len(mask), 256):
        state, transitions = observe(profile, state, data.metrics.iloc[begin:begin + 256])
        for event in transitions:
            if event["kind"] == "open":
                active[event["id"]] = event["detected_index"]
                count += 1
            elif event["kind"] == "recover":
                start = active.pop(event["id"])
                mask[start:event["closed_index"]] = True
    for start in active.values():
        mask[start:] = True
    return mask, count


def metrics(truth, prediction):
    tp = int((truth & prediction).sum())
    fp = int((~truth & prediction).sum())
    fn = int((truth & ~prediction).sum())
    tn = int((~truth & ~prediction).sum())
    precision = tp / (tp + fp) if tp + fp else 0.
    recall = tp / (tp + fn) if tp + fn else 0.
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.,
            "normal_point_false_positive_rate": fp / (fp + tn) if fp + tn else 0.}


if __name__ == "__main__":
    registry = Registry(ROOT / "data/monitoring-smd")
    rows = []
    started = perf_counter()
    for scenario in registry.scenarios.values():
        data = registry.load(scenario.id)
        profile = data.fit_detector(registry.root)
        prediction, count = predict(data, profile)
        # No label or interpretation is passed to fitting, scoring or persistence logic.
        labels = pd.read_parquet(ROOT / "data/evaluation-smd" / scenario.id / "labels.parquet")
        if not np.array_equal(labels.sample_index.to_numpy(), data.metrics.sample_index.to_numpy()):
            raise ValueError("Evaluation alignment mismatch")
        truth = labels.is_anomaly.to_numpy(dtype=bool)
        rows.append({"machine": scenario.machine_id, "samples": len(truth), "alerts": count,
                     "profile_fingerprint": profile["fingerprint"], **metrics(truth, prediction)})
        print(f"{scenario.machine_id}: precision={rows[-1]['precision']:.3f}, recall={rows[-1]['recall']:.3f}, alerts={count}", flush=True)
    if len(rows) != 28:
        raise ValueError("Expected the complete 28-machine benchmark")
    totals = {key: sum(row[key] for row in rows) for key in ["tp", "fp", "fn", "tn"]}
    tp, fp, fn, tn = [totals[key] for key in ["tp", "fp", "fn", "tn"]]
    precision, recall = tp / (tp + fp) if tp + fp else 0., tp / (tp + fn) if tp + fn else 0.
    report = {"version": VERSION, "config": CONFIG, "status": "initial_frozen_baseline_not_selected_using_test",
              "protocol": "chronological 80/20 training split; pointwise OR of active feature alerts; no point adjustment",
              "seconds": perf_counter() - started, "samples": sum(row["samples"] for row in rows),
              "micro": {**totals, "precision": precision, "recall": recall,
                        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.,
                        "normal_point_false_positive_rate": fp / (fp + tn) if fp + tn else 0.},
              "macro_f1": sum(row["f1"] for row in rows) / len(rows), "machines": rows}
    (ROOT / "reports/detection_evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    pd.DataFrame(rows).to_csv(ROOT / "reports/detection_evaluation.csv", index=False)
    print(json.dumps(report["micro"]), flush=True)
