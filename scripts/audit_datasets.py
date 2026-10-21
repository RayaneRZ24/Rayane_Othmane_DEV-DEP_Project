"""Reproducible local audit; never modifies the downloaded telemetry."""
from pathlib import Path
import json
import platform
import sys
import argparse
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

def observed_median(series):
    observed = series.dropna()
    return float(observed.median()) if len(observed) else None

def table_audit(df):
    return {
        "rows": len(df), "columns": len(df.columns),
        "null_cells": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "memory_bytes": int(df.memory_usage(deep=True).sum()),
    }

def time_audit(values, begin, end):
    values = pd.to_numeric(values, errors="coerce").dropna()
    return {
        "min": float(values.min()) if len(values) else None,
        "max": float(values.max()) if len(values) else None,
        "rows_in_metric_window": int(values.between(begin, end).sum()),
        "rows_outside_metric_window": int((~values.between(begin, end)).sum()),
    }

def audit_case(row, include_traces=True):
    path = ROOT / "data/raw/RCAEval" / row["case"]
    m = pd.read_parquet(path / "metrics.parquet")
    v = m.drop(columns="time")
    injection = int((path / "inject_time.txt").read_text())
    normal = v.loc[m.time < injection]
    post = v.loc[m.time >= injection]
    target = f"{row['root_cause_service']}_{'diskio' if row['fault'] == 'disk' else row['fault']}"
    result = {
        "case": row["case"], "dataset": row["dataset"], "fault": row["fault"],
        "root_cause_service": row["root_cause_service"],
        "inject_time": injection, "index_injection_matches": bool(injection == row["inject_time"]),
        "normal_rows": len(normal), "post_injection_rows": len(post),
        "index_metric_rows_match": bool(len(m) == row["n_timesteps"]),
        "duration_seconds": int(m.time.max() - m.time.min()),
        "metrics": {
            **table_audit(m), "n_metrics": len(v.columns),
            "null_fraction": float(v.isna().to_numpy().mean()),
            "infinite_cells": int(np.isinf(v.to_numpy(dtype=float)).sum()),
            "duplicate_timestamps": int(m.time.duplicated().sum()),
            "sorted_timestamps": bool(m.time.is_monotonic_increasing),
            "median_step_seconds": float(m.time.diff().median()),
            "step_counts": {str(k): int(c) for k, c in m.time.diff().value_counts().items()},
            "constant_columns": v.columns[v.nunique(dropna=True) <= 1].tolist(),
            "all_null_columns": v.columns[v.isna().all()].tolist(),
            "columns_over_20pct_missing": v.columns[v.isna().mean() > .2].tolist(),
            "root_service_metrics": [c for c in v if c.startswith(row["root_cause_service"] + "_")],
            "direct_fault_metric": target if target in v else None,
        },
    }
    if target in v:
        result["metrics"]["direct_metric_normal_median"] = observed_median(normal[target])
        result["metrics"]["direct_metric_post_median"] = observed_median(post[target])
    for name in ["logs", "traces"]:
        if name == "traces" and not include_traces:
            result[name] = {"present": bool(row["has_traces"]), "audited": False, "rows": int(row["n_traces"])}
            continue
        file = path / f"{name}.parquet"
        if not file.exists():
            result[name] = {"present": False}
            continue
        df = pd.read_parquet(file)
        details = {"present": True, **table_audit(df), "column_names": df.columns.tolist()}
        details["nulls_by_column"] = {c: int(n) for c, n in df.isna().sum().items()}
        details["index_row_count_matches"] = bool(len(df) == row["n_logs" if name == "logs" else "n_traces"])
        if name == "logs":
            times = df.timestamp
            services = df.container_name
            details["empty_messages"] = int(df.message.fillna("").str.strip().eq("").sum())
            details["distinct_messages"] = int(df.message.nunique())
            details["root_service_rows"] = int(services.eq(row["root_cause_service"]).sum())
        else:
            times = df.startTimeMillis / 1000
            services = df.serviceName
            details["duplicate_span_keys"] = int(df.duplicated(["traceID", "spanID"]).sum())
            details["negative_durations"] = int((df.duration < 0).sum())
            details["null_parent_ids"] = int(df.parentSpanID.isna().sum())
        details["services"] = sorted(str(s) for s in services.dropna().unique())
        details["time"] = time_audit(times, m.time.min(), m.time.max())
        details["rows_before_injection"] = int((times < injection).sum())
        details["rows_at_or_after_injection"] = int((times >= injection).sum())
        result[name] = details
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected", action="store_true", help="Audit metrics/logs of all 90 RE2-OB incidents")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    REPORTS.mkdir(exist_ok=True)
    idx = pd.read_parquet(ROOT / "data/sources/cases.parquet")
    summary = idx.groupby("dataset").agg(
        cases=("case", "size"), cases_with_logs=("has_logs", "sum"), cases_with_traces=("has_traces", "sum"),
        metrics_min=("n_metrics", "min"), metrics_max=("n_metrics", "max"),
        normal_rows_min=("normal_timesteps", "min"), duration_minutes_min=("duration_minutes", "min"),
        duration_minutes_max=("duration_minutes", "max"),
    ).reset_index()
    summary.to_csv(REPORTS / "dataset_inventory.csv", index=False)
    invalid = idx[(idx.inject_time <= idx.time_start) | (idx.inject_time >= idx.time_end)]
    invalid.to_csv(REPORTS / "index_time_issues.csv", index=False)
    prefix = "selected" if args.selected else "sample"
    manifest = json.loads((REPORTS / f"{prefix}_manifest.json").read_text(encoding="utf-8"))
    results = []
    for i, case in enumerate(manifest["cases"]):
        results.append(audit_case(idx.loc[idx.case.eq(case)].iloc[0], include_traces=not args.selected))
        print(f"Audited {i+1}/{len(manifest['cases'])}: {case}", flush=True)
    (REPORTS / f"{prefix}_audit.json").write_text(json.dumps({
        "dataset_revision": manifest["revision"],
        "environment": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "scope": "All 90 RE2-OB cases, metrics/logs only; trace counts from index" if args.selected else "12 purposively selected cases, six fault types in each of RE2-SS and RE2-OB; not a random sample",
        "results": results,
    }, indent=2, allow_nan=False), encoding="utf-8")
    rows = []
    for r in results:
        rows.append({"case": r["case"], "metrics": r["metrics"]["n_metrics"],
                     "null_pct": round(100 * r["metrics"]["null_fraction"], 4),
                     "constant_metrics": len(r["metrics"]["constant_columns"]),
                     "normal_rows": r["normal_rows"], "post_rows": r["post_injection_rows"],
                     "logs": r["logs"].get("rows", 0), "log_nulls": r["logs"].get("null_cells", 0),
                     "log_duplicate_rows": r["logs"].get("duplicate_rows", 0),
                     "root_service_logs": r["logs"].get("root_service_rows", 0),
                     "spans": r["traces"].get("rows", 0),
                     "direct_fault_metric": r["metrics"]["direct_fault_metric"]})
    frame = pd.DataFrame(rows)
    frame.to_csv(REPORTS / f"{prefix}_quality.csv", index=False)
    print(summary.to_string(index=False))
    print(frame.to_string(index=False))
