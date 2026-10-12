"""Build ID-only public corpora from validated pyXcom collections; no network."""

import argparse
import csv
import hashlib
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from pyxcom import (
    export_post_ids,
    iter_post_ids,
    validate_collection,
    validate_id_dataset,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_group(name, sources, destination):
    destination.mkdir(parents=True, exist_ok=False)
    ids = set()
    scopes = []
    for source in sorted(sources):
        validation = validate_collection(source)
        if not validation["valid"]:
            raise ValueError("Source failed package validation: " + source.name)
        # Conversation membership is not published per root; only the union is public.
        with tempfile.TemporaryDirectory(prefix="pyxcom-id-export-") as temporary:
            shard = (
                (Path(temporary) / "ids")
                if name == "institution_conversations"
                else destination / "strata" / source.name
            )
            exported = export_post_ids(source, shard)
            validate_id_dataset(shard)
            ids.update(iter_post_ids(shard))
        scope_name = (
            f"conversation_{len(scopes) + 1:03d}"
            if name == "institution_conversations"
            else source.name
        )
        scopes.append(
            {
                "stratum": scope_name,
                "retained_analysis_ids": exported["count"],
                "collection_complete": exported["collection_complete"],
                "coverage_complete": False,
                "id_sha256": exported["sha256"],
                "source_fingerprint": exported["source_fingerprint"],
            }
        )
    file = destination / "post_ids.csv"
    file.write_text("post_id\n" + "".join(i + "\n" for i in sorted(ids, key=int)))
    manifest = {
        "schema": "ai-open-research-corpus/1",
        "name": name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(ids),
        "stratum_record_sum": sum(x["retained_analysis_ids"] for x in scopes),
        "post_ids_sha256": digest(file),
        "strata": scopes,
        "coverage_complete": False,
        "unit": "unique retained analysis or seed post ID; context records excluded",
        "content_license": "No license to X post content is granted; rehydration requires your own lawful access.",
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def local_personal_csv(personal, destination):
    records = {}
    fields = [
        "post_id",
        "products",
        "created_at_utc",
        "author_handle",
        "post_role",
        "post_type",
        "text",
        "url",
        "language",
        "in_reply_to_id",
        "conversation_id",
        "like_count",
        "reply_count",
        "repost_count",
        "quote_count",
        "view_count",
        "captured_at_utc",
    ]
    for source in sorted(personal.glob("personal_*")):
        product = source.name[len("personal_") : -11]
        for line in (source / ".pyxcom/posts.jsonl").read_text().split("\n"):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("observation_role") == "context":
                continue
            entry = records.setdefault(r["id"], {"record": r, "products": set()})
            entry["products"].add(product)
    with destination.open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for key, entry in sorted(records.items(), key=lambda item: int(item[0])):
            row = {field: entry["record"].get(field) for field in fields}
            row.update(post_id=key, products=";".join(sorted(entry["products"])))
            writer.writerow(row)
    return len(records)


def check_local_destination(path, source_roots, public_root):
    destination = path.expanduser().resolve()
    if path.is_symlink() or destination.exists():
        raise FileExistsError("Local text export must use a new file")
    for root in (*source_roots, public_root):
        root = root.resolve()
        if destination.is_relative_to(root) or root.is_relative_to(destination):
            raise ValueError(
                "Local text export must remain outside source collections and public release"
            )
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collections", type=Path, required=True)
    parser.add_argument("--personal-collections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-personal-csv", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("Release output must be new")
    sources = args.collections.resolve()
    personal = args.personal_collections.resolve()
    if args.local_personal_csv:
        args.local_personal_csv = check_local_destination(
            args.local_personal_csv, (sources, personal), output.parent
        )
    for source in (sources, personal):
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError("Public release and raw scopes must not overlap")
    groups = {
        "institution_voices": list(sources.glob("institution_*")),
        "ai_discourse": list(sources.glob("discourse_*")),
        "institution_conversations": list(sources.glob("conversation_*")),
    }
    for product in ("meta_muse", "openai_dots", "grok_bot"):
        groups["personal_" + product] = list(
            personal.glob("personal_" + product + "_*")
        )
    output.mkdir(parents=True, exist_ok=False)
    summary = {}
    for name, scopes in groups.items():
        if not scopes:
            raise ValueError("Missing collection group: " + name)
        summary[name] = build_group(name, scopes, output / name)
    # Count cross-product duplicates rather than summing product totals blindly.
    all_ids = set()
    for name in groups:
        if name.startswith("personal_"):
            with (output / name / "post_ids.csv").open() as stream:
                all_ids.update(r["post_id"] for r in csv.DictReader(stream))
    summary_file = {
        "schema": "ai-open-research-index/1",
        "datasets": {
            k: {"count": v["count"], "strata": len(v["strata"])}
            for k, v in summary.items()
        },
        "personal_agent_union_count": len(all_ids),
        "coverage_complete": False,
    }
    (output / "index.json").write_text(json.dumps(summary_file, indent=2) + "\n")
    if args.local_personal_csv:
        summary_file["local_personal_rows"] = local_personal_csv(
            personal, args.local_personal_csv
        )
    print(json.dumps(summary_file, indent=2))


if __name__ == "__main__":
    main()
