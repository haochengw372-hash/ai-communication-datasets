#!/usr/bin/env python3
"""Bounded literature-method adaptations from retained pyXcom records.

Input stays private. Public outputs contain aggregates and a header-only coding
form, never post text, author IDs, or root/reply pairs. No network calls.
"""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
from pathlib import Path
import platform
import re
from urllib.parse import urlsplit

MIN_COUNT = 3


def unique_analysis(records):
    """Retain first observation per canonical post ID, matching package policy."""
    unique = {}
    duplicate = context = 0
    for row in records:
        if row.get("observation_role") == "context":
            context += 1
            continue
        pid = row.get("id")
        if not isinstance(pid, str) or not pid.strip():
            raise ValueError("Canonical input requires a nonempty string id")
        if pid in unique:
            duplicate += 1
        else:
            unique[pid] = row
    return list(unique.values()), duplicate, context


def safe_token(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 64
        and all(c.isalnum() or c == "_" for c in value)
    )


def safe_domain(value):
    return (
        isinstance(value, str)
        and len(value) <= 253
        and "." in value
        and all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
            for part in value.split(".")
        )
        and not re.fullmatch(r"[0-9.]+", value)
    )


def suppress(counts, domain=False, edge=False):
    """Privacy threshold is publication-only; denominators precede suppression."""
    kept = []
    report = {
        "threshold": MIN_COUNT,
        "all_terms": len(counts),
        "all_incidence": sum(counts.values()),
        "unsafe_terms": 0,
        "unsafe_incidence": 0,
        "below_threshold_terms": 0,
        "below_threshold_incidence": 0,
    }
    for key, count in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        safe = (
            all(safe_token(x) for x in key)
            if edge
            else (safe_domain(key) if domain else safe_token(key))
        )
        reason = (
            "unsafe" if not safe else ("below_threshold" if count < MIN_COUNT else None)
        )
        if reason:
            report[reason + "_terms"] += 1
            report[reason + "_incidence"] += count
        else:
            kept.append((key, count))
    report["published_terms"] = len(kept)
    report["published_incidence"] = sum(count for _, count in kept)
    return kept, report


def discourse(records, include_reposts=False):
    records, duplicates, contexts = unique_analysis(records)
    main = [
        r
        for r in records
        if include_reposts
        or (r.get("post_role") != "repost" and not r.get("reposted_post_id"))
    ]
    result = {
        key: Counter()
        for key in (
            "case_sensitive",
            "casefold",
            "edges",
            "domains",
            "post_types_all",
            "post_types_primary",
            "language",
            "missing",
            "url_rejections",
        )
    }
    for row in records:
        kind = row.get("post_type")
        result["post_types_all"][
            kind if kind in ("original", "quote", "reply", "repost") else "unknown"
        ] += 1
    for row in main:
        kind = row.get("post_type")
        result["post_types_primary"][
            kind if kind in ("original", "quote", "reply", "repost") else "unknown"
        ] += 1
        language = row.get("language")
        result["language"][
            language
            if isinstance(language, str) and re.fullmatch(r"[a-z]{2,3}", language)
            else "missing"
            if not language
            else "invalid"
        ] += 1
        for field in ("hashtags", "outbound_urls"):
            if row.get(field) is not None and not isinstance(row[field], list):
                raise ValueError(
                    "Structured hashtag and URL fields must be lists or null"
                )
        for field in ("language", "created_at_utc", "hashtags", "outbound_urls"):
            if row.get(field) is None or row.get(field) == "":
                result["missing"][field] += 1
        for field in ("hashtags", "outbound_urls"):
            if row.get(field) == []:
                result["missing"][field + "_empty_list"] += 1
        tags = {x for x in (row.get("hashtags") or []) if isinstance(x, str) and x}
        result["case_sensitive"].update(tags)
        folded = {t.casefold() for t in tags}
        result["casefold"].update(folded)
        result["edges"].update(
            combinations(sorted(folded - {"ai", "artificialintelligence"}), 2)
        )
        domains = set()
        for url in row.get("outbound_urls") or []:
            try:
                parts = urlsplit(url)
                host = parts.hostname
                if parts.scheme not in ("http", "https") or not host:
                    reason = "invalid"
                elif parts.username or parts.password:
                    reason = "userinfo"
                elif host.lower().rstrip(".") in ("t.co", "www.t.co"):
                    reason = "shortener"
                else:
                    domains.add(host.lower().rstrip("."))
                    continue
            except (TypeError, ValueError):
                reason = "invalid"
            result["url_rejections"][reason] += 1
        result["domains"].update(domains)
    result["denominators"] = {
        "unique_analysis_posts": len(records),
        "primary_non_reposts": len(main),
        "excluded_reposts": len(records) - len(main),
        "duplicate_observations": duplicates,
        "excluded_context_observations": contexts,
    }
    return result


