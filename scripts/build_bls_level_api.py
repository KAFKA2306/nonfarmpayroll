#!/usr/bin/env python3
"""Build a fail-closed API for BLS CES Total nonfarm employment.

Live BLS downloads are used only by an explicit refresh operation. Normal CI and
Pages builds use a committed, checksum-audited normalized snapshot so that
external blocking cannot silently change or break published data.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://download.bls.gov/pub/time.series/ce/ce.data.00a.TotalNonfarm.Employment"
SERIES_ID = "CES0000000001"
FIELDS = ["series_id", "observation_date", "value_thousands", "preliminary"]


def fetch_source(url: str = SOURCE_URL, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "KAFKA2306/nonfarmpayroll BLS data updater"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"BLS download failed with HTTP {response.status}")
        return response.read()


def _validate(records: list[dict[str, object]]) -> list[dict[str, object]]:
    if not records:
        raise ValueError("no records")
    seen: set[str] = set()
    for row in records:
        if row["series_id"] != SERIES_ID:
            raise ValueError(f"unexpected series_id: {row['series_id']}")
        date = str(row["observation_date"])
        if date in seen:
            raise ValueError(f"duplicate observation_date: {date}")
        seen.add(date)
        if not isinstance(row["value_thousands"], int):
            raise ValueError(f"non-integer value: {date}")
        if not isinstance(row["preliminary"], bool):
            raise ValueError(f"invalid preliminary flag: {date}")
    records.sort(key=lambda item: str(item["observation_date"]))
    return records


def parse_series(raw: bytes) -> list[dict[str, object]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter="\t")
    records: list[dict[str, object]] = []
    for row in reader:
        normalized = {str(k).strip(): (v.strip() if v else "") for k, v in row.items()}
        if normalized.get("series_id") != SERIES_ID:
            continue
        period = normalized.get("period", "")
        if not period.startswith("M") or period == "M13":
            continue
        month = int(period[1:])
        year = int(normalized["year"])
        if not 1 <= month <= 12:
            raise ValueError(f"invalid month {period}")
        records.append({
            "series_id": SERIES_ID,
            "observation_date": f"{year:04d}-{month:02d}-01",
            "value_thousands": int(normalized["value"]),
            "preliminary": "P" in normalized.get("footnote_codes", ""),
        })
    return _validate(records)


def load_normalized_gzip(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    records = [{
        "series_id": row["series_id"],
        "observation_date": row["observation_date"],
        "value_thousands": int(row["value_thousands"]),
        "preliminary": row["preliminary"].strip().lower() == "true",
    } for row in rows]
    return _validate(records)


def build_payload(records: list[dict[str, object]], source_meta: dict[str, object]) -> dict[str, object]:
    records = _validate(records)
    return {
        "schema_version": 1,
        "series": {"series_id": SERIES_ID, "title": "Total nonfarm employment", "survey": "Current Employment Statistics", "unit": "thousands of persons", "seasonal_adjustment": "seasonally adjusted"},
        "source": source_meta,
        "record_count": len(records),
        "first_observation": records[0]["observation_date"],
        "last_observation": records[-1]["observation_date"],
        "records": records,
        "warning": "Latest available level series at retrieval time; not release-vintage history and not valid for revision-stage analysis.",
    }


def write_outputs(payload: dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_bytes = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
    (output_dir / "total-nonfarm.json").write_bytes(json_bytes)
    csv_path = output_dir / "total-nonfarm.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(payload["records"])
    manifest = {
        "schema_version": 1, "analysis_available": False,
        "revision_vintage_available": False, "level_series_available": True,
        "series_id": SERIES_ID, "record_count": payload["record_count"],
        "first_observation": payload["first_observation"], "last_observation": payload["last_observation"],
        "retrieved_at_utc": payload["source"]["retrieved_at_utc"], "source_sha256": payload["source"]["source_sha256"],
        "files": {
            "total-nonfarm.json": {"bytes": len(json_bytes), "sha256": hashlib.sha256(json_bytes).hexdigest()},
            "total-nonfarm.csv": {"bytes": csv_path.stat().st_size, "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest()},
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized-gzip", type=Path, default=Path("data_verified/total_nonfarm.csv.gz"))
    parser.add_argument("--snapshot", type=Path, default=Path("data_verified/source_snapshots/2026-08-07-total-nonfarm.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/api/v1"))
    parser.add_argument("--refresh", action="store_true", help="Fetch BLS live instead of using committed snapshot")
    args = parser.parse_args()
    if args.refresh:
        raw = fetch_source()
        records = parse_series(raw)
        source_meta = {"publisher": "U.S. Bureau of Labor Statistics", "url": SOURCE_URL, "retrieved_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "source_sha256": hashlib.sha256(raw).hexdigest(), "license": "U.S. federal government public domain; cite BLS as source"}
    else:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        records = load_normalized_gzip(args.normalized_gzip)
        if len(records) != snapshot["record_count"] or records[-1]["observation_date"] != snapshot["last_observation"]:
            raise ValueError("normalized snapshot does not match audit metadata")
        source_meta = {"publisher": "U.S. Bureau of Labor Statistics", "url": snapshot["source_url"], "retrieved_at_utc": snapshot["retrieved_at_utc"], "source_sha256": snapshot["source_sha256"], "license": snapshot["license"]}
    payload = build_payload(records, source_meta)
    write_outputs(payload, args.output_dir)
    print(f"published {payload['record_count']} observations: {payload['first_observation']}..{payload['last_observation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
