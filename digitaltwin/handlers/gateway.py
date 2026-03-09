"""Gateway endpoint handlers — return the twin's own gateway URL."""

from __future__ import annotations

from starlette.requests import Request

from digitaltwin.handlers.registry import register


@register("GET", "/gateway")
async def get_gateway(request: Request, **kwargs) -> dict:
    host = request.headers.get("host", "localhost:8080")
    return {"url": f"ws://{host}/gateway"}


@register("GET", "/gateway/bot")
async def get_gateway_bot(request: Request, **kwargs) -> dict:
    host = request.headers.get("host", "localhost:8080")
    return {
        "url": f"ws://{host}/gateway",
        "shards": 1,
        "session_start_limit": {
            "total": 1000,
            "remaining": 999,
            "reset_after": 86400000,
            "max_concurrency": 1,
        },
    }
