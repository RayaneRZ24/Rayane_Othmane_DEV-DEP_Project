"""Fetch a deterministic, multi-fault sample at a pinned dataset revision."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import argparse
import time
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

def download(job):
    relative, revision = job
    dest = ROOT / "data" / "raw" / "RCAEval" / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/datasets/phamquiluan/RCAEval/resolve/{revision}/{relative}"
    if not dest.exists():
        for attempt in range(3):
            try:
                with requests.Session() as session:
                    session.mount("https://", HTTPAdapter(max_retries=Retry(total=1, backoff_factor=.5, status_forcelist=[429, 500, 502, 503, 504])))
                    response = session.get(url, timeout=(10, 25), stream=True)
                    response.raise_for_status()
                    content = response.content
                temporary = dest.with_suffix(dest.suffix + ".part")
                temporary.write_bytes(content)
                temporary.replace(dest)
                break
            except requests.RequestException as error:
                if attempt == 2:
                    return {"path": relative, "url": url, "error": str(error)}
                time.sleep(1)
    content = dest.read_bytes()
    return {"path": relative, "url": url, "bytes": len(content), "sha256": sha256(content).hexdigest()}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-ob-metrics-logs", action="store_true", help="Fetch metrics/logs for all 90 selected cases; traces remain sampled")
    args = parser.parse_args()
    info = json.loads((ROOT / "data/sources/rcaeval_info.json").read_text(encoding="utf-8"))
    revision = info["sha"]
    index = pd.read_parquet(ROOT / "data/sources/cases.parquet")
    cases = []
    for dataset in ["RE2-SS", "RE2-OB"]:
        part = index[(index.dataset == dataset) & (index.repetition == 1)]
        services = sorted(part.root_cause_service.unique())
        for i, fault in enumerate(sorted(part.fault.unique())):
            row = part[(part.fault == fault) & (part.root_cause_service == services[i % len(services)])].iloc[0]
            cases.append(row["case"])
    if args.all_ob_metrics_logs:
        cases = index.loc[index.dataset.eq("RE2-OB"), "case"].tolist()
    files = [x["rfilename"] for x in info["siblings"]
             if x["rfilename"].split("/")[0] in cases
             and (not args.all_ob_metrics_logs or x["rfilename"].split("/")[-1] != "traces.parquet")]
    results = []
    with ThreadPoolExecutor(8) as pool:
        for i, result in enumerate(pool.map(download, [(f, revision) for f in files])):
            results.append(result)
            if (i+1) % 20 == 0 or "error" in result:
                print(f"Processed {i+1}/{len(files)}; last: {result['path']}; error: {result.get('error', 'none')}", flush=True)
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    manifest_name = "selected_manifest.json" if args.all_ob_metrics_logs else "sample_manifest.json"
    (out / manifest_name).write_text(json.dumps({"revision": revision, "cases": cases, "files": results}, indent=2), encoding="utf-8")
    errors = [x for x in results if "error" in x]
    print("Total bytes:", sum(x.get("bytes", 0) for x in results), "Failures:", len(errors))
    if errors:
        raise SystemExit("Some files failed; rerun to resume.")
