import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_bls_vintage_api import build


class BlsVintageApiTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = Path("data_verified/vintages/bls-payroll-change-2026-08-07.json")
        self.payload = json.loads(self.snapshot.read_text())

    def _build_payload(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "snapshot.json"
            snapshot.write_text(json.dumps(payload), encoding="utf-8")
            out = root / "out"
            manifest = build(snapshot, out)
            return manifest, json.loads((out / "payroll-vintages.json").read_text())

    def _assert_rejected(self, mutate):
        payload = copy.deepcopy(self.payload)
        mutate(payload)
        with self.assertRaises(ValueError):
            self._build_payload(payload)

    def test_verified_release_chain_and_revisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            manifest = build(self.snapshot, out)
            vintages = json.loads((out / "payroll-vintages.json").read_text())
            revisions = json.loads((out / "payroll-revisions.json").read_text())

            self.assertFalse(manifest["analysis_available"])
            self.assertEqual(manifest["vintage_record_count"], 18)
            self.assertEqual(manifest["revision_record_count"], 11)
            self.assertEqual(manifest["revision_stage_counts"], {
                "release1": 7, "release2": 6, "release3": 5
            })
            self.assertEqual(manifest["integrity_status"], "SOURCE_DOCUMENT_CHECKSUMS_NOT_ARCHIVED")
            self.assertEqual(manifest["first_observation"], "2026-01")
            self.assertEqual(vintages["record_count"], 18)
            self.assertEqual(
                [r["revision_thousands"] for r in revisions["records"]],
                [-4, 34, -41, -23, 7, 29, 64, -31, -43, -66, -37],
            )
            first = vintages["records"][0]
            self.assertEqual(first["series_id"], "CES0000000001")
            self.assertEqual(first["unit"], "thousand_persons")
            self.assertEqual(first["seasonal_adjustment"], "seasonally_adjusted")
            self.assertEqual(first["retrieved_at"], self.payload["retrieved_at"])
            self.assertEqual(len(first["source_snapshot_sha256"]), 64)

    def test_january_through_april_have_complete_three_release_chains(self):
        by_month = {}
        for row in self.payload["records"]:
            by_month.setdefault(row["observation_month"], []).append(row)
        expected = {
            "2026-01": [130, 126, 160],
            "2026-02": [-92, -133, -156],
            "2026-03": [178, 185, 214],
            "2026-04": [115, 179, 148],
        }
        for month, values in expected.items():
            self.assertEqual(
                [r["revision_stage"] for r in by_month[month]],
                ["release1", "release2", "release3"],
            )
            self.assertEqual(
                [r["value_thousands"] for r in by_month[month]],
                values,
            )
        self.assertEqual(by_month["2026-07"][0]["value_thousands"], -23)

    def test_duplicate_stage_is_rejected(self):
        def mutate(payload):
            payload["records"].append(copy.deepcopy(payload["records"][0]))
        self._assert_rejected(mutate)

    def test_unit_mismatch_is_rejected(self):
        self._assert_rejected(lambda payload: payload.__setitem__("unit", "persons"))

    def test_observation_release_date_inversion_is_rejected(self):
        def mutate(payload):
            payload["records"][0]["release_date"] = "2026-01-01"
        self._assert_rejected(mutate)

    def test_revision_release_dates_must_increase(self):
        def mutate(payload):
            payload["records"][1]["release_date"] = payload["records"][0]["release_date"]
        self._assert_rejected(mutate)

    def test_non_bls_source_is_rejected(self):
        def mutate(payload):
            payload["records"][0]["source_url"] = "https://example.com/release"
        self._assert_rejected(mutate)


if __name__ == "__main__":
    unittest.main()
