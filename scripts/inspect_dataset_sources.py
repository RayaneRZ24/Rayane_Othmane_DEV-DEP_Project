"""Download public dataset documentation and the RCAEval case index."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sources"
OUT.mkdir(parents=True, exist_ok=True)
CONFIG = json.loads((ROOT / "config/dataset.json").read_text(encoding="utf-8"))
REVISION = CONFIG["revision"]
URLS = {
    "rcaeval_info.json": f"https://huggingface.co/api/datasets/phamquiluan/RCAEval/revision/{REVISION}",
    "rcaeval_card.md": f"https://huggingface.co/datasets/phamquiluan/RCAEval/raw/{REVISION}/README.md",
    "rcaeval_readme.md": "https://raw.githubusercontent.com/phamquiluan/RCAEval/main/README.md",
    "gaia_readme.md": "https://raw.githubusercontent.com/CloudWise-OpenSource/GAIA-DataSet/main/README.md",
    "gaia_license.txt": "https://raw.githubusercontent.com/CloudWise-OpenSource/GAIA-DataSet/main/LICENSE",
    "smd_readme.md": "https://raw.githubusercontent.com/NetManAIOps/OmniAnomaly/master/README.md",
    "openrca_readme.md": "https://raw.githubusercontent.com/microsoft/OpenRCA/main/README.md",
}

def fetch(item):
    name, url = item
    r = requests.get(url, timeout=45)
    r.raise_for_status()
    (OUT / name).write_bytes(r.content)
    return {"file": name, "url": url, "bytes": len(r.content)}

if __name__ == "__main__":
    results = list(ThreadPoolExecutor(5).map(fetch, URLS.items()))
    info = json.loads((OUT / "rcaeval_info.json").read_text(encoding="utf-8"))
    revision = info["sha"]
    index_url = f"https://huggingface.co/datasets/phamquiluan/RCAEval/resolve/{revision}/cases.parquet"
    results.append(fetch(("cases.parquet", index_url)))
    (OUT / "provenance.json").write_text(json.dumps({"revision": revision, "downloads": results}, indent=2), encoding="utf-8")
    print(json.dumps({"revision": revision, "downloads": results}, indent=2))
    print("First files:", [x["rfilename"] for x in info["siblings"]][:25])
