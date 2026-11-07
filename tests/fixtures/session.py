"""Explicit synthetic observations for replay tests only, never a production fallback."""
import json
from pathlib import Path
from uuid import uuid4

import pandas as pd


def build_session(root: Path):
    identifier = str(uuid4())
    folder = root / identifier
    folder.mkdir(parents=True)
    values = [i / 400 for i in range(401)]
    values[4] = None
    frame = pd.DataFrame({"sample_index": list(range(401)), "cpu_r": values,
                          "mem_u": [.5] * 401, "disk_u": [.2] * 401, "tcp_use": [.3] * 401})
    frame.to_parquet(folder / "metrics.parquet", index=False)
    reference = frame.copy()
    reference["cpu_r"] = .2
    reference.to_parquet(folder / "reference.parquet", index=False)
    features = [{"id": name, "label": label, "group": group, "unit": "normalized"}
                for name, label, group in [("cpu_r", "CPU", "cpu"), ("mem_u", "Mémoire", "memory"),
                                           ("disk_u", "Disque", "disk"), ("tcp_use", "Réseau", "network")]]
    scenario = {"id": identifier, "machine_id": "machine-test", "display_name": "machine-test",
                "start_index": 0, "end_index": 400, "sample_count": 401, "reference_samples": 401, "features": features}
    (root / "registry.json").write_text(json.dumps({"schema_version": 2, "dataset": "SMD", "axis": "sample_index",
                                                   "scenarios": [scenario]}), encoding="utf-8")
    return scenario


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build_session(parser.parse_args().output)
