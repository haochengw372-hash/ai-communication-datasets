"""Offline validation of ID unions, export schemas, aggregate thresholds and hashes."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from pyxcom import validate_id_dataset, iter_post_ids


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root):
    root = root.resolve()
    index = json.loads((root / "data/index.json").read_text())
    if {p.name for p in (root / "data").iterdir()} != set(index["datasets"]) | {
        "index.json"
    }:
        raise ValueError("Unexpected data directory contents")
    union = set()
    rows = {}
    shard_count = 0
    for name, expected in index["datasets"].items():
        folder = root / "data" / name
        m = json.loads((folder / "manifest.json").read_text())
        with (folder / "post_ids.csv").open() as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != ["post_id"]:
                raise ValueError("Unexpected ID fields")
            ids = [r["post_id"] for r in reader]
        if any(not i.isdecimal() or i.startswith("0") or int(i) >= 2**64 for i in ids):
            raise ValueError("Invalid ID")
        if (
            ids != sorted(set(ids), key=int)
            or len(ids) != m["count"]
            or len(ids) != expected["count"]
        ):
            raise ValueError("ID union count/order mismatch")
        if (
            digest(folder / "post_ids.csv") != m["post_ids_sha256"]
            or m["coverage_complete"] is not False
        ):
            raise ValueError("Union hash/coverage mismatch")
        if len(m["strata"]) != expected["strata"]:
            raise ValueError("Scope count mismatch")
        if name == "institution_conversations":
            if {p.name for p in folder.iterdir()} != {"post_ids.csv", "manifest.json"}:
                raise ValueError("Conversation membership must not be published")
            if any(
                s["stratum"] != f"conversation_{i:03d}"
                for i, s in enumerate(m["strata"], 1)
            ):
                raise ValueError("Conversation labels must be anonymous")
        else:
            merged = set()
            if {p.name for p in folder.iterdir()} != {
                "post_ids.csv",
                "manifest.json",
                "strata",
            }:
                raise ValueError("Unexpected group contents")
            if {p.name for p in (folder / "strata").iterdir()} != {
                s["stratum"] for s in m["strata"]
            }:
                raise ValueError("Unexpected strata")
            for scope in m["strata"]:
                path = folder / "strata" / scope["stratum"]
                record = validate_id_dataset(path)
                if (
                    record["count"] != scope["retained_analysis_ids"]
                    or record["sha256"] != scope["id_sha256"]
                ):
                    raise ValueError("Stratum metadata mismatch")
                merged.update(iter_post_ids(path))
                shard_count += 1
            if merged != set(ids):
                raise ValueError("Strata and group union differ")
        if name.startswith("personal_"):
            union.update(ids)
        rows[name] = len(ids)
    if len(union) != index["personal_agent_union_count"]:
        raise ValueError("Personal union mismatch")
    forbidden = {
        "text",
        "author_id",
        "author_handle",
        "observer_id",
        "observer_login_id",
        "password",
        "auth_token",
        "ct0",
    }
    for path in (root / "aggregate").glob("*.csv"):
        with path.open() as f:
            reader = csv.DictReader(f)
            if forbidden.intersection(reader.fieldnames or []):
                raise ValueError("Unsafe aggregate fields")
            for row in reader:
                for key in ("count", "post_count", "weight"):
                    if key in row and int(row[key]) < 3:
                        raise ValueError("Aggregate threshold violation")
    for name in ("SHA256.json", "replications/analysis_outputs.json"):
        inventory = root / name
        if inventory.exists():
            hashes = json.loads(inventory.read_text())
            if name == "replications/analysis_outputs.json":
                if hashes["script_sha256"] != digest(root / "scripts/analyze.py"):
                    raise ValueError("Analysis code hash mismatch")
                hashes = hashes["sha256"]
            for relative, value in hashes.items():
                path = (root / relative).resolve()
                if (
                    not path.is_relative_to(root)
                    or not path.is_file()
                    or digest(path) != value
                ):
                    raise ValueError("Inventory hash mismatch: " + relative)
    return {
        "valid": True,
        "datasets": rows,
        "verified_shards": shard_count,
        "personal_union": len(union),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    args = parser.parse_args()
    print(json.dumps(validate(args.root), indent=2))
