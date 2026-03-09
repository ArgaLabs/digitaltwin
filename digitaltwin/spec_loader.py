"""Parse the Discord OpenAPI spec and extract path/operation/schema info."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Parameter:
    name: str
    location: str  # "path", "query", "header"
    required: bool = False
    schema: dict = field(default_factory=dict)


@dataclass
class Operation:
    method: str
    path: str
    operation_id: str
    parameters: list[Parameter] = field(default_factory=list)
    request_body_schema: dict | None = None
    success_response_schema: dict | None = None
    success_status: int = 200
    security: list[dict] = field(default_factory=list)


def load_spec(path: str | Path = "specs/openapi.json") -> dict:
    with open(path) as f:
        return json.load(f)


def _resolve_ref(spec: dict, ref: str) -> dict:
    parts = ref.lstrip("#/").split("/")
    node = spec
    for p in parts:
        node = node[p]
    return node


def resolve_schema(spec: dict, schema: dict) -> dict:
    """Recursively resolve $ref pointers one level."""
    if "$ref" in schema:
        return _resolve_ref(spec, schema["$ref"])
    return schema


def _extract_success_response(spec: dict, responses: dict) -> tuple[int, dict | None]:
    for code in ("200", "201", "204"):
        if code in responses:
            resp = responses[code]
            if "$ref" in resp:
                resp = _resolve_ref(spec, resp["$ref"])
            if code == "204":
                return 204, None
            content = resp.get("content", {})
            json_content = content.get("application/json", {})
            schema = json_content.get("schema")
            if schema:
                return int(code), resolve_schema(spec, schema)
            return int(code), None
    return 200, None


def _openapi_path_to_fastapi(path: str) -> str:
    """Convert OpenAPI path params like {guild_id} to FastAPI format (already compatible)."""
    return path


def get_operations(spec: dict) -> list[Operation]:
    ops: list[Operation] = []
    paths = spec.get("paths", {})

    shared_params_cache: dict[str, list[Parameter]] = {}

    for path, path_item in paths.items():
        if "$ref" in path_item:
            path_item = _resolve_ref(spec, path_item["$ref"])

        shared_params = []
        for p in path_item.get("parameters", []):
            if "$ref" in p:
                p = _resolve_ref(spec, p["$ref"])
            shared_params.append(
                Parameter(
                    name=p["name"],
                    location=p["in"],
                    required=p.get("required", False),
                    schema=p.get("schema", {}),
                )
            )

        for method in ("get", "post", "put", "patch", "delete"):
            op_data = path_item.get(method)
            if not op_data:
                continue

            params = list(shared_params)
            for p in op_data.get("parameters", []):
                if "$ref" in p:
                    p = _resolve_ref(spec, p["$ref"])
                params.append(
                    Parameter(
                        name=p["name"],
                        location=p["in"],
                        required=p.get("required", False),
                        schema=p.get("schema", {}),
                    )
                )

            request_body_schema = None
            rb = op_data.get("requestBody", {})
            if rb:
                if "$ref" in rb:
                    rb = _resolve_ref(spec, rb["$ref"])
                json_content = rb.get("content", {}).get("application/json", {})
                if "schema" in json_content:
                    request_body_schema = resolve_schema(spec, json_content["schema"])

            success_status, response_schema = _extract_success_response(
                spec, op_data.get("responses", {})
            )

            ops.append(
                Operation(
                    method=method,
                    path=path,
                    operation_id=op_data.get("operationId", f"{method}_{path}"),
                    parameters=params,
                    request_body_schema=request_body_schema,
                    success_response_schema=response_schema,
                    success_status=success_status,
                    security=op_data.get("security", []),
                )
            )

    return ops
