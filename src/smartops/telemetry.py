"""SMD series without annotations, read strictly through a confirmed sample index."""
from dataclasses import asdict, dataclass
import json
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Scenario:
    id: str
    machine_id: str
    display_name: str
    start_index: int
    end_index: int
    sample_count: int
    reference_samples: int
    features: list[dict]

    def public(self):
        return {**asdict(self), "axis": "sample_index", "split": "test"}


class Registry:
    def __init__(self, root: Path):
        self.root = root
        self.scenarios: dict[str, Scenario] = {}
        manifest = root / "registry.json"
        if not manifest.exists():
            return
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("schema_version") != 2 or data.get("dataset") != "SMD" or data.get("axis") != "sample_index":
            raise ValueError("Unsupported SMD registry; run scripts/prepare_smd.py")
        for item in data["scenarios"]:
            UUID(item["id"])
            scenario = Scenario(**item)
            if scenario.start_index != 0 or scenario.end_index != scenario.sample_count - 1 or scenario.sample_count < 1:
                raise ValueError("Invalid sample bounds")
            ids = [f["id"] for f in scenario.features]
            if len(ids) != len(set(ids)) or not ids or any(f["unit"] != "normalized" for f in scenario.features):
                raise ValueError("Invalid feature dictionary")
            self.scenarios[scenario.id] = scenario

    def load(self, identifier: str):
        return Telemetry(self.scenarios[identifier], self.root / str(UUID(identifier)))


class Telemetry:
    def __init__(self, scenario: Scenario, folder: Path):
        self.scenario = scenario
        self.metrics = pd.read_parquet(folder / "metrics.parquet")
        expected = ["sample_index", *[f["id"] for f in scenario.features]]
        if list(self.metrics.columns) != expected or len(self.metrics) != scenario.sample_count:
            raise ValueError("Invalid prepared feature schema")
        if not np.array_equal(self.metrics.sample_index.to_numpy(), np.arange(scenario.sample_count)):
            raise ValueError("Invalid observation order")

    def metric_page(self, feature, begin, end, offset, limit):
        if feature not in {f["id"] for f in self.scenario.features}:
            raise KeyError("feature")
        segment = self.metrics.iloc[max(begin, 0):min(end + 1, len(self.metrics))][["sample_index", feature]]
        page = segment.iloc[offset:offset + limit]
        values = [{"sample_index": int(i), "value": None if pd.isna(v) else float(v),
                   "observed": bool(pd.notna(v))} for i, v in page.itertuples(index=False, name=None)]
        return values, offset + len(values) < len(segment)

    def fit_detector(self, root, method="robust-mad-v1"):
        from smartops.detection import fit_reference
        path = root / self.scenario.id / "reference.parquet"
        reference = pd.read_parquet(path)
        if len(reference) != self.scenario.reference_samples:
            raise ValueError("Invalid training reference size")
        if method == "pca-joint-v1":
            from smartops.multivariate import fit_multivariate
            return fit_multivariate(reference, self.scenario.features, sha256(path.read_bytes()).hexdigest())
        if method != "robust-mad-v1":
            raise ValueError("Unknown detector")
        return fit_reference(reference, self.scenario.features, sha256(path.read_bytes()).hexdigest())
