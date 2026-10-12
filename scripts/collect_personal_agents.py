"""Collect the prespecified personal-agent search strata using pyXcom only."""

import argparse
import json
from pathlib import Path
from pyxcom import XClientPool, LoginConfig, CollectionJob


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parents[1] / "config/personal_agents.json",
    )
    parser.add_argument("--profiles", nargs="+", required=True)
    parser.add_argument("--proxy")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    private = args.private_dir.expanduser().resolve()
    if private.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("Raw records must remain outside the public release")
    private.mkdir(parents=True, exist_ok=True)
    logins = [
        LoginConfig("session_" + str(i), profile=p) for i, p in enumerate(args.profiles)
    ]
    jobs = [
        CollectionJob(
            f"personal_{product['key']}_{since}",
            "search_query",
            product["query"],
            private / "collections" / f"personal_{product['key']}_{since}",
            options={"since": since, "until": until},
        )
        for product in config["products"]
        for since, until in config["intervals"]
    ]
    with XClientPool(
        logins,
        state_dir=private / "queue",
        client_options={
            "delay": config["delay"],
            "timeout": config["timeout"],
            "proxy": args.proxy,
        },
    ) as pool:
        pool.add_jobs(jobs)
        report = pool.run(
            page_budget=config["pages_per_stratum"],
            max_workers=config["max_workers"],
            max_steps=len(jobs),
            max_seconds=config["max_seconds"],
        )
    (private / "collection_report.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                "steps": report["steps"],
                "jobs": {
                    key: {"reason": job["reason"], "result": job.get("result")}
                    for key, job in report["jobs"].items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
