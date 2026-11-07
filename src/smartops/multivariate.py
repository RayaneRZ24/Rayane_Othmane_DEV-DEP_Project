"""A fixed PCA challenger, fitted and calibrated only on chronological train data."""
from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

import numpy as np

VERSION = "pca-joint-v1"
CONFIG = {"explained_variance": .90, "residual_scale_floor": .1,
          "eigenvalue_relative_floor": .001, "eigenvalue_absolute_floor": 1e-6,
          "minimum_residual_threshold": 36., "validation_quantile": .995,
          "persistence": 3, "recovery": 5}


def components(profile, values):
    pca = profile["pca"]
    names = profile["feature_order"]
    center = np.array([profile["features"][n]["center"] for n in names])
    scale = np.array([profile["features"][n]["scale"] for n in names])
    z = (values - center) / scale - np.array(pca["mean"])
    basis = np.asarray(pca["basis"]).reshape(len(names), pca["rank"])
    projected = z @ basis
    residual = z - projected @ basis.T
    residual_contributions = (residual / np.asarray(pca["residual_scale"])) ** 2
    q = residual_contributions.mean(axis=1)
    eigenvalues = np.asarray(pca["eigenvalues"])
    t2 = ((projected ** 2) / eigenvalues).sum(axis=1) if pca["rank"] else np.zeros(len(values))
    joint_contributions = np.abs(z * ((projected / eigenvalues) @ basis.T)) if pca["rank"] else np.zeros_like(z)
    return q, t2, residual_contributions, joint_contributions


def fit_multivariate(frame, features, source_hash):
    from smartops.detection import fit_reference
    profile = fit_reference(frame, features, source_hash)
    names = list(profile["features"])
    # JSONB may reorder object keys. Array coordinates must retain an explicit order.
    profile["feature_order"] = names
    values = frame[names].to_numpy(dtype=float)
    boundary = profile["fit_count"]
    center = np.array([profile["features"][n]["center"] for n in names])
    scale = np.array([profile["features"][n]["scale"] for n in names])
    fit = (values[:boundary] - center) / scale
    mean = fit.mean(axis=0)
    fit = fit - mean
    covariance = fit.T @ fit / max(len(fit) - 1, 1)
    eigenvalues, basis = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues, basis = np.maximum(eigenvalues[order], 0), basis[:, order]
    total = eigenvalues.sum()
    rank = min(int(np.searchsorted(np.cumsum(eigenvalues) / total, CONFIG["explained_variance"])) + 1, len(names) - 1) if total > 1e-12 else 0
    basis = basis[:, :rank]
    residual = fit - (fit @ basis) @ basis.T
    floor = max(float(eigenvalues[0]) * CONFIG["eigenvalue_relative_floor"], CONFIG["eigenvalue_absolute_floor"])
    profile["pca"] = {"rank": rank, "mean": mean.tolist(), "basis": basis.tolist(),
                      "eigenvalues": np.maximum(eigenvalues[:rank], floor).tolist(),
                      "residual_scale": np.maximum(np.sqrt((residual ** 2).mean(axis=0)), CONFIG["residual_scale_floor"]).tolist()}
    profile["version"] = VERSION
    profile["config"] = {**profile["config"], **CONFIG}
    q, t2, _, _ = components(profile, values[boundary:])
    profile["pca"]["q_threshold"] = max(CONFIG["minimum_residual_threshold"], float(np.quantile(q, CONFIG["validation_quantile"])))
    profile["pca"]["t2_threshold"] = max(float(rank + 6 * np.sqrt(2 * max(rank, 1))), float(np.quantile(t2, CONFIG["validation_quantile"])))
    profile.pop("fingerprint", None)
    profile["fingerprint"] = sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()
    return profile


def observe_multivariate(profile, previous_state, frame):
    state = deepcopy(previous_state or {})
    current = state.setdefault("joint", {"streak": 0, "clear": 0, "alert_id": None})
    names = profile["feature_order"]
    values = frame[names].to_numpy(dtype=float)
    q, t2, q_contributions, t_contributions = components(profile, values)
    config, model = profile["config"], profile["pca"]
    transitions = []
    for position, index in enumerate(frame.sample_index):
        index = int(index)
        finite = bool(np.isfinite(values[position]).all())
        ratios = (q[position] / model["q_threshold"], t2[position] / model["t2_threshold"])
        score = float(max(ratios)) if finite else None
        if finite and score > 1.:
            if not current["streak"]:
                current["start"] = index
            current["streak"] += 1
            current["clear"] = 0
            if not current["alert_id"] and current["streak"] >= config["persistence"]:
                contributions = q_contributions[position] if ratios[0] >= ratios[1] else t_contributions[position]
                order = np.argsort(-contributions, kind="stable")
                dominant = int(order[0])
                reference = profile["features"][names[dominant]]
                current["alert_id"] = str(uuid4())
                current["peak_score"] = score
                evidence = {"method": VERSION, "sample_index": index, "value": float(values[position, dominant]),
                            "reference_median": reference["center"], "reference_scale": reference["scale"],
                            "expected_lower": max(0., reference["center"] - reference["scale"] * reference["threshold"]),
                            "expected_upper": min(1., reference["center"] + reference["scale"] * reference["threshold"]),
                            "score": score, "threshold": 1., "q_score": float(q[position]), "t2_score": float(t2[position]),
                            "q_threshold": model["q_threshold"], "t2_threshold": model["t2_threshold"],
                            "contributors": [{"feature_id": names[int(i)], "label": profile["features"][names[int(i)]]["label"],
                                              "resource": profile["features"][names[int(i)]]["group"],
                                              "value": float(values[position, int(i)]), "contribution": float(contributions[int(i)])}
                                             for i in order[:3]]}
                transitions.append({"kind": "open", "id": current["alert_id"], "feature_id": names[dominant],
                                    "feature_label": reference["label"], "resource": reference["group"],
                                    "start_index": current["start"], "detected_index": index,
                                    "last_anomalous_index": index, "peak_score": score, "evidence": evidence})
            elif current["alert_id"]:
                current["peak_score"] = max(current["peak_score"], score)
                transitions.append({"kind": "update", "id": current["alert_id"], "last_anomalous_index": index, "peak_score": current["peak_score"]})
        else:
            current["streak"] = 0
            current["clear"] = current["clear"] + 1 if finite else 0
            if current["alert_id"] and current["clear"] >= config["recovery"]:
                transitions.append({"kind": "recover", "id": current["alert_id"], "closed_index": index})
                current["alert_id"] = None
    return state, transitions
