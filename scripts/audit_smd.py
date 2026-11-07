"""Audit complete local downloads; never fit a detector or tune on test labels."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"


def segments(labels):
    labels = np.asarray(labels, dtype=bool)
    changes = np.diff(np.r_[False, labels, False].astype(int))
    return list(zip(np.flatnonzero(changes == 1).tolist(), (np.flatnonzero(changes == -1) - 1).tolist()))


def numeric_report(frame):
    values = frame.to_numpy(dtype=float)
    finite = np.isfinite(values)
    return {
        "rows": len(frame), "dimensions": len(frame.columns),
        "missing_cells": int(frame.isna().sum().sum()), "infinite_cells": int(np.isinf(values).sum()),
        "negative_cells": int((values < 0).sum()), "above_one_cells": int((values > 1).sum()),
        "constant_columns": [str(c) for c in frame if frame[c].nunique(dropna=False) <= 1],
        "duplicate_rows": int(frame.duplicated().sum()),
        "consecutive_equal_rows": int(np.all(values[1:] == values[:-1], axis=1).sum()),
        "all_finite": bool(finite.all()),
    }


def smd():
    folder = DATA / "raw/SMD"
    files, columns, entities = [], [], []
    for train_path in sorted((folder / "train").glob("*.txt")):
        name = train_path.name
        train = pd.read_csv(train_path, header=None)
        test = pd.read_csv(folder / "test" / name, header=None)
        labels = pd.read_csv(folder / "test_label" / name, header=None).iloc[:, 0]
        annotations = []
        for line in (folder / "interpretation_label" / name).read_text().splitlines():
            bounds, dims = line.split(":")
            start, end = map(int, bounds.split("-"))
            annotations.append({"start": start, "end": end, "dimensions": list(map(int, dims.split(",")))})
        train_hash = pd.util.hash_pandas_object(train, index=False)
        test_hash = pd.util.hash_pandas_object(test, index=False)
        overlap = int(test_hash.isin(set(train_hash)).sum())
        valid_bounds = all(0 <= a["start"] <= a["end"] <= len(test) for a in annotations)
        valid_dims = all(all(1 <= d <= test.shape[1] for d in a["dimensions"]) for a in annotations)
        annotation_alignment = {}
        for origin in [0, 1]:
            mask = np.zeros(len(test), dtype=bool)
            for a in annotations:
                left, right = a["start"] - origin, a["end"] - origin
                if left >= 0 and right < len(mask):
                    mask[left:right + 1] = True
            annotation_alignment[str(origin)] = {
                "covered_points": int(mask.sum()),
                "disagreement_with_binary_labels": int((mask != labels.to_numpy(dtype=bool)).sum()),
            }
        for origin in [0, 1]:
            mask = np.zeros(len(test), dtype=bool)
            for a in annotations:
                left, right = a["start"] - origin, a["end"] - origin
                if left >= 0 and right <= len(mask):
                    mask[left:right] = True
            annotation_alignment[f"{origin}_half_open"] = {
                "covered_points": int(mask.sum()),
                "disagreement_with_binary_labels": int((mask != labels.to_numpy(dtype=bool)).sum()),
            }
        entities.append({"machine": train_path.stem, "train_rows": len(train), "test_rows": len(test),
                         "dimensions": test.shape[1], "label_rows": len(labels),
                         "binary_labels_valid": bool(labels.isin([0, 1]).all()),
                         "label_length_matches": bool(len(labels) == len(test)),
                         "anomaly_points": int(labels.sum()), "anomaly_ratio": float(labels.mean()),
                         "anomaly_segments": len(segments(labels)), "interpretation_ranges": len(annotations),
                         "interpretation_bounds_valid": valid_bounds, "interpretation_dimensions_valid": valid_dims,
                         "interpretation_alignment": annotation_alignment, "test_rows_identical_to_train": overlap})
        for split, frame in [("train", train), ("test", test)]:
            files.append({"machine": train_path.stem, "split": split, **numeric_report(frame)})
            for col in frame:
                columns.append({"machine": train_path.stem, "split": split, "dimension": int(col) + 1,
                                "min": float(frame[col].min()), "max": float(frame[col].max()),
                                "unique": int(frame[col].nunique()), "std": float(frame[col].std())})
    if len(entities) != 28:
        raise ValueError("Incomplete SMD download")
    pd.DataFrame(files).to_csv(REPORTS / "smd_files.csv", index=False)
    pd.DataFrame(columns).to_csv(REPORTS / "smd_columns.csv", index=False)
    summary = {
        "machines": len(entities), "dimensions": sorted({f["dimensions"] for f in files}),
        "train_rows": sum(e["train_rows"] for e in entities), "test_rows": sum(e["test_rows"] for e in entities),
        "missing_cells": sum(f["missing_cells"] for f in files), "infinite_cells": sum(f["infinite_cells"] for f in files),
        "negative_cells": sum(f["negative_cells"] for f in files), "above_one_cells": sum(f["above_one_cells"] for f in files),
        "anomaly_points": sum(e["anomaly_points"] for e in entities),
        "anomaly_segments": sum(e["anomaly_segments"] for e in entities),
        "interpretation_ranges": sum(e["interpretation_ranges"] for e in entities),
        "constant_columns_per_file_min": min(len(f["constant_columns"]) for f in files),
        "constant_columns_per_file_max": max(len(f["constant_columns"]) for f in files),
        "duplicate_rows": sum(f["duplicate_rows"] for f in files),
        "test_rows_identical_to_train": sum(e["test_rows_identical_to_train"] for e in entities),
        "labels_all_valid": all(e["label_length_matches"] and e["binary_labels_valid"] for e in entities),
        "interpretations_all_in_bounds": all(e["interpretation_bounds_valid"] and e["interpretation_dimensions_valid"] for e in entities),
        "interpretation_disagreement_totals_by_index_convention": {
            convention: sum(e["interpretation_alignment"][convention]["disagreement_with_binary_labels"] for e in entities)
            for convention in ["0", "1", "0_half_open", "1_half_open"]
        },
    }
    return {"summary": summary, "entities": entities, "files": files}



if __name__ == "__main__":
    REPORTS.mkdir(exist_ok=True)
    result = smd()
    (REPORTS / "smd_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
