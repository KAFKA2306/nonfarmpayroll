from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_bls_level_api import build_payload, parse_series, write_outputs


SAMPLE = b"series_id\tyear\tperiod\tvalue\tfootnote_codes\nCES0000000001\t2026\tM05\t158927\tP\nCES0000000001\t2026\tM06\t158984\tP\nCES0500000001\t2026\tM06\t136000\t\n"


class BLSLevelApiTests(unittest.TestCase):
    def test_parses_only_target_series(self) -> None:
        records = parse_series(SAMPLE)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[-1]["observation_date"], "2026-06-01")
        self.assertEqual(records[-1]["value_thousands"], 158984)
        self.assertTrue(records[-1]["preliminary"])

    def test_rejects_duplicate_observation_month(self) -> None:
        duplicate = SAMPLE + b"CES0000000001\t2026\tM06\t158985\tP\n"
        with self.assertRaisesRegex(ValueError, "duplicate observation_date"):
            parse_series(duplicate)

    def test_manifest_matches_generated_files(self) -> None:
        payload = build_payload(SAMPLE, "2026-08-07T07:17:36Z")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            write_outputs(payload, output)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertFalse(manifest["analysis_available"])
            self.assertFalse(manifest["revision_vintage_available"])
            self.assertTrue(manifest["level_series_available"])
            for name, meta in manifest["files"].items():
                data = (output / name).read_bytes()
                self.assertEqual(meta["bytes"], len(data))
                self.assertEqual(meta["sha256"], hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    unittest.main()
