"""Fetch currently available posts through your own pyXcom browser session.

The public download contains IDs only. Deleted/unavailable posts may not return;
missing IDs here are not proof of deletion. Raw output remains local.
"""

import argparse
import hashlib
import json
from pathlib import Path
from pyxcom import XClient, iter_post_ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shard", type=Path, help="Two-file pyXcom ID shard")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--browser", default="chrome")
    parser.add_argument("--proxy")
    parser.add_argument(
        "--max-batches", type=int, default=1, help="At most 50 requested IDs per batch"
    )
    args = parser.parse_args()
    if args.max_batches < 1:
        raise ValueError("max-batches must be positive")
    output = args.output.expanduser().resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("Hydrated content must stay outside the public repository")
    ids = list(iter_post_ids(args.shard))
    selected = ids[: 50 * args.max_batches]
    output.mkdir(parents=True, exist_ok=False)
    retained = set()
    reason = "request_budget"
    # Login stays manual; never serialize the browser session.
    try:
        with XClient.from_login(
            browser=args.browser,
            profile=args.profile,
            proxy=args.proxy,
            timeout=15,
            delay=1,
        ) as client:
            with (output / "posts.jsonl").open("x", encoding="utf-8") as stream:
                for start in range(0, len(selected), 50):
                    batch = selected[start : start + 50]
                    for post in client.get_posts(batch):
                        if post.id in batch and post.id not in retained:
                            stream.write(
                                json.dumps(post.to_dict(), ensure_ascii=False) + "\n"
                            )
                            retained.add(post.id)
        reason = "finished_requested_ids"
    finally:
        manifest = {
            "requested_count": len(selected),
            "available_count": len(retained),
            "not_returned_ids": sorted(set(selected) - retained, key=int),
            "reason": reason,
            "source_total_ids": len(ids),
            "source_id_sha256": hashlib.sha256(
                (args.shard / "post_ids.csv").read_bytes()
            ).hexdigest(),
            "missing_is_not_proof_of_deletion": True,
        }
        (output / "rehydration_manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )
        print(
            json.dumps({k: v for k, v in manifest.items() if k != "not_returned_ids"})
        )


if __name__ == "__main__":
    main()
