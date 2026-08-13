import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("level_explorer", ROOT / "docs/explorer/level_explorer.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class BrowserLevelExplorerTests(unittest.TestCase):
    def setUp(self):
        self.manifest = (ROOT / "docs/api/v1/manifest.json").read_bytes()
        self.data = (ROOT / "docs/api/v1/total-nonfarm.json").read_bytes()

    def run_mode(self, mode):
        return json.loads(MODULE.explore(self.manifest, self.data, "2025-01-01", "2026-07-01", mode))

    def test_verified_modes_do_not_enable_revision_analysis(self):
        for mode in ("level", "mom", "yoy"):
            result = self.run_mode(mode)
            self.assertFalse(result["analysis_available"])
            self.assertFalse(result["revision_statistics_generated"])
            self.assertEqual(result["series"]["series_id"], "CES0000000001")
            self.assertTrue(result["records"])

    def test_checksum_mismatch_fails_closed(self):
        corrupted = bytearray(self.data)
        corrupted[-2] ^= 1
        with self.assertRaisesRegex(MODULE.ExplorerContractError, "SHA-256"):
            MODULE.explore(self.manifest, bytes(corrupted), "2025-01-01", "2026-07-01", "level")

    def test_outside_verified_coverage_fails_closed(self):
        with self.assertRaisesRegex(MODULE.ExplorerContractError, "coverage"):
            MODULE.explore(self.manifest, self.data, "2020-01-01", "2026-07-01", "level")


if __name__ == "__main__":
    unittest.main()
