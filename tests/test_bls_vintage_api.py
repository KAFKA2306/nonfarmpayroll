import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_bls_vintage_api import build


class BlsVintageApiTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = Path("data_verified/vintages/bls-payroll-change-2026-08-07.json")

    def test_verified_release_chain_and_revisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            manifest = build(self.snapshot, out)
            vintages = json.loads((out / "payroll-vintages.json").read_text())
            revisions = json.loads((out / "payroll-revisions.json").read_text())

            self.assertFalse(manifest["analysis_available"])
            self.assertEqual(manifest["vintage_record_count"], 6)
            self.assertEqual(manifest["revision_record_count"], 3)
            self.assertEqual(vintages["record_count"], 6)
            self.assertEqual(
                [r["revision_thousands"] for r in revisions["records"]],
                [-43, -66, -37],
            )

    def test_may_has_three_releases_and_july_is_initial_only(self):
        payload = json.loads(self.snapshot.read_text())
        by_month = {}
        for row in payload["records"]:
            by_month.setdefault(row["observation_month"], []).append(row)
        self.assertEqual([r["revision_stage"] for r in by_month["2026-05"]], ["release1", "release2", "release3"])
        self.assertEqual(by_month["2026-07"][0]["value_thousands"], -23)


if __name__ == "__main__":
    unittest.main()
