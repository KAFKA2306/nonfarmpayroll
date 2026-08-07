#!/usr/bin/env python3
"""Build a fail-closed API dataset from the official BLS CES flat file.

This intentionally publishes only the latest available level series for
CES0000000001 (Total nonfarm employment). It must never be used as a
release-vintage/revision-stage dataset.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://download.bls.gov/pub/time.series/ce/ce.data.00a.TotalNonfarm.Employment"
SERIES_ID = "CES0000000001"


def fetch_source(url: str = SOURCE_URL, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "KAFKA2306/nonfarmpayroll BLS data updater"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"BLS download failed with HTTP {response.status}")
        return response.read()


def parse_series(raw: bytes) -> list[dict[str, object]]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in reader:
        normalized = {str(k).strip(): (v.strip() if v else "") for k, v in row.items()}
        if normalized.get("series_id") != SERIES_ID:
            continue
        period = normalized.get("period", "")
        if not period.startswith("M") or period == "M13":
            continue
        try:
            month = int(period[1:])
            year = int(normalized["year"])
            value = int(normalized["value"])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"invalid BLS row for {SERIES_ID}: {normalized}") from exc
        if not 1 <= month <= 12:
            raise ValueError(f"invalid month {period}")
        observation_date = f"{year:04d}-{month:02d}-01"
        if observation_date in seen:
            raise ValueError(f"duplicate observation_date: {observation_date}")
        seen.add(observation_date)
        records.append(
            {
                "series_id": SERIES_ID,
                "observation_date": observation_date,
                "value_thousands": value,
                "preliminary": "P" in normalized.get("footnote_codes", ""),
            }
        )
    records.sort(key=lambda item: str(item["observation_date"]))
    if not records:
        raise ValueError(f"series {SERIES_ID} not found")
    return records


def build_payload(raw: bytes, retrieved_at_utc: str) -> dict[str, object]:
    records = parse_series(raw)
    return {
        "schema_version": 1,
        "series": {
            "series_id": SERIES_ID,
            "title": "Total nonfarm employment",
            "survey": "Current Employment Statistics",
            "unit": "thousands of persons",
            "seasonal_adjustment": "seasonally adjusted",
        },
        "source": {
            "publisher": "U.S. Bureau of Labor Statistics",
            "url": SOURCE_URL,
            "retrieved_at_utc": retrieved_at_utc,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "license": "U.S. federal government public domain; cite BLS as source",
        },
        "record_count": len(records),
        "first_observation": records[0]["observation_date"],
        "last_observation": records[-1]["observation_date"],
        "records": records,
        "warning": (
            "This is the latest available level series at retrieval time, not a release-vintage "
            "history and not valid for revision-stage analysis."
        ),
    }


def write_outputs(payload: dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_bytes = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
    json_path = output_dir / "total-nonfarm.json"
    json_path.write_bytes(json_bytes)

    records = payload["records"]
    assert isinstance(records, list)
    csv_path = output_dir / "total-nonfarm.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["series_id", "observation_date", "value_thousands", "preliminary"],
        )
        writer.writeheader()
        writer.writerows(records)

    manifest = {
        "schema_version": 1,
        "analysis_available": False,
        "revision_vintage_available": False,
        "level_series_available": True,
        "series_id": SERIES_ID,
        "record_count": payload["record_count"],
        "first_observation": payload["first_observation"],
        "last_observation": payload["last_observation"],
        "retrieved_at_utc": payload["source"]["retrieved_at_utc"],
        "source_sha256": payload["source"]["source_sha256"],
        "files": {
            "total-nonfarm.json": {
                "bytes": len(json_bytes),
                "sha256": hashlib.sha256(json_bytes).hexdigest(),
            },
            "total-nonfarm.csv": {
                "bytes": csv_path.stat().st_size,
                "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            },
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="Use a local BLS flat file instead of downloading")
    parser.add_argument("--output-dir", type=Path, default=Path("docs/api/v1"))
    parser.add_argument("--retrieved-at", help="UTC ISO-8601 retrieval timestamp")
    args = parser.parse_args()

    raw = args.input.read_bytes() if args.input else fetch_source()
    retrieved_at = args.retrieved_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = build_payload(raw, retrieved_at)
    write_outputs(payload, args.output_dir)
    print(
        f"published {payload['record_count']} observations: "
        f"{payload['first_observation']}..{payload['last_observation']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
