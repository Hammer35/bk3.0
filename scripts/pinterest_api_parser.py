#!/usr/bin/env python3
"""
Pinterest API inventory parser for BOOSTKLIENT® 3.0.

Source of truth:
https://github.com/pinterest/api-description
https://raw.githubusercontent.com/pinterest/api-description/main/v5/openapi.json

The script does NOT scrape Pinterest product pages. It reads Pinterest's
official MIT-licensed OpenAPI description and produces a compact inventory
of endpoints, scopes, rate-limit categories and Sandbox support.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OPENAPI_URL = (
    "https://raw.githubusercontent.com/pinterest/api-description/"
    "main/v5/openapi.json"
)
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def download_json(url: str) -> tuple[dict[str, Any], bytes]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BOOSTKLIENT-Pinterest-API-Inventory/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    return json.loads(raw), raw


def normalize_security(operation: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for security_item in operation.get("security", []) or []:
        for scheme, scopes in security_item.items():
            for scope in scopes or []:
                result[scheme].add(scope)
    return {scheme: sorted(scopes) for scheme, scopes in sorted(result.items())}


def build_inventory(spec: dict[str, Any], source_url: str, raw: bytes) -> dict[str, Any]:
    endpoints: list[dict[str, Any]] = []
    tags = Counter()
    rate_categories = Counter()
    scopes = Counter()
    sandbox = Counter()

    for path, path_item in (spec.get("paths") or {}).items():
        for method, operation in path_item.items():
            method_lower = method.lower()
            if method_lower not in HTTP_METHODS or not isinstance(operation, dict):
                continue

            security = normalize_security(operation)
            for scheme_scopes in security.values():
                for scope in scheme_scopes:
                    scopes[scope] += 1

            op_tags = operation.get("tags") or ["untagged"]
            for tag in op_tags:
                tags[tag] += 1

            rate_category = operation.get("x-ratelimit-category")
            if rate_category:
                rate_categories[str(rate_category)] += 1

            sandbox_value = operation.get("x-sandbox", "unspecified")
            sandbox[str(sandbox_value)] += 1

            endpoints.append(
                {
                    "method": method_lower.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId"),
                    "summary": operation.get("summary"),
                    "tags": op_tags,
                    "security": security,
                    "rate_limit_category": rate_category,
                    "sandbox": sandbox_value,
                }
            )

    endpoints.sort(key=lambda item: (item["path"], item["method"]))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_url": source_url,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "openapi": spec.get("openapi"),
        "api_title": (spec.get("info") or {}).get("title"),
        "api_version": (spec.get("info") or {}).get("version"),
        "endpoint_count": len(endpoints),
        "tag_counts": dict(sorted(tags.items())),
        "scope_usage_counts": dict(sorted(scopes.items())),
        "rate_limit_category_counts": dict(sorted(rate_categories.items())),
        "sandbox_values": dict(sorted(sandbox.items())),
        "endpoints": endpoints,
    }


def markdown(inventory: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Pinterest API — generated inventory")
    lines.append("")
    lines.append(f"- API: {inventory.get('api_title')}")
    lines.append(f"- API version: {inventory.get('api_version')}")
    lines.append(f"- OpenAPI: {inventory.get('openapi')}")
    lines.append(f"- Endpoints: {inventory.get('endpoint_count')}")
    lines.append(f"- Generated: {inventory.get('generated_at')}")
    lines.append(f"- Source: {inventory.get('source_url')}")
    lines.append(f"- Source SHA-256: {inventory.get('source_sha256')}")
    lines.append("")

    lines.append("## Scopes found in endpoint security declarations")
    lines.append("")
    for scope, count in inventory["scope_usage_counts"].items():
        lines.append(f"- `{scope}` — {count} endpoint declarations")
    lines.append("")

    lines.append("## Rate-limit categories")
    lines.append("")
    for category, count in inventory["rate_limit_category_counts"].items():
        lines.append(f"- `{category}` — {count} endpoints")
    lines.append("")

    lines.append("## Tags")
    lines.append("")
    for tag, count in inventory["tag_counts"].items():
        lines.append(f"- `{tag}` — {count}")
    lines.append("")

    lines.append("## Endpoints")
    lines.append("")
    lines.append("| Method | Path | Operation | Scopes | Rate category | Sandbox |")
    lines.append("|---|---|---|---|---|---|")
    for endpoint in inventory["endpoints"]:
        scopes: list[str] = []
        for scheme_scopes in endpoint["security"].values():
            scopes.extend(scheme_scopes)
        scope_text = ", ".join(sorted(set(scopes)))
        lines.append(
            "| {method} | `{path}` | {operation} | {scopes} | {rate} | {sandbox} |".format(
                method=endpoint["method"],
                path=endpoint["path"].replace("|", "\\|"),
                operation=(endpoint.get("operation_id") or "").replace("|", "\\|"),
                scopes=scope_text.replace("|", "\\|"),
                rate=str(endpoint.get("rate_limit_category") or ""),
                sandbox=str(endpoint.get("sandbox") or ""),
            )
        )

    lines.append("")
    lines.append(
        "> Generated mechanically from Pinterest's official OpenAPI schema. "
        "Policy requirements and product eligibility must still be checked "
        "against Pinterest Developer Guidelines and current documentation."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=OPENAPI_URL)
    parser.add_argument(
        "--json-out",
        default="docs/generated/pinterest_api_inventory.json",
    )
    parser.add_argument(
        "--md-out",
        default="docs/generated/pinterest_api_inventory.md",
    )
    args = parser.parse_args()

    try:
        spec, raw = download_json(args.source)
    except Exception as exc:
        print(f"Failed to download Pinterest OpenAPI: {exc}", file=sys.stderr)
        return 1

    inventory = build_inventory(spec, args.source, raw)

    json_path = Path(args.json_out)
    md_path = Path(args.md_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(markdown(inventory), encoding="utf-8")

    print(
        f"Pinterest API {inventory.get('api_version')}: "
        f"{inventory.get('endpoint_count')} endpoints"
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
