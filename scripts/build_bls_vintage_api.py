#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def _dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build(snapshot_path: Path, output_dir: Path) -> dict:
    snapshot_text = snapshot_path.read_text(encoding="utf-8")
    snapshot = json.loads(snapshot_text)
    records = sorted(
        snapshot["records"],
        key=lambda row: (row["observation_month"], int(row["revision_stage"][-1])),
    )

    keys = [(r["observation_month"], r["revision_stage"]) for r in records]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate observation_month/revision_stage")

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        if row["revision_stage"] not in {"release1", "release2", "release3"}:
            raise ValueError("unsupported revision_stage")
        grouped[row["observation_month"]].append(row)

    revisions = []
    for month in sorted(grouped):
        rows = grouped[month]
        stages = [int(r["revision_stage"][-1]) for r in rows]
        if stages != list(range(1, len(stages) + 1)):
            raise ValueError(f"non-contiguous revision stages for {month}")
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
                }
            )

    vintages = {
        "schema_version": "1.0",
        "analysis_available": False,
        "coverage_status": "partial_verified_vintages",
        "record_count": len(records),
        "records": records,
    }
    revision_payload = {
        "schema_version": "1.0",
        "analysis_available": False,
        "revision_record_count": len(revisions),
        "records": revisions,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {
        "payroll-vintages.json": _dump_json(vintages),
        "payroll-revisions.json": _dump_json(revision_payload),
    }
    csv_path = output_dir / "payroll-revisions.csv"
    fieldnames = list(revisions[0]) if revisions else [
        "observation_month", "from_stage", "to_stage", "from_value_thousands",
        "to_value_thousands", "revision_thousands", "release_date", "source_document_id",
    ]
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(revisions)
    files["payroll-revisions.csv"] = buffer.getvalue()

    for name, text in files.items():
        (output_dir / name).write_text(text, encoding="utf-8", newline="")

    manifest = {
        "schema_version": "1.0",
        "dataset_id": snapshot["dataset_id"],
        "analysis_available": False,
        "coverage_status": "partial_verified_vintages",
        "vintage_record_count": len(records),
        "revision_record_count": len(revisions),
        "first_observation": snapshot["coverage"]["first_observation"],
        "last_observation": snapshot["coverage"]["last_observation"],
        "source_snapshot_sha256": hashlib.sha256(snapshot_text.encode("utf-8")).hexdigest(),
        "source_urls": sorted({r["source_url"] for r in records}),
        "license": snapshot["license"],
        "files": {
            name: {"bytes": len(text.encode("utf-8")), "sha256": _sha256(text)}
            for name, text in files.items()
        },
    }
    (output_dir / "vintage-manifest.json").write_text(_dump_json(manifest), encoding="utf-8", newline="")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=Path("data_verified/vintages/bls-payroll-change-2026-08-07.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/api/v1"))
    args = parser.parse_args()
    manifest = build(args.snapshot, args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
