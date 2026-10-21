"""Summarize measured quality and validate downloaded-file fingerprints."""
from hashlib import sha256
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    reports = ROOT / "reports"
    r = json.loads((reports / "selected_audit.json").read_text(encoding="utf-8"))["results"]
    m, logs = [x["metrics"] for x in r], [x["logs"] for x in r]
    idx = pd.read_parquet(ROOT / "data/sources/cases.parquet")
    idx = idx.loc[idx.dataset.eq("RE2-OB")].sort_values("time_start")
    overlaps = []
    for pos, (_, a) in enumerate(idx.iterrows()):
        for _, b in idx.iloc[pos + 1:].iterrows():
            if b.time_start <= a.time_end:
                overlaps.append([a["case"], b["case"]])
    summary = {
        "cases": len(r), "log_rows": sum(x["rows"] for x in logs),
        "logs_null_cells": sum(x["null_cells"] for x in logs),
        "logs_empty_messages": sum(x["empty_messages"] for x in logs),
        "logs_outside_metric_window": sum(x["time"]["rows_outside_metric_window"] for x in logs),
        "metric_missing_pct_min": min(x["null_fraction"] for x in m) * 100,
        "metric_missing_pct_median": float(pd.Series([x["null_fraction"] for x in m]).median() * 100),
        "metric_missing_pct_max": max(x["null_fraction"] for x in m) * 100,
        "metric_constant_columns_min": min(len(x["constant_columns"]) for x in m),
        "metric_constant_columns_max": max(len(x["constant_columns"]) for x in m),
        "cases_with_all_null_metric": sum(bool(x["all_null_columns"]) for x in m),
        "metric_duplicate_timestamps": sum(x["duplicate_timestamps"] for x in m),
        "metric_infinite_cells": sum(x["infinite_cells"] for x in m),
        "metric_rows": sum(x["rows"] for x in m),
        "log_duplicate_rows": sum(x["duplicate_rows"] for x in logs),
        "index_injection_matches": all(x["index_injection_matches"] for x in r),
        "index_metric_rows_match": all(x["index_metric_rows_match"] for x in r),
        "index_log_rows_match": all(x["index_row_count_matches"] for x in logs),
        "max_case_logs_memory_MB": max(x["memory_bytes"] for x in logs) / 1e6,
        "cases_with_no_root_service_logs": [x["case"] for x in r if x["logs"]["root_service_rows"] == 0],
        "overlapping_case_windows": overlaps,
        "short_cases": idx.loc[idx.n_timesteps.lt(1441), ["case", "normal_timesteps", "faulty_timesteps"]].to_dict("records"),
    }
    for filename in ["selected_manifest.json", "sample_manifest.json"]:
        manifest = json.loads((reports / filename).read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            path = ROOT / "data/raw/RCAEval" / entry["path"]
            if sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"Fingerprint mismatch: {path}")
    if not (len(r) == 90 and summary["index_injection_matches"] and summary["index_metric_rows_match"] and summary["index_log_rows_match"]):
        raise ValueError("Audit does not match the selected index")
    summary["local_fingerprints_verified"] = True
    (reports / "selected_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))