def conversation(records, root_id):
    # Context ancestors may establish a chain but never enter reply denominators.
    index = {}
    for row in records:
        if isinstance(row.get("id"), str) and row["id"]:
            index.setdefault(row["id"], row)
    records, duplicates, contexts = unique_analysis(records)
    index.update({r["id"]: r for r in records})
    root = index.get(root_id)
    comments = [
        r for r in records if r["id"] != root_id and r.get("post_role") == "comment"
    ]
    ancestry, depths, relations = Counter(), Counter(), Counter()
    for row in comments:
        author = row.get("author_id")
        root_author = root.get("author_id") if root else None
        relations[
            "unknown"
            if not author or not root_author
            else "root_author"
            if author == root_author
            else "other_author"
        ] += 1
        current, seen, depth = row, set(), 0
        while True:
            cid = current["id"]
            if cid in seen:
                status = "cycle"
                break
            seen.add(cid)
            if current.get("conversation_id") and current["conversation_id"] != root_id:
                status = "root_mismatch"
                break
            parent = current.get("in_reply_to_id")
            if not parent:
                status = "missing_parent"
                break
            depth += 1
            if parent == root_id:
                status = "resolved" if root else "missing_root"
                if root:
                    depths[depth] += 1
                break
            if parent not in index:
                status = "missing_parent"
                break
            current = index[parent]
        ancestry[status] += 1
    return {
        "root_present": bool(root),
        "retained_comments": len(comments),
        "resolved_comments": ancestry["resolved"],
        "ancestry": dict(ancestry),
        "depths": dict(depths),
        "author_relation": dict(relations),
        "manual_sample_eligible": ancestry["resolved"] >= 3,
        "duplicate_observations": duplicates,
        "excluded_context_observations": contexts,
    }


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_scope(path):
    source = path / ".pyxcom/posts.jsonl"
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    expected = manifest.get("source_sha256", {}).get(".pyxcom/posts.jsonl")
    if not expected or digest(source) != expected:
        raise ValueError(
            "Source hash mismatch or absent; collection must be finished before analysis"
        )
    for name, expected_hash in manifest.get("sha256", {}).items():
        if Path(name).name != name or digest(path / name) != expected_hash:
            raise ValueError("Export hash mismatch or unsafe manifest filename")
    # JSONL uses LF delimiters; Unicode U+2028/U+0085/U+2029 inside JSON
    # strings are content, not record boundaries.
    records = [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").split("\n")
        if line.strip()
    ]
    coverage = {
        k: manifest.get(k)
        for k in ("pages_fetched", "complete", "reason", "date_scope")
    }
    coverage["source_sha256"] = expected
    coverage["manifest_sha256"] = digest(manifest_path)
    return records, manifest, coverage


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def run(project, collections=None):
    contract = json.loads(
        (project / ".codex-research/contracts/first-open-edition.json").read_text()
    )
    state = json.loads((project / ".codex-research/state.yaml").read_text())
    if state["revision"] != contract["state_revision"] or state["revision"] != 0:
        raise ValueError(
            "Analysis contract revision changed; obtain controller handoff"
        )
    return _run_analysis(
        project / "release",
        collections or project / "private/collections",
        project / "literature/methods.json",
        execution_mode="governed",
        state_revision=0,
    )


def run_portable(release, collections):
    return _run_analysis(
        release,
        collections,
        release / "references/methods.json",
        execution_mode="portable",
        state_revision=None,
    )


