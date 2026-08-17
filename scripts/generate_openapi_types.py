"""Generate TypeScript types from the exported OpenAPI 3 schema.

The output file (``apps/web/src/api-types.ts``) is committed and consumed by
the frontend contracts; ``git diff --exit-code`` on it in CI acts as the
contract-drift check, so hand-written TypeScript contracts cannot silently
diverge from the FastAPI schema.

Usage:
    python scripts/generate_openapi_types.py [--openapi docs/api/openapi.json]
        [--output apps/web/src/api-types.ts]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPENAPI = ROOT / "docs" / "api" / "openapi.json"
DEFAULT_OUTPUT = ROOT / "apps" / "web" / "src" / "api-types.ts"

_REF_RE = re.compile(r"#/components/schemas/(.+)")

_TS_KEYWORDS = {
    "string",
    "number",
    "boolean",
    "object",
    "any",
    "unknown",
    "never",
}


def _type_name(name: str) -> str:
    """Sanitize a schema name into a valid TypeScript type identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"T_{cleaned}"
    return cleaned


def _resolve_ref(ref: str) -> str:
    match = _REF_RE.match(ref)
    if not match:
        raise ValueError(f"unsupported $ref: {ref}")
    return _type_name(match.group(1))


def _ts_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    escaped = json.dumps(str(value), ensure_ascii=False)
    return escaped


def _schema_to_ts(schema: dict[str, Any], schemas: dict[str, Any]) -> str:
    """Convert one JSON Schema node to a TypeScript type expression."""
    if "$ref" in schema:
        return _resolve_ref(str(schema["$ref"]))

    if "allOf" in schema:
        merged = [_schema_to_ts(item, schemas) for item in schema["allOf"]]
        return " & ".join(f"({part})" for part in merged)

    if "anyOf" in schema or "oneOf" in schema:
        variants = schema.get("anyOf") or schema.get("oneOf") or []
        variant_ts: list[str] = []
        for variant in variants:
            if isinstance(variant, dict) and variant.get("type") == "null":
                variant_ts.append("null")
            else:
                variant_ts.append(_schema_to_ts(variant, schemas))
        return " | ".join(dict.fromkeys(variant_ts))

    if "enum" in schema:
        values = [_ts_literal(value) for value in schema["enum"]]
        return " | ".join(values) if values else "never"

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        non_null = [t for t in schema_type if t != "null"]
        base = _schema_to_ts({**schema, "type": non_null[0]}, schemas)
        if "null" in schema_type:
            return f"{base} | null"
        return base

    if schema_type == "array":
        items = schema.get("items", {})
        item_ts = (
            _schema_to_ts(items, schemas)
            if isinstance(items, dict)
            else "unknown"
        )
        return f"{item_ts}[]"

    if schema_type == "object" or "properties" in schema:
        required = set(schema.get("required", []))
        lines: list[str] = []
        for prop_name, prop_schema in (schema.get("properties") or {}).items():
            prop_ts = _schema_to_ts(prop_schema, schemas)
            if prop_name in required:
                lines.append(f"  {prop_name}: {prop_ts};")
            else:
                lines.append(f"  {prop_name}?: {prop_ts};")
        additional = schema.get("additionalProperties", True)
        if additional is True:
            lines.append("  [key: string]: unknown;")
        elif isinstance(additional, dict):
            value_ts = _schema_to_ts(additional, schemas)
            lines.append(f"  [key: string]: {value_ts};")
        if not lines:
            return "Record<string, unknown>"
        return "{\n" + "\n".join(lines) + "\n}"

    if schema_type == "string":
        return "string"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "null":
        return "null"

    return "unknown"


def _render_schema(name: str, schema: dict[str, Any], schemas: dict[str, Any]) -> str:
    ts = _schema_to_ts(schema, schemas)
    return f"export type {name} = {ts};"


def generate(openapi: dict[str, Any]) -> str:
    schemas = openapi.get("components", {}).get("schemas", {})
    header = [
        "/*",
        " * GENERATED FILE — do not edit by hand.",
        " * Run: python scripts/generate_openapi_types.py",
        " * Source: exported OpenAPI 3 schema (docs/api/openapi.json).",
        " */",
        "",
        "/* eslint-disable */",
        "",
    ]
    body: list[str] = []
    for raw_name in sorted(schemas):
        name = _type_name(raw_name)
        if name in _TS_KEYWORDS:
            name = f"Schema{name.capitalize()}"
        body.append(_render_schema(name, schemas[raw_name], schemas))
        body.append("")
    return "\n".join(header + body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openapi", type=Path, default=DEFAULT_OPENAPI)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = json.loads(args.openapi.read_text(encoding="utf-8"))
    rendered = generate(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"TypeScript API types written: {args.output} ({len(rendered)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
