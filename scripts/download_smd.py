"""Download the pinned SMD release or verify the complete local copy."""
import argparse
from hashlib import sha1, sha256
import io
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "SmartOps-SMD"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def verify(config):
    manifest = json.loads((ROOT / "data/sources/SMD/provenance.json").read_text())
    if manifest["dataset"] != "SMD" or manifest["revision"] != config["revision"]:
        raise ValueError("SMD provenance does not match the pinned configuration")
    if len(manifest["files"]) != config["expected_machines"] * 4 + 1:
        raise ValueError("Incomplete SMD manifest")
    folder = ROOT / config["raw_directory"]
    for item in manifest["files"]:
        relative = Path(item["path"]).relative_to("ServerMachineDataset")
        if ".." in relative.parts:
            raise ValueError("Invalid manifest path")
        content = (folder / relative).read_bytes()
        if len(content) != item["bytes"] or sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"SMD checksum mismatch: {relative}")
    return manifest


def download(config):
    revision = config["revision"]
    tree = json.loads(fetch(f"https://api.github.com/repos/NetManAIOps/OmniAnomaly/git/trees/{revision}?recursive=1"))
    if tree.get("truncated"):
        raise ValueError("Incomplete source tree")
    entries = {e["path"]: e for e in tree["tree"] if e["path"].startswith("ServerMachineDataset/") and e["type"] == "blob"}
    url = f"https://codeload.github.com/NetManAIOps/OmniAnomaly/tar.gz/{revision}"
    archive = fetch(url)
    files = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar:
            relative = member.name.partition("/")[2]
            if not member.isfile() or relative not in entries:
                continue
            path = Path(relative).relative_to("ServerMachineDataset")
            if ".." in path.parts:
                raise ValueError("Invalid archive path")
            payload = tar.extractfile(member).read()
            if sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest() != entries[relative]["sha"]:
                raise ValueError("Git blob integrity mismatch")
            target = ROOT / config["raw_directory"] / path
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".download")
            temporary.write_bytes(payload)
            temporary.replace(target)
            files.append({"path": relative, "bytes": len(payload), "sha256": sha256(payload).hexdigest()})
    if len(files) != len(entries):
        raise ValueError("Incomplete SMD archive")
    manifest = {"dataset": "SMD", "revision": revision, "url": url,
                "archive_sha256": sha256(archive).hexdigest(), "files": files}
    dest = ROOT / "data/sources/SMD/provenance.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return verify(config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true", help="Verify all local files without network access")
    args = parser.parse_args()
    config = json.loads((ROOT / "config/dataset.json").read_text())
    if config["name"] != "SMD":
        raise ValueError("This project requires SMD")
    if args.verify_only:
        result = verify(config)
    else:
        try:
            result = verify(config)
        except (OSError, ValueError, KeyError):
            result = download(config)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/smd_sources.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Verified {len(result['files'])} SMD files at {result['revision']}")
