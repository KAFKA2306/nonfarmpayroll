from __future__ import annotations
import hashlib, json
from datetime import date

SERIES_ID = "CES0000000001"
DATA_FILE = "total-nonfarm.json"

class ExplorerContractError(ValueError):
    pass

def _d(value: str) -> date:
    try: return date.fromisoformat(value)
    except ValueError as exc: raise ExplorerContractError(f"invalid ISO date: {value}") from exc

def explore(manifest_bytes: bytes, data_bytes: bytes, start: str, end: str, mode: str = "level") -> str:
    manifest = json.loads(manifest_bytes)
    meta = manifest.get("files", {}).get(DATA_FILE)
    if not isinstance(meta, dict): raise ExplorerContractError("manifest does not authorize data")
    if meta.get("bytes") != len(data_bytes): raise ExplorerContractError("byte count mismatch")
    if meta.get("sha256") != hashlib.sha256(data_bytes).hexdigest(): raise ExplorerContractError("SHA-256 mismatch")
    payload = json.loads(data_bytes)
    if manifest.get("analysis_available") is not False or manifest.get("level_series_available") is not True: raise ExplorerContractError("level series unavailable")
    if manifest.get("series_id") != SERIES_ID or payload.get("series", {}).get("series_id") != SERIES_ID: raise ExplorerContractError("unexpected series")
    rows = payload.get("records")
    if not isinstance(rows, list) or not rows or len(rows) != manifest.get("record_count"): raise ExplorerContractError("record count mismatch")
    dates = [r.get("observation_date") for r in rows]
    if dates != sorted(dates) or len(dates) != len(set(dates)): raise ExplorerContractError("dates not unique/sorted")
    if dates[0] != manifest.get("first_observation") or dates[-1] != manifest.get("last_observation"): raise ExplorerContractError("coverage mismatch")
    if _d(start) > _d(end): raise ExplorerContractError("invalid range")
    if _d(start) < _d(dates[0]) or _d(end) > _d(dates[-1]): raise ExplorerContractError("range exceeds verified coverage")
    by_date = {r["observation_date"]: r for r in rows}
    out = []
    for i, row in enumerate(rows):
        value = row.get("value_thousands")
        if not isinstance(value, (int, float)): raise ExplorerContractError("non-numeric value")
        if mode == "level": transformed = value
        elif mode == "mom": transformed = None if i == 0 else value - rows[i-1]["value_thousands"]
        elif mode == "yoy":
            cur = _d(row["observation_date"]); prior = by_date.get(cur.replace(year=cur.year-1).isoformat())
            transformed = None if prior is None else value - prior["value_thousands"]
        else: raise ExplorerContractError("unsupported transform")
        if start <= row["observation_date"] <= end:
            out.append({"observation_date":row["observation_date"],"value_thousands":value,"transformed_value":transformed,"preliminary":bool(row.get("preliminary",False))})
    if not out: raise ExplorerContractError("no verified observations")
    return json.dumps({"analysis_available":False,"revision_statistics_generated":False,"series":payload["series"],"source":payload["source"],"coverage_scope":manifest["coverage_scope"],"verified_artifact_sha256":meta["sha256"],"mode":mode,"records":out}, ensure_ascii=False, separators=(",",":"))
