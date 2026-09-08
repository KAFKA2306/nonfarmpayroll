#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

BLS_HOSTS = {"www.bls.gov", "bls.gov"}
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _fetch(url: str) -> tuple[bytes, str]:
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=60) as response:
        final_url = response.geturl()
        if urlparse(final_url).hostname not in BLS_HOSTS:
            raise ValueError(f"unexpected redirect host: {final_url}")
        content_type = response.headers.get_content_type()
        payload = response.read()
    if not payload:
        raise ValueError(f"empty source document: {url}")
    return payload, content_type


def archive(manifest_path: Path, output_dir: Path, retrieved_at: str | None = None) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    urls = manifest.get("source_urls")
    document_ids = manifest.get("source_document_ids")
    if not isinstance(urls, list) or not isinstance(document_ids, list):
        raise ValueError("vintage manifest must list source_urls and source_document_ids")
    if len(urls) != len(document_ids) or not urls:
        raise ValueError("source URL/document ID coverage mismatch")

    retrieved_at = retrieved_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    output_dir.mkdir(parents=True, exist_ok=True)

    documents = []
    for source_url, document_id in zip(urls, document_ids, strict=True):
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or parsed.hostname not in BLS_HOSTS:
            raise ValueError(f"source URL is not HTTPS BLS: {source_url}")
        if not isinstance(document_id, str) or not document_id.startswith("USDL-"):
            raise ValueError(f"invalid source document ID: {document_id}")

        payload, content_type = _fetch(source_url)
        suffix = Path(parsed.path).suffix.lower()
        if suffix == ".pdf":
            if not payload.startswith(b"%PDF-"):
                raise ValueError(f"expected PDF bytes: {source_url}")
        else:
            text = payload.decode("utf-8", errors="replace")
            if document_id not in text or "EMPLOYMENT SITUATION" not in text.upper():
                raise ValueError(f"BLS document identity markers missing: {source_url}")
            suffix = ".htm"

        filename = f"{document_id}{suffix}"
        path = output_dir / filename
        path.write_bytes(payload)
        documents.append({
            "source_document_id": document_id,
            "source_url": source_url,
            "path": filename,
            "content_type": content_type,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })

    output_manifest = {
        "schema_version": 1,
        "authority": "U.S. Bureau of Labor Statistics",
        "dataset_id": manifest.get("dataset_id"),
        "retrieved_at": retrieved_at,
        "document_count": len(documents),
        "documents": documents,
    }
    (output_dir / "manifest.json").write_text(_dump_json(output_manifest), encoding="utf-8", newline="")
    return output_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("docs/api/v1/vintage-manifest.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--retrieved-at")
    args = parser.parse_args()
    result = archive(args.manifest, args.output_dir, args.retrieved_at)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
