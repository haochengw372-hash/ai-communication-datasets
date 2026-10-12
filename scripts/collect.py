"""Reproduce the frozen bounded collection through pyXcom, using manual logins."""

import argparse
import json
from pathlib import Path

from pyxcom import CollectionJob, LoginConfig, XClientPool


def build_search_jobs(config, private):
    jobs = []
    for item in config["institutions"]:
        for since, until in config["institution_intervals"]:
            name = f"institution_{item['handle']}_{since}"
            jobs.append(
                CollectionJob(
                    name,
                    "search_query",
                    f"from:{item['handle']}",
                    private / "collections" / name,
                    options={"since": since, "until": until},
                )
            )
    for item in config["discourse_queries"]:
        for since, until in config["discourse_intervals"]:
            name = f"discourse_{item['name']}_{since}"
            jobs.append(
                CollectionJob(
                    name,
                    "search_query",
                    item["query"],
                    private / "collections" / name,
                    options={"since": since, "until": until},
                )
            )
    return jobs


def choose_conversations(config, private):
    candidates, selected = [], []
    for account in config["institutions"]:
        handle = account["handle"]
        source = (
            private
            / "collections"
            / f"institution_{handle}_2026-09-01"
            / ".pyxcom/posts.jsonl"
        )
        rows = (
            [
                json.loads(line)
                for line in source.read_text().split("\n")
                if line.strip()
            ]
            if source.exists()
            else []
        )
        eligible = []
        for row in rows:
            ok = (
                row["post_role"] == "main"
                and row["post_type"] == "original"
                and (row.get("reply_count") or 0) >= 3
            )
            candidates.append(
                {
                    "handle": handle,
                    "post_id": row["id"],
                    "created_at_utc": row["created_at_utc"],
                    "eligible": ok,
                    "rule": "original main with observed reply_count >=3",
                }
            )
            if ok:
                eligible.append(row)
        eligible.sort(key=lambda x: (x["created_at_utc"], int(x["id"])))
        if eligible:
            for row in {
                eligible[0]["id"]: eligible[0],
                eligible[-1]["id"]: eligible[-1],
            }.values():
                selected.append(
                    {
                        "handle": handle,
                        "post_id": row["id"],
                        "created_at_utc": row["created_at_utc"],
                    }
                )
    (private / "root_sampling_frame.json").write_text(json.dumps(candidates, indent=2))
    (private / "selected_roots.json").write_text(json.dumps(selected, indent=2))
    return [
        CollectionJob(
            "conversation_" + row["post_id"],
            "post_comments",
            row["post_id"],
            private / "collections" / ("conversation_" + row["post_id"]),
            options={
                "max_depth": config["conversation_max_depth"],
                "max_comments": config["conversation_max_comments"],
            },
        )
        for row in selected
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parents[1] / "config/sampling.json",
    )
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--profiles", nargs="+", required=True)
    parser.add_argument("--proxy")
    parser.add_argument(
        "--stage", choices=["search", "discourse", "conversations"], required=True
    )
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    private = args.private_dir.expanduser().resolve()
    private.mkdir(parents=True, exist_ok=True)
    if private.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("Raw data must remain outside the public release directory")
    jobs = (
        build_search_jobs(config, private)
        if args.stage in ("search", "discourse")
        else choose_conversations(config, private)
    )
    if args.stage == "discourse":
        jobs = [j for j in jobs if j.job_id.startswith("discourse_")]
    # Profile labels are local credential locations and are not included in public datasets.
    logins = [
        LoginConfig("session_" + str(i), profile=profile)
        for i, profile in enumerate(args.profiles)
    ]
    with XClientPool(
        logins,
        state_dir=private / ("queue_" + args.stage),
        client_options={
            "proxy": args.proxy,
            "delay": config["delay_seconds"],
            "timeout": config["request_timeout_seconds"],
        },
    ) as pool:
        pool.add_jobs(jobs)
        report = pool.run(
            max_workers=config["workers"],
            page_budget=config["pages_per_stratum"]
            if args.stage in ("search", "discourse")
            else config["conversation_page_budget"],
            max_steps=len(jobs),
            max_seconds=config["dispatch_seconds_limit"],
            wait_on_rate_limit=False,
        )
    (private / (args.stage + "_report.json")).write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                "stage": args.stage,
                "steps": report["steps"],
                "jobs": {
                    k: {
                        "status": v["status"],
                        "reason": v["reason"],
                        "result": v.get("result"),
                    }
                    for k, v in report["jobs"].items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
