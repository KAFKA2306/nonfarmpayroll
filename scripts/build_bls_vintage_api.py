#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

EXPECTED_SERIES_ID = "CES0000000001"
EXPECTED_UNIT = "thousand_persons"
EXPECTED_SEASONAL_ADJUSTMENT = "seasonally_adjusted"
VALID_STAGES = {"release1", "release2", "release3"}


def _dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_month(value: str) -> tuple[int, int]:
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise ValueError(f"invalid observation_month: {value}") from exc
    return parsed.year, parsed.month


def _parse_release_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid release_date: {value}") from exc


def _validate_snapshot(snapshot: dict) -> None:
    if snapshot.get("series_id") != EXPECTED_SERIES_ID:
        raise ValueError("unexpected series_id")
    if snapshot.get("unit") != EXPECTED_UNIT:
        raise ValueError("unexpected unit")
    if snapshot.get("seasonal_adjustment") != EXPECTED_SEASONAL_ADJUSTMENT:
        raise ValueError("unexpected seasonal_adjustment")
    if snapshot.get("publisher") != "U.S. Bureau of Labor Statistics":
        raise ValueError("unexpected publisher")
    try:
        datetime.fromisoformat(snapshot["retrieved_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid retrieved_at") from exc

    records = snapshot.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a non-empty list")

    seen = set()
    by_month: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        required = {
            "observation_month",
            "release_date",
            "revision_stage",
            "value_thousands",
            "source_document_id",
            "source_url",
        }
        missing = sorted(required - row.keys())
        if missing:
            raise ValueError(f"missing record fields: {', '.join(missing)}")
        if row["revision_stage"] not in VALID_STAGES:
            raise ValueError("unsupported revision_stage")
        if isinstance(row["value_thousands"], bool) or not isinstance(row["value_thousands"], (int, float)):
            raise ValueError("value_thousands must be numeric")
        if not isinstance(row["source_document_id"], str) or not row["source_document_id"].strip():
            raise ValueError("missing source_document_id")

        parsed_url = urlparse(row["source_url"])
        if parsed_url.scheme != "https" or parsed_url.hostname not in {"www.bls.gov", "bls.gov"}:
            raise ValueError("source_url must be an HTTPS BLS URL")

        year, month = _parse_month(row["observation_month"])
        released = _parse_release_date(row["release_date"])
        if (released.year, released.month) <= (year, month):
            raise ValueError("release_date must be after observation_month")

        key = (row["observation_month"], row["revision_stage"])
        if key in seen:
            raise ValueError("duplicate observation_month/revision_stage")
        seen.add(key)
        by_month[row["observation_month"]].append(row)

    for observation_month, rows in by_month.items():
        rows.sort(key=lambda row: int(row["revision_stage"][-1]))
        stages = [int(row["revision_stage"][-1]) for row in rows]
        if stages != list(range(1, len(stages) + 1)):
            raise ValueError(f"non-contiguous revision stages for {observation_month}")
        release_dates = [_parse_release_date(row["release_date"]) for row in rows]
        if release_dates != sorted(release_dates) or len(release_dates) != len(set(release_dates)):
            raise ValueError(f"release dates must increase by revision stage for {observation_month}")


def build(snapshot_path: Path, output_dir: Path) -> dict:
    snapshot_text = snapshot_path.read_text(encoding="utf-8")
    snapshot_sha256 = hashlib.sha256(snapshot_text.encode("utf-8")).hexdigest()
    snapshot = json.loads(snapshot_text)
    _validate_snapshot(snapshot)

    records = sorted(
        snapshot["records"],
        key=lambda row: (row["observation_month"], int(row["revision_stage"][-1])),
    )
    normalized_records = [
        {
            **row,
            "series_id": snapshot["series_id"],
            "unit": snapshot["unit"],
            "seasonal_adjustment": snapshot["seasonal_adjustment"],
            "retrieved_at": snapshot["retrieved_at"],
            "source_snapshot_sha256": snapshot_sha256,
        }
        for row in records
    ]

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in normalized_records:
        grouped[row["observation_month"]].append(row)

    revisions = []
    for month in sorted(grouped):
        rows = grouped[month]
        for previous, current in zip(rows, rows[1:]):
            revisions.append(
                {
                    "observation_month": month,
                    "from_stage": previous["revision_stage"],
                    "to_stage": current["revision_stage"],
                    "from_value_thousands": previous["value_thousands"],
                    "to_value_thousands": current["value_thousands"],
                    "revision_thousands": current["value_thousands"] - previous["value_thousands"],
                    "release_date": current["release_date"],
                    "source_document_id": current["source_document_id"],
                    "source_url": current["source_url"],
                    "source_snapshot_sha256": snapshot_sha256,
                }
            )

    vintages = {
        "schema_version": "1.1",
        "analysis_available": False,
        "coverage_status": "partial_verified_vintages",
        "integrity_status": "SOURCE_DOCUMENT_CHECKSUMS_NOT_ARCHIVED",
        "record_count": len(normalized_records),
        "records": normalized_records,
    }
    revision_payload = {
        "schema_version": "1.1",
        "analysis_available": False,
        "revision_record_count": len(revisions),
        "records": revisions,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {
        "payroll-vintages.json": _dump_json(vintages),
        "payroll-revisions.json": _dump_json(revision_payload),
    }
    fieldnames = list(revisions[0]) if revisions else [
        "observation_month",
        "from_stage",
        "to_stage",
        "from_value_thousands",
        "to_value_thousands",
        "revision_thousands",
        "release_date",
        "source_document_id",
        "source_url",
        "source_snapshot_sha256",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(revisions)
    files["payroll-revisions.csv"] = buffer.getvalue()

    for name, text in files.items():
        (output_dir / name).write_text(text, encoding="utf-8", newline="")

    stage_counts = {
        stage: sum(row["revision_stage"] == stage for row in normalized_records)
        for stage in sorted(VALID_STAGES)
    }
    manifest = {
        "schema_version": "1.1",
        "dataset_id": snapshot["dataset_id"],
        "series_id": snapshot["series_id"],
        "unit": snapshot["unit"],
        "seasonal_adjustment": snapshot["seasonal_adjustment"],
        "retrieved_at": snapshot["retrieved_at"],
        "analysis_available": False,
        "coverage_status": "partial_verified_vintages",
        "integrity_status": "SOURCE_DOCUMENT_CHECKSUMS_NOT_ARCHIVED",
        "vintage_record_count": len(normalized_records),
        "revision_record_count": len(revisions),
        "revision_stage_counts": stage_counts,
        "first_observation": snapshot["coverage"]["first_observation"],
        "last_observation": snapshot["coverage"]["last_observation"],
        "source_snapshot_sha256": snapshot_sha256,
        "source_urls": sorted({r["source_url"] for r in normalized_records}),
        "source_document_ids": sorted({r["source_document_id"] for r in normalized_records}),
        "license": snapshot["license"],
        "files": {
            name: {"bytes": len(text.encode("utf-8")), "sha256": _sha256(text)}
            for name, text in files.items()
        },
    }
    (output_dir / "vintage-manifest.json").write_text(
        _dump_json(manifest), encoding="utf-8", newline=""
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path("data_verified/vintages/bls-payroll-change-2026-08-07.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("docs/api/v1"))
    args = parser.parse_args()
    manifest = build(args.snapshot, args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
