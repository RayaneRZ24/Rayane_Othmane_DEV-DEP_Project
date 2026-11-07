"""Compare exactly two predeclared candidates; never select hyperparameters on test."""
import json
from hashlib import sha256
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from smartops.detection import CONFIG as BASELINE_CONFIG
from smartops.multivariate import CONFIG as PCA_CONFIG
from smartops.telemetry import Registry
from evaluate_detector import metrics, predict

ROOT = Path(__file__).resolve().parents[1]
METHODS = ["robust-mad-v1", "pca-joint-v1"]


if __name__ == "__main__":
    protocol = {"date": "2026-10-22", "methods": METHODS, "baseline_config": BASELINE_CONFIG,
                "pca_config": PCA_CONFIG, "selection": "none; baseline remains default; both methods explicitly available",
                "splits": "chronological 80/20 within published train; test labels for reporting only",
                "metrics": "pointwise, no point adjustment; active alerts union across indicators"}
    payload = json.dumps(protocol, sort_keys=True, indent=2)
    protocol_path = ROOT / "config/comparison_protocol.json"
    if protocol_path.exists() and json.loads(protocol_path.read_text()) != protocol:
        raise ValueError("The frozen protocol changed; create a new study instead of overwriting it")
    protocol_path.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode()).hexdigest()
    print(f"Frozen protocol before predictions and labels: {digest}", flush=True)
    registry = Registry(ROOT / "data/monitoring-smd")
    rows = []
    for scenario in registry.scenarios.values():
        data = registry.load(scenario.id)
        predictions = {}
        for method in METHODS:
            started = perf_counter()
            profile = data.fit_detector(registry.root, method)
            prediction, alerts = predict(data, profile)
            predictions[method] = (prediction, alerts, profile["fingerprint"], perf_counter() - started)
        labels = pd.read_parquet(ROOT / "data/evaluation-smd" / scenario.id / "labels.parquet")
        if not np.array_equal(labels.sample_index.to_numpy(), data.metrics.sample_index.to_numpy()):
            raise ValueError("Evaluation alignment mismatch")
        truth = labels.is_anomaly.to_numpy(dtype=bool)
        for method, (prediction, alerts, fingerprint, seconds) in predictions.items():
            rows.append({"machine": scenario.machine_id, "method": method, "samples": len(truth),
                         "alerts": alerts, "profile_fingerprint": fingerprint, "seconds": seconds, **metrics(truth, prediction)})
        print(scenario.machine_id + ": " + ", ".join(f"{r['method']} F1={r['f1']:.3f}" for r in rows[-2:]), flush=True)
    if len(rows) != 56:
        raise ValueError("Both candidates must be evaluated on all 28 machines")
    summaries = {}
    for method in METHODS:
        selected = [r for r in rows if r["method"] == method]
        sums = {key: sum(r[key] for r in selected) for key in ["tp", "fp", "fn", "tn", "alerts", "samples", "seconds"]}
        tp, fp, fn, tn = [sums[k] for k in ["tp", "fp", "fn", "tn"]]
        precision = tp / (tp + fp) if tp + fp else 0.
        recall = tp / (tp + fn) if tp + fn else 0.
        summaries[method] = {**sums, "precision": precision, "recall": recall,
                             "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.,
                             "normal_point_false_positive_rate": fp / (fp + tn) if fp + tn else 0.,
                             "macro_f1": sum(r["f1"] for r in selected) / len(selected)}
    report = {"protocol": protocol, "protocol_sha256": digest, "summaries": summaries, "machines": rows}
    (ROOT / "reports/detector_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    pd.DataFrame(rows).to_csv(ROOT / "reports/detector_comparison.csv", index=False)
    print(json.dumps(summaries, indent=2), flush=True)
