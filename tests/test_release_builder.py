import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_datasets import check_local_destination, local_personal_csv


class ReleaseBuilderTests(unittest.TestCase):
    def test_reject_raw_and_public_paths_and_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw"
            public = root / "release"
            source.mkdir()
            (source / "posts.jsonl").write_text("preserve")
            for path in (
                source / "posts.jsonl",
                source / "new.csv",
                public / "leak.csv",
            ):
                with self.assertRaises((ValueError, FileExistsError)):
                    check_local_destination(path, (source,), public)
            self.assertEqual((source / "posts.jsonl").read_text(), "preserve")
            self.assertEqual(
                check_local_destination(root / "local.csv", (source,), public),
                (root / "local.csv").resolve(),
            )

    def test_unicode_jsonl_text_survives_local_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "collections"
            scope = private / "personal_meta_muse_2026-09-01" / ".pyxcom"
            scope.mkdir(parents=True)
            text = "a\u2028b\u0085c"
            (scope / "posts.jsonl").write_text(
                json.dumps({"id": "12345", "text": text}, ensure_ascii=False) + "\n"
            )
            dest = root / "out.csv"
            self.assertEqual(local_personal_csv(private, dest), 1)
            with dest.open(encoding="utf-8-sig", newline="") as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row["text"], text)
            self.assertEqual(row["products"], "meta_muse")
            with self.assertRaises(FileExistsError):
                local_personal_csv(private, dest)
