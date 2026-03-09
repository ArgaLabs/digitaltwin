"""Maps (method, path_template) -> async handler function.

Each handler receives (request, **path_params) and returns a Response or dict.
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from starlette.requests import Request
from starlette.responses import Response

HandlerFunc = Callable[..., Coroutine[Any, Any, Response | dict | list | None]]

HANDLER_REGISTRY: dict[tuple[str, str], HandlerFunc] = {}


def register(method: str, path: str):
    """Decorator to register a stateful handler."""
    def decorator(func: HandlerFunc) -> HandlerFunc:
        HANDLER_REGISTRY[(method.upper(), path)] = func
        return func
    return decorator
