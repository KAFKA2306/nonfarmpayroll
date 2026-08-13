from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

SERIES_ID = "CES0000000001"
DATA_FILE = "total-nonfarm.json"


class ExplorerContractError(ValueError):
    pass


def _parse_iso(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ExplorerContractError(f"invalid ISO date: {value}") from exc


def _validate_bytes(manifest: dict[str, Any], data_bytes: bytes) -> None:
    file_meta = manifest.get("files", {}).get(DATA_FILE)
    if not isinstance(file_meta, dict):
        raise ExplorerContractError(f"manifest does not authorize {DATA_FILE}")
    if file_meta.get("bytes") != len(data_bytes):
        raise ExplorerContractError("verified artifact byte count mismatch")
    actual = hashlib.sha256(data_bytes).hexdigest()
    if file_meta.get("sha256") != actual:
        raise ExplorerContractError("verified artifact SHA-256 mismatch")


def _validate_contract(manifest: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("analysis_available") is not False:
        raise ExplorerContractError("explorer requires analysis_available=false")
    if manifest.get("level_series_available") is not True:
        raise ExplorerContractError("verified level series is unavailable")
    if manifest.get("series_id") != SERIES_ID:
        raise ExplorerContractError("unexpected manifest series_id")
    series = payload.get("series") or {}
    if series.get("series_id") != SERIES_ID:
        raise ExplorerContractError("unexpected payload series_id")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != manifest.get("record_count"):
        raise ExplorerContractError("record_count mismatch")
    if not records:
        raise ExplorerContractError("verified level series is empty")
    dates = [row.get("observation_date") for row in records]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise ExplorerContractError("observation dates must be unique and sorted")
    if dates[0] != manifest.get("first_observation") or dates[-1] != manifest.get("last_observation"):
        raise ExplorerContractError("coverage mismatch")
    return records


def _transform(records: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    by_date = {row["observation_date"]: row for row in records}
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(records):
        value = row.get("value_thousands")
        if not isinstance(value, (int, float)):
            raise ExplorerContractError("non-numeric verified value")
        if mode == "level":
            transformed: float | int | None = value
        elif mode == "mom":
            transformed = None if idx == 0 else value - records[idx - 1]["value_thousands"]
        elif mode == "yoy":
            current = _parse_iso(row["observation_date"])
            prior_key = current.replace(year=current.year - 1).isoformat()
            prior = by_date.get(prior_key)
            transformed = None if prior is None else value - prior["value_thousands"]
        else:
            raise ExplorerContractError(f"unsupported transform: {mode}")
        out.append({
            "observation_date": row["observation_date"],
            "value_thousands": value,
            "transformed_value": transformed,
            "preliminary": bool(row.get("preliminary", False)),
        })
    return out


def explore(manifest_bytes: bytes, data_bytes: bytes, start: str, end: str, mode: str = "level") -> str:
    manifest = json.loads(manifest_bytes)
    _validate_bytes(manifest, data_bytes)
    payload = json.loads(data_bytes)
    records = _validate_contract(manifest, payload)
    start_date = _parse_iso(start)
    end_date = _parse_iso(end)
    if start_date > end_date:
        raise ExplorerContractError("start must be on or before end")
    coverage_start = _parse_iso(manifest["first_observation"])
    coverage_end = _parse_iso(manifest["last_observation"])
    if start_date < coverage_start or end_date > coverage_end:
        raise ExplorerContractError("requested range exceeds verified coverage")
    transformed = _transform(records, mode)
    selected = [row for row in transformed if start <= row["observation_date"] <= end]
    if not selected:
        raise ExplorerContractError("requested range contains no verified observations")
    result = {
        "analysis_available": False,
        "revision_statistics_generated": False,
        "series": payload["series"],
        "source": payload["source"],
        "coverage_scope": manifest["coverage_scope"],
        "verified_artifact_sha256": manifest["files"][DATA_FILE]["sha256"],
        "mode": mode,
        "start": start,
        "end": end,
        "records": selected,
    }
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
