"""FastAPI app with dynamic route registration from the OpenAPI spec."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from digitaltwin.auth import AuthMiddleware
from digitaltwin.config import API_PREFIX
from digitaltwin.errors import DiscordError
from digitaltwin.mock import generate_mock_response
from digitaltwin.ratelimit import RateLimitMiddleware
from digitaltwin.spec_loader import Operation, get_operations, load_spec
from digitaltwin.store.state import state
from digitaltwin.snowflake import generate_snowflake
from digitaltwin.gateway_ws import broadcast_event
from datetime import datetime, timezone

# Force handler registration by importing all handler modules
import digitaltwin.handlers.users  # noqa: F401
import digitaltwin.handlers.guilds  # noqa: F401
import digitaltwin.handlers.channels  # noqa: F401
import digitaltwin.handlers.messages  # noqa: F401
import digitaltwin.handlers.roles  # noqa: F401
import digitaltwin.handlers.members  # noqa: F401
import digitaltwin.handlers.gateway  # noqa: F401
import digitaltwin.handlers.interactions  # noqa: F401
import digitaltwin.handlers.webhooks  # noqa: F401
import digitaltwin.handlers.events  # noqa: F401
from digitaltwin.handlers.registry import HANDLER_REGISTRY
from digitaltwin.gateway_ws import gateway_ws_handler


def _find_spec_path() -> Path:
    candidates = [
        Path("specs/openapi.json"),
        Path(__file__).parent.parent / "specs" / "openapi.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("Cannot find specs/openapi.json")


def create_app() -> FastAPI:
    app = FastAPI(title="Discord API Digital Twin", version="10")

    spec = load_spec(_find_spec_path())
    operations = get_operations(spec)

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthMiddleware)

    @app.exception_handler(DiscordError)
    async def handle_discord_error(request: Request, exc: DiscordError) -> JSONResponse:
        return exc.to_response()

    # Store spec on app state for mock generation
    app.state.spec = spec

    _register_routes(app, operations, spec)
    _register_extra_handlers(app)

    app.add_websocket_route("/gateway", gateway_ws_handler)

    @app.get("/_frontend/state")
    async def get_frontend_state():
        return {
            "guilds": state.guilds,
            "channels": state.channels,
            "users": state.users,
            "messages": state.messages,
            "channel_messages": state.channel_messages,
            "bot_user": state.bot_user,
            "human_user": getattr(state, "human_user", None),
        }

    @app.post("/_frontend/messages")
    async def frontend_send_message(request: Request):
        body = await request.json()
        channel_id = body.get("channel_id")
        content = body.get("content")
        
        msg_id = generate_snowflake()
        message = {
            "id": msg_id,
            "type": 0,
            "content": content,
            "channel_id": channel_id,
            "author": getattr(state, "human_user", state.bot_user),
            "attachments": [],
            "embeds": [],
            "mentions": [],
            "mention_roles": [],
            "pinned": False,
            "mention_everyone": False,
            "tts": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "edited_timestamp": None,
            "flags": 0,
            "components": [],
            "nonce": None,
            "referenced_message": None,
        }
        state.messages[msg_id] = message
        state.channel_messages.setdefault(channel_id, []).append(msg_id)
        
        ch = state.channels.get(channel_id)
        if ch:
            ch["last_message_id"] = msg_id
            guild_id = ch.get("guild_id")
            dispatch_msg = dict(message)
            if guild_id:
                dispatch_msg["guild_id"] = guild_id
            await broadcast_event("MESSAGE_CREATE", dispatch_msg)
            
        return message

    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


def _normalize_path(openapi_path: str) -> str:
    """Convert OpenAPI path to FastAPI path, prefixed with /api/v10."""
    return API_PREFIX + openapi_path


def _register_routes(app: FastAPI, operations: list[Operation], spec: dict) -> None:
    registered: set[tuple[str, str]] = set()

    # Sort: literal paths before parameterized so /users/@me wins over /users/{user_id}
    operations.sort(key=lambda o: o.path.count("{"))

    for op in operations:
        fastapi_path = _normalize_path(op.path)
        method = op.method.upper()
        key = (method, fastapi_path)

        if key in registered:
            continue
        registered.add(key)

        handler_key = (method, op.path)
        stateful_handler = HANDLER_REGISTRY.get(handler_key)

        response_schema = op.success_response_schema
        success_status = op.success_status

        if stateful_handler:
            _add_route(app, method, fastapi_path, stateful_handler)
        else:
            _add_mock_route(app, method, fastapi_path, response_schema, success_status, spec)


def _register_extra_handlers(app: FastAPI) -> None:
    """Register handler-registry entries that have no matching spec operation."""
    existing = set()
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for m in route.methods:
                existing.add((m, route.path))

    for (method, path), handler in HANDLER_REGISTRY.items():
        fastapi_path = _normalize_path(path)
        if (method, fastapi_path) not in existing:
            _add_route(app, method, fastapi_path, handler)


def _wrap_handler(handler):
    """Wrap a handler so FastAPI only sees (request: Request) — we handle path param injection."""
    async def wrapped(request: Request) -> Response:
        result = await handler(request, **request.path_params)
        if isinstance(result, Response):
            return result
        return JSONResponse(result)
    wrapped.__name__ = getattr(handler, "__name__", "handler")
    wrapped.__qualname__ = getattr(handler, "__qualname__", wrapped.__name__)
    return wrapped


def _add_route(app: FastAPI, method: str, path: str, handler) -> None:
    endpoint = _wrap_handler(handler)
    app.add_api_route(path, endpoint, methods=[method], response_model=None)


def _add_mock_route(
    app: FastAPI,
    method: str,
    path: str,
    response_schema: dict | None,
    success_status: int,
    spec: dict,
) -> None:
    _schema = response_schema
    _status = success_status
    _spec = spec

    async def mock_handler(request: Request, **kwargs: Any) -> Response:
        if _status == 204 or _schema is None:
            return Response(status_code=204)
        body = generate_mock_response(_schema, _spec)
        return JSONResponse(body, status_code=_status)

    slug = re.sub(r"[{}/@]", "_", path).strip("_")
    mock_handler.__name__ = f"mock_{method.lower()}_{slug}"
    mock_handler.__qualname__ = mock_handler.__name__

    _add_route(app, method, path, mock_handler)
