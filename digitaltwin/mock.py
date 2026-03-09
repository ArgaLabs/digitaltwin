"""Generate plausible mock responses from OpenAPI JSON Schema definitions."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from digitaltwin.snowflake import generate_snowflake


def generate_mock_value(schema: dict, spec: dict | None = None, field_name: str = "") -> Any:
    """Produce a value that satisfies *schema*."""
    if not schema:
        return None

    if "$ref" in schema and spec:
        ref = schema["$ref"]
        parts = ref.lstrip("#/").split("/")
        node = spec
        for p in parts:
            node = node[p]
        return generate_mock_value(node, spec, field_name)

    if "oneOf" in schema:
        return generate_mock_value(schema["oneOf"][0], spec, field_name)
    if "anyOf" in schema:
        non_null = [s for s in schema["anyOf"] if s.get("type") != "null"]
        if non_null:
            return generate_mock_value(non_null[0], spec, field_name)
        return None

    typ = schema.get("type")
    if isinstance(typ, list):
        typ = next((t for t in typ if t != "null"), typ[0])

    if typ == "object":
        props = schema.get("properties", {})
        result = {}
        for k, v in props.items():
            result[k] = generate_mock_value(v, spec, k)
        return result

    if typ == "array":
        items_schema = schema.get("items", {})
        return [generate_mock_value(items_schema, spec, field_name)]

    if typ == "string":
        fmt = schema.get("format", "")
        if fmt == "date-time" or field_name.endswith("_at"):
            return datetime.now(timezone.utc).isoformat()
        if "snowflake" in fmt or field_name == "id" or field_name.endswith("_id"):
            return generate_snowflake()
        if "enum" in schema:
            return schema["enum"][0]
        return _string_heuristic(field_name)

    if typ == "integer":
        if "enum" in schema:
            return schema["enum"][0]
        if field_name in ("type", "flags", "permissions"):
            return 0
        return 0

    if typ == "number":
        return 0.0

    if typ == "boolean":
        return False

    if typ == "null":
        return None

    return None


def _string_heuristic(name: str) -> str:
    lower = name.lower()
    if "name" in lower:
        return "mock-name"
    if "icon" in lower or "avatar" in lower or "image" in lower:
        return None  # type: ignore[return-value]
    if "url" in lower:
        return "https://example.com"
    if "email" in lower:
        return "mock@example.com"
    if "hash" in lower:
        return "abcdef1234567890"
    if "token" in lower:
        return "mock-token"
    return ""


def generate_mock_response(schema: dict | None, spec: dict | None = None) -> Any:
    if schema is None:
        return None
    return generate_mock_value(schema, spec)
