from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "docs" / "api" / "v1"
EMBED = ROOT / "docs" / "embed" / "nfp"


class NfpMediaEmbedContractTests(unittest.TestCase):
    def test_level_snapshot_matches_fail_closed_manifest(self) -> None:
        manifest = json.loads((API / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["level_series_available"])
        self.assertFalse(manifest["analysis_available"])
        self.assertFalse(manifest["revision_vintage_available"])
        self.assertEqual(manifest["series_id"], "CES0000000001")
        for name, meta in manifest["files"].items():
            payload = (API / name).read_bytes()
            self.assertEqual(meta["bytes"], len(payload))
            self.assertEqual(meta["sha256"], hashlib.sha256(payload).hexdigest())

    def test_level_payload_is_current_verified_subset(self) -> None:
        data = json.loads((API / "total-nonfarm.json").read_text(encoding="utf-8"))
        self.assertEqual(data["series"]["series_id"], "CES0000000001")
        self.assertEqual(data["series"]["unit"], "thousands of persons")
        self.assertEqual(data["series"]["seasonal_adjustment"], "seasonally adjusted")
        self.assertEqual(data["record_count"], len(data["records"]))
        self.assertGreaterEqual(data["record_count"], 61)
        self.assertEqual(data["last_observation"], "2026-07-01")
        self.assertTrue(data["records"][-1]["preliminary"])
        self.assertEqual(data["source"]["publisher"], "U.S. Bureau of Labor Statistics")
        self.assertEqual(len(data["source"]["source_sha256"]), 64)

    def test_embed_uses_only_level_endpoint_and_required_boundaries(self) -> None:
        js = (EMBED / "embed.js").read_text(encoding="utf-8")
        html = (EMBED / "index.html").read_text(encoding="utf-8")
        self.assertIn("../../api/v1/manifest.json", js)
        self.assertIn("../../api/v1/total-nonfarm.json", js)
        self.assertNotIn("payroll-revisions", js)
        self.assertNotIn("payroll-vintages", js)
        self.assertIn("analysis_available !== false", js)
        self.assertIn("revision_vintage_available !== false", js)
        self.assertIn("CHECKSUM_MISMATCH", js)
        self.assertIn("CES0000000001", html)
        self.assertIn("preliminary", html)

    def test_partner_metrics_are_small_and_pii_free(self) -> None:
        js = (EMBED / "embed.js").read_text(encoding="utf-8")
        for metric in (
            "embed_loaded",
            "source_opened",
            "full_chart_opened",
            "business_inquiry_started",
        ):
            self.assertIn(metric, js)
        for forbidden in ("localStorage", "document.cookie", "email", "user_id", "ip_address"):
            self.assertNotIn(forbidden, js)
        self.assertIn("partner, metric", js)

    def test_external_iframe_fixture_points_to_embed(self) -> None:
        fixture = (ROOT / "tests" / "fixtures" / "nfp-media-embed-host.html").read_text(encoding="utf-8")
        self.assertIn("<iframe", fixture)
        self.assertIn("docs/embed/nfp/index.html?range=1y&locale=en&partner=fixture_host", fixture)
        self.assertIn("nfp_media_embed_metric", fixture)


if __name__ == "__main__":
    unittest.main()