def _run_analysis(
    release, collections, methods_path, *, execution_mode, state_revision
):
    # Validate required portable inputs before producing any results.
    sampling_hash = digest(release / "config/sampling.json")
    methods_hash = digest(methods_path)
    out = release / "aggregate"
    rep = release / "replications"
    sources, records = [], []
    scopes = sorted(collections.glob("discourse_*"))
    if not scopes:
        raise ValueError("No discourse scopes found in selected collection directory")
    for number, scope in enumerate(scopes, 1):
        rows, manifest, coverage = read_scope(scope)
        records.extend(rows)
        coverage["scope"] = f"discourse_{number:02d}"
        # Query labels are the frozen AI / ChatGPT terms, never user-generated text.
        coverage["query"] = manifest.get("query", {})
        sources.append(coverage)
    result = discourse(records)
    suppression = {}
    specs = [
        ("hashtag_counts", "case_sensitive", "hashtag"),
        ("hashtag_casefold_counts", "casefold", "hashtag"),
        ("domain_counts", "domains", "hostname"),
        ("hashtag_edges", "edges", "source"),
    ]
    for filename, key, column in specs:
        kept, suppression[filename] = suppress(
            result[key], domain=key == "domains", edge=key == "edges"
        )
        rows = [(a, b, count) for (a, b), count in kept] if key == "edges" else kept
        fields = (
            ["source", "target", "post_incidence"]
            if key == "edges"
            else [column, "post_incidence"]
        )
        write_csv(out / f"{filename}.csv", fields, rows)
    node_incidence = Counter()
    for (left, right), weight in result["edges"].items():
        node_incidence[left] += weight
        node_incidence[right] += weight
    # Nodes must themselves meet post-incidence suppression; edge degree is not
    # a post count and is explicitly labelled in the exported graph.
    nodes, suppression["hashtag_nodes"] = suppress(
        {k: result["casefold"][k] for k in node_incidence}
    )
    write_csv(
        out / "hashtag_nodes.csv",
        ["hashtag", "post_incidence", "weighted_degree_before_edge_suppression"],
        [(key, count, node_incidence[key]) for key, count in nodes],
    )
    all_retained = discourse(records, include_reposts=True)
    for filename, key, column in specs:
        kept, suppression["all_retained_" + filename] = suppress(
            all_retained[key], domain=key == "domains", edge=key == "edges"
        )
        rows = [(a, b, count) for (a, b), count in kept] if key == "edges" else kept
        fields = (
            ["source", "target", "post_incidence"]
            if key == "edges"
            else [column, "post_incidence"]
        )
        write_csv(out / ("all_retained_" + filename + ".csv"), fields, rows)
    category_rows = []
    for label, key in [
        ("all_retained", "post_types_all"),
        ("non_repost", "post_types_primary"),
    ]:
        category_rows.extend(
            (label, kind, count)
            for kind, count in sorted(result[key].items())
            if count >= MIN_COUNT
        )
    write_csv(
        out / "post_type_counts.csv", ["scope", "post_type", "count"], category_rows
    )
    write_csv(
        out / "language_counts.csv",
        ["language", "non_repost_count"],
        [
            (key, count)
            for key, count in sorted(result["language"].items())
            if count >= MIN_COUNT
        ],
    )
    common = {
        "claim": "new_sample_method_adaptation_only",
        "python": platform.python_version(),
        "state_revision": state_revision,
        "execution_mode": execution_mode,
        "analysis_script_sha256": digest(Path(__file__)),
        "sampling_config_sha256": sampling_hash,
        "literature_methods_sha256": methods_hash,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "publication_threshold": MIN_COUNT,
        "privacy": "No text, author IDs, or root-reply pairs published; aggregate term incidence threshold is not a formal anonymity guarantee.",
    }
    write_json(
        rep / "kaiser_green_2026/replication_manifest.json",
        {
            **common,
            "doi": "10.5210/fm.v31i4.14436",
            "status": "executed" if records else "executed_empty_retained_sample",
            "network_export_status": "public_edges_available"
            if suppression["hashtag_edges"]["published_terms"]
            else "no_edges_survive_publication_threshold",
            "denominators": result["denominators"],
            "missingness_non_reposts": result["missing"],
            "post_types_all_unsuppressed": result["post_types_all"],
            "post_types_primary_unsuppressed": result["post_types_primary"],
            "language_unsuppressed": result["language"],
            "url_rejections_non_reposts": result["url_rejections"],
            "suppression": suppression,
            "sources": sources,
            "host_normalization": "lowercase and remove trailing dot; preserve www; hostname not registrable domain; no redirects",
            "canonical_policy": "first analysis observation per post ID in lexicographic scope order, then saved record order",
            "language_policy": "Retain returned missing/other languages and report separately; lang:en is the requested source filter, not inferred English.",
            "sensitivity": "all_retained_* term and edge tables include native reposts; primary tables exclude them; equal if no reposts retained.",
            "not_replicated": [
                "original 2023 results",
                "GPT sentiment",
                "retweet network",
                "Gephi community structure",
            ],
        },
    )
    conv_results, conv_sources = [], []
    observed_reply_authors = set()
    unique_comment_ids = set()
    selected_path = collections.parent / "selected_roots.json"
    selected = json.loads(selected_path.read_text()) if selected_path.exists() else []
    selected_ids = {str(r["post_id"]) for r in selected}
    for number, scope in enumerate(sorted(collections.glob("conversation_*")), 1):
        rows, manifest, coverage = read_scope(scope)
        root_id = scope.name.removeprefix("conversation_")
        if not root_id.isdigit() or root_id not in selected_ids:
            raise ValueError(
                "Conversation scope must match the frozen private selected_roots list"
            )
        scope_records, _, _ = unique_analysis(rows)
        for row in scope_records:
            if row.get("post_role") == "comment":
                unique_comment_ids.add(row["id"])
                if row.get("author_id"):
                    observed_reply_authors.add(row["author_id"])
        conv_results.append(conversation(rows, str(root_id)))
        coverage["scope"] = f"conversation_{number:02d}"
        conv_sources.append(coverage)
    sums = Counter()
    distribution = Counter()
    for r in conv_results:
        for field in (
            "retained_comments",
            "resolved_comments",
            "root_present",
            "manual_sample_eligible",
        ):
            sums[field] += r[field]
        for group in ("ancestry", "depths", "author_relation"):
            for key, count in r[group].items():
                sums[f"{group}:{key}"] += count
        distribution[r["retained_comments"]] += 1
    sums["unique_reply_authors_known"] = len(observed_reply_authors)
    sums["unique_retained_comment_ids"] = len(unique_comment_ids)
    sums["direct_resolved_comments"] = sums.get("depths:1", 0)
    sums["deeper_resolved_comments"] = sum(
        v
        for k, v in sums.items()
        if k.startswith("depths:") and int(k.split(":")[1]) >= 2
    )
    total_comments = sums.get("retained_comments", 0)
    ratios = {}
    for name, numerator in (
        ("unresolved_ancestry", total_comments - sums.get("resolved_comments", 0)),
        ("self_reply", sums.get("author_relation:root_author", 0)),
        ("unknown_author_relation", sums.get("author_relation:unknown", 0)),
    ):
        ratios[name] = {
            "numerator": numerator,
            "denominator": total_comments,
            "fraction": numerator / total_comments if total_comments else None,
        }
    write_csv(
        out / "conversation_structure.csv",
        ["measure", "count"],
        [(key, count) for key, count in sorted(sums.items()) if count >= MIN_COUNT],
    )
    write_csv(
        out / "conversation_size_distribution.csv",
        ["retained_reply_count", "root_count"],
        [
            (key, count)
            for key, count in sorted(distribution.items())
            if count >= MIN_COUNT
        ],
    )
    write_csv(
        rep / "hara_et_al_2025/role_annotation_template.csv",
        [
            "local_root_key",
            "local_comment_key",
            "role_code",
            "coder_id",
            "evidence",
            "reference",
        ],
        [],
    )
    write_json(
        rep / "hara_et_al_2025/replication_manifest.json",
        {
            **common,
            "doi": "10.22323/2.24010202",
            "status": "executed"
            if conv_results
            else "awaiting_conversation_collections",
            "design": "organization-public conversation structure adaptation; institutions are not screened or coded as scientists",
            "collection_scopes": len(conv_results),
            "counts": sums,
            "sources": conv_sources,
            "ratios_over_all_retained_scope_replies": ratios,
            "retained_reply_distribution_unsuppressed": distribution,
            "selected_roots": len(selected_ids),
            "selected_roots_file_sha256": digest(selected_path)
            if selected_path.exists()
            else None,
            "manual_sample_rule": "at least 3 actually retained replies with a parent chain resolved to the retained root",
            "reply_author_labels": "root_author / other_author / unknown; other authors are not assumed laypersons",
            "not_replicated": [
                "original sample and results",
                "expert profile screening",
                "manual semantic role coding",
                "Biterm Topic Model",
                "negative binomial regressions",
            ],
            "ancestry_policy": "Context records may resolve observed ancestor links but do not enter reply denominators.",
            "coverage": "Observed retained records only; unresolved ancestry and limited depth/page/sample caps prevent conversation completeness claims.",
        },
    )
    (rep / "RESULTS.md").write_text(
        "# Executed adaptation results\n\n"
        f"Discourse: {len(scopes)} bounded search strata retained "
        f"{result['denominators']['unique_analysis_posts']} distinct analysis post IDs after "
        f"{result['denominators']['duplicate_observations']} duplicate observations were removed. "
        f"{result['denominators']['primary_non_reposts']} enter the non-repost primary analysis.\n\n"
        f"Before publication suppression, the casefold network has {len(result['edges'])} "
        f"distinct edges. At incidence >= {MIN_COUNT}, "
        f"{suppression['hashtag_edges']['published_terms']} edges and "
        f"{suppression['hashtag_nodes']['published_terms']} nodes remain publishable. "
        "Empty public tables reflect the declared suppression rule, not a claim that no hashtags "
        "occurred. This sample cannot establish AI discourse communities or population prevalence.\n\n"
        f"Conversations: {len(conv_results)} collected scopes contain {total_comments} retained "
        f"replies from {len(observed_reply_authors)} known distinct reply authors. "
        f"{sums.get('resolved_comments', 0)} replies have ancestry resolved to retained roots; "
        f"{sums['direct_resolved_comments']} are direct and {sums['deeper_resolved_comments']} deeper. "
        f"{sums.get('author_relation:root_author', 0)} are root-author replies, "
        f"{sums.get('author_relation:other_author', 0)} other-author replies, and "
        f"{sums.get('author_relation:unknown', 0)} have unknown author relation. "
        f"{sums.get('manual_sample_eligible', 0)} roots meet the rule of at least three actually "
        "retained, resolved replies. These counts describe available bounded branches and do not "
        "establish complete conversations.\n\n"
        "Both methods ran on a new sample. Original-data findings, expert-versus-layperson labels, "
        "semantic roles, topic models, and regression effects were not reproduced. See the "
        "deviation matrix and manifests for denominators, suppression, hashes, and coverage.\n",
        encoding="utf-8",
    )
    outputs = {}
    for folder in (out, rep):
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.name != "analysis_outputs.json":
                outputs[str(path.relative_to(release))] = digest(path)
    write_json(
        rep / "analysis_outputs.json",
        {"sha256": outputs, "script_sha256": digest(Path(__file__))},
    )
    print(
        json.dumps(
            {
                "discourse": result["denominators"],
                "conversation_scopes": len(conv_results),
                "conversation_counts": sums,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--project",
        type=Path,
        help="Private governed project containing release/ and the revision contract",
    )
    mode.add_argument(
        "--release-root",
        type=Path,
        help="Portable cloned release repository containing config/ and references/",
    )
    parser.add_argument(
        "--collections",
        type=Path,
        help="Authoritative private collection directory; no legacy/new-run merging",
    )
    args = parser.parse_args()
    collections = args.collections.resolve() if args.collections else None
    if args.project:
        run(args.project.resolve(), collections)
    else:
        if collections is None:
            parser.error(
                "Portable mode requires --collections pointing to locally retained canonical records"
            )
        release = (
            args.release_root.resolve()
            if args.release_root
            else Path(__file__).resolve().parents[1]
        )
        run_portable(release, collections)
