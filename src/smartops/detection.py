"""A fixed robust baseline calibrated only on a chronological training holdout."""
from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

import numpy as np

VERSION = "robust-mad-v1"
CONFIG = {"fit_fraction": .8, "validation_quantile": .995, "minimum_z": 6.,
          "scale_floor": .001, "persistence": 3, "recovery": 5,
          "minimum_fit_points": 100, "minimum_validation_points": 20}


def fit_reference(frame, features, source_hash):
    names = [f["id"] for f in features]
    if list(frame.columns) != ["sample_index", *names]:
        raise ValueError("Invalid reference schema")
    boundary = int(len(frame) * CONFIG["fit_fraction"])
    if boundary < CONFIG["minimum_fit_points"] or len(frame) - boundary < CONFIG["minimum_validation_points"]:
        raise ValueError("Insufficient training reference")
    values = frame[names].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Incomplete reference observations")
    fit, validation = values[:boundary], values[boundary:]
    center = np.median(fit, axis=0)
    mad = np.median(np.abs(fit - center), axis=0)
    iqr = np.quantile(fit, .75, axis=0) - np.quantile(fit, .25, axis=0)
    scale = np.maximum(np.maximum(1.4826 * mad, iqr / 1.349), CONFIG["scale_floor"])
    scores = np.abs(validation - center) / scale
    thresholds = np.maximum(CONFIG["minimum_z"], np.quantile(scores, CONFIG["validation_quantile"], axis=0))
    profile = {"version": VERSION, "config": CONFIG.copy(), "reference_hash": source_hash,
               "fit_count": boundary, "validation_count": len(validation), "features": {}}
    for n, feature in enumerate(features):
        profile["features"][feature["id"]] = {**feature, "center": float(center[n]),
                                               "scale": float(scale[n]), "threshold": float(thresholds[n])}
    profile["fingerprint"] = sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()
    return profile


def observe(profile, previous_state, frame):
    """Process every row in order. Return state and deterministic alert transitions."""
    if profile["version"] == "pca-joint-v1":
        from smartops.multivariate import observe_multivariate
        return observe_multivariate(profile, previous_state, frame)
    state = deepcopy(previous_state or {})
    transitions = []
    config = profile["config"]
    for row in frame.to_dict(orient="records"):
        index = int(row["sample_index"])
        for name, reference in profile["features"].items():
            current = state.setdefault(name, {"streak": 0, "clear": 0, "alert_id": None})
            value = row[name]
            finite = value is not None and np.isfinite(value)
            score = abs(float(value) - reference["center"]) / reference["scale"] if finite else None
            abnormal = finite and score > reference["threshold"]
            if abnormal:
                if not current["streak"]:
                    current["start"] = index
                current["streak"] += 1
                current["clear"] = 0
                current["last_anomalous_index"] = index
                evidence = {"sample_index": index, "value": float(value), "reference_median": reference["center"],
                            "reference_scale": reference["scale"], "score": score, "threshold": reference["threshold"],
                            "expected_lower": max(0., reference["center"] - reference["scale"] * reference["threshold"]),
                            "expected_upper": min(1., reference["center"] + reference["scale"] * reference["threshold"])}
                if not current["alert_id"] and current["streak"] >= config["persistence"]:
                    current["alert_id"] = str(uuid4())
                    current["peak_score"] = score
                    transitions.append({"kind": "open", "id": current["alert_id"], "feature_id": name,
                                        "feature_label": reference["label"], "resource": reference["group"],
                                        "start_index": current["start"], "detected_index": index,
                                        "last_anomalous_index": index, "peak_score": score, "evidence": evidence})
                elif current["alert_id"]:
                    current["peak_score"] = max(current["peak_score"], score)
                    transitions.append({"kind": "update", "id": current["alert_id"],
                                        "last_anomalous_index": index, "peak_score": current["peak_score"]})
            else:
                current["streak"] = 0
                # Missing values break persistence, but never establish recovery.
                current["clear"] = current["clear"] + 1 if finite else 0
                if current["alert_id"] and current["clear"] >= config["recovery"]:
                    transitions.append({"kind": "recover", "id": current["alert_id"], "closed_index": index})
                    current["alert_id"] = None
    return state, transitions
