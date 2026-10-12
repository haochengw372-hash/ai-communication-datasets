"""Synthetic fixtures only: no network, private text, or user credentials."""

import importlib.util
from pathlib import Path
import unittest
import json
import tempfile
import subprocess
import sys

SPEC = importlib.util.spec_from_file_location(
    "analysis", Path(__file__).parents[1] / "scripts" / "analyze.py"
)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def post(pid, **kw):
    return {
        "id": str(pid),
        "post_role": "main",
        "post_type": "original",
        "author_id": "a",
        "observation_role": "analysis",
        "language": "en",
        "created_at_utc": "2026-09-05T00:00:00Z",
        "hashtags": [],
        "outbound_urls": [],
        **kw,
    }


class AnalysisTests(unittest.TestCase):
    def test_unique_keys_reposts_context_and_missing(self):
        result = analysis.discourse(
            [
                post(1),
                post(1),
                post(2, language=None),
                post(3, post_role="repost"),
                post(4, observation_role="context"),
            ]
        )
        self.assertEqual(result["denominators"]["unique_analysis_posts"], 3)
        self.assertEqual(result["denominators"]["primary_non_reposts"], 2)
        self.assertEqual(result["denominators"]["duplicate_observations"], 1)
        self.assertEqual(result["missing"]["language"], 1)
        self.assertEqual(result["language"]["missing"], 1)

    def test_hashtags_are_post_incidence_not_occurrences(self):
        r = analysis.discourse(
            [
                post(
                    1, hashtags=["AI", "Ai", "ai", "Robot", "Robot", "robot", "Policy"]
                ),
                post(2, hashtags=["Robot", "Policy"]),
            ]
        )
        self.assertEqual(r["case_sensitive"]["Robot"], 2)
        self.assertEqual(r["casefold"]["robot"], 2)
        self.assertEqual(r["edges"], {("policy", "robot"): 2})
        self.assertEqual(r["casefold"]["ai"], 1)

    def test_domains_never_infer_short_urls(self):
        r = analysis.discourse(
            [
                post(
                    1,
                    outbound_urls=[
                        "https://WWW.Example.com/a",
                        "https://www.example.com/b",
                        "https://t.co/abcd",
                        "https://user@example.com/",
                        "https://example.org/path?email=a@b.c",
                    ],
                )
            ]
        )
        self.assertEqual(r["domains"], {"www.example.com": 1, "example.org": 1})
        self.assertEqual(r["url_rejections"]["shortener"], 1)
        self.assertEqual(r["url_rejections"]["userinfo"], 1)

    def test_suppression_and_token_safety(self):
        rows, report = analysis.suppress(
            {"valid": 3, "rare": 2, "a@b": 9, "../path": 9, "a" * 65: 9}
        )
        self.assertEqual(rows, [("valid", 3)])
        self.assertEqual(report["unsafe_terms"], 3)
        self.assertEqual(report["below_threshold_terms"], 1)
        self.assertEqual(report["all_incidence"], 32)

    def test_conversation_resolves_without_guessing(self):
        root = post(1)
        records = [
            root,
            post(2, in_reply_to_id="1", post_role="comment"),
            post(3, in_reply_to_id="2", author_id="b", post_role="comment"),
            post(4, in_reply_to_id="99", author_id=None, post_role="comment"),
            post(5, in_reply_to_id="6", post_role="comment"),
            post(6, in_reply_to_id="5", post_role="comment"),
        ]
        r = analysis.conversation(records, "1")
        self.assertEqual(r["retained_comments"], 5)
        self.assertEqual(r["resolved_comments"], 2)
        self.assertEqual(r["depths"], {1: 1, 2: 1})
        self.assertEqual(
            r["ancestry"], {"resolved": 2, "missing_parent": 1, "cycle": 2}
        )
        self.assertEqual(
            r["author_relation"], {"root_author": 3, "other_author": 1, "unknown": 1}
        )
        self.assertFalse(r["manual_sample_eligible"])

    def test_missing_id_is_not_silently_deduplicated(self):
        with self.assertRaises(ValueError):
            analysis.discourse([{"hashtags": []}])

    def test_missing_root_and_mismatched_conversation(self):
        r = analysis.conversation(
            [post(2, post_role="comment", in_reply_to_id="1", conversation_id="99")],
            "1",
        )
        self.assertEqual(r["ancestry"], {"root_mismatch": 1})
        self.assertEqual(r["author_relation"], {"unknown": 1})
        self.assertFalse(r["root_present"])

    def test_all_retained_sensitivity_includes_reposts(self):
        records = [
            post(1, hashtags=["Topic"]),
            post(2, post_role="repost", hashtags=["Topic"]),
        ]
        self.assertEqual(analysis.discourse(records)["casefold"]["topic"], 1)
        self.assertEqual(
            analysis.discourse(records, include_reposts=True)["casefold"]["topic"], 2
        )

    def test_malformed_entities_fail_before_counting_characters(self):
        with self.assertRaises(ValueError):
            analysis.discourse([post(1, hashtags="AI")])

    def test_known_parent_to_absent_root_is_not_resolved(self):
        result = analysis.conversation(
            [post(2, post_role="comment", in_reply_to_id="1")], "1"
        )
        self.assertEqual(result["ancestry"], {"missing_root": 1})
        self.assertEqual(result["resolved_comments"], 0)

    def test_source_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = Path(tmp)
            (scope / ".pyxcom").mkdir()
            source = scope / ".pyxcom/posts.jsonl"
            source.write_text(json.dumps(post(1)) + "\n")
            manifest = {
                "source_sha256": {".pyxcom/posts.jsonl": analysis.digest(source)}
            }
            (scope / "manifest.json").write_text(json.dumps(manifest))
            rows, _, _ = analysis.read_scope(scope)
            self.assertEqual(len(rows), 1)
            source.write_text(json.dumps(post(2)) + "\n")
            with self.assertRaises(ValueError):
                analysis.read_scope(scope)

    def test_end_to_end_private_fixture_produces_only_safe_aggregates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                ".codex-research/contracts/first-open-edition.json": {
                    "state_revision": 0
                },
                ".codex-research/state.yaml": {"revision": 0},
                "release/config/sampling.json": {},
                "literature/methods.json": {},
                "private/selected_roots.json": [{"post_id": "99999999999999"}],
            }
            for name, value in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            fixtures = {
                "discourse_ai_fixture": [
                    post(str(888880 + i), hashtags=["AI", "Robotics", "Policy"])
                    for i in range(3)
                ],
                "conversation_99999999999999": [post("99999999999999")]
                + [
                    post(
                        str(888890 + i),
                        post_role="comment",
                        in_reply_to_id="99999999999999",
                    )
                    for i in range(3)
                ],
            }
            for name, rows in fixtures.items():
                scope = root / "private/collections" / name
                (scope / ".pyxcom").mkdir(parents=True)
                path = scope / ".pyxcom/posts.jsonl"
                path.write_text("".join(json.dumps(row) + "\n" for row in rows))
                (scope / "manifest.json").write_text(
                    json.dumps(
                        {
                            "source_sha256": {
                                ".pyxcom/posts.jsonl": analysis.digest(path)
                            }
                        }
                    )
                )
            analysis.run(root)
            manifest = json.loads(
                (
                    root
                    / "release/replications/hara_et_al_2025/replication_manifest.json"
                ).read_text()
            )
            self.assertEqual(manifest["counts"]["manual_sample_eligible"], 1)
            self.assertEqual(manifest["counts"]["resolved_comments"], 3)
            template = (
                root
                / "release/replications/hara_et_al_2025/role_annotation_template.csv"
            )
            self.assertEqual(len(template.read_text().splitlines()), 1)
            for path in (root / "release").rglob("*"):
                if path.is_file():
                    text = path.read_text()
                    self.assertNotIn("99999999999999", text)
                    self.assertNotIn(str(root), text)

    def test_context_ancestor_resolves_without_entering_denominator(self):
        records = [
            post(1),
            post(
                2, post_role="comment", in_reply_to_id="1", observation_role="context"
            ),
            post(3, post_role="comment", in_reply_to_id="2"),
        ]
        result = analysis.conversation(records, "1")
        self.assertEqual(result["retained_comments"], 1)
        self.assertEqual(result["resolved_comments"], 1)
        self.assertEqual(result["depths"], {2: 1})
        self.assertEqual(result["excluded_context_observations"], 1)

    def test_jsonl_preserves_unicode_line_separators_inside_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = Path(tmp)
            (scope / ".pyxcom").mkdir()
            source = scope / ".pyxcom/posts.jsonl"
            text = "before\u2028middle\u0085after\u2029end"
            first = post(1, text=text)
            second = post(2, text="next record")
            source.write_text(
                json.dumps(first, ensure_ascii=False)
                + "\n\n"
                + json.dumps(second, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            (scope / "manifest.json").write_text(
                json.dumps(
                    {"source_sha256": {".pyxcom/posts.jsonl": analysis.digest(source)}}
                )
            )
            rows, _, _ = analysis.read_scope(scope)
            self.assertEqual([row["id"] for row in rows], ["1", "2"])
            self.assertEqual(rows[0]["text"], text)

    def test_portable_clone_cli_needs_no_private_governance(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "clone"
            (repo / "scripts").mkdir(parents=True)
            (repo / "config").mkdir()
            (repo / "references").mkdir()
            script = repo / "scripts/analyze.py"
            script.write_bytes(Path(analysis.__file__).read_bytes())
            (repo / "config/sampling.json").write_text("{}")
            (repo / "references/methods.json").write_text(
                '{"status":"original_protocol_archive"}'
            )
            collections = base / "local-private/collections"
            scope = collections / "discourse_fixture"
            (scope / ".pyxcom").mkdir(parents=True)
            source = scope / ".pyxcom/posts.jsonl"
            source.write_text(
                "".join(json.dumps(post(str(i))) + "\n" for i in range(3))
            )
            (scope / "manifest.json").write_text(
                json.dumps(
                    {"source_sha256": {".pyxcom/posts.jsonl": analysis.digest(source)}}
                )
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--release-root",
                    str(repo),
                    "--collections",
                    str(collections),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            manifest = json.loads(
                (
                    repo / "replications/kaiser_green_2026/replication_manifest.json"
                ).read_text()
            )
            self.assertEqual(manifest["execution_mode"], "portable")
            self.assertIsNone(manifest["state_revision"])
            self.assertEqual(manifest["denominators"]["unique_analysis_posts"], 3)
            self.assertFalse((repo / ".codex-research").exists())
            self.assertFalse((repo / "literature").exists())
            for folder in ("aggregate", "replications"):
                for path in (repo / folder).rglob("*"):
                    if path.is_file():
                        self.assertNotIn(str(base), path.read_text())


if __name__ == "__main__":
    unittest.main()
