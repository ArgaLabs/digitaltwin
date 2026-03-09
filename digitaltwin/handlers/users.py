"""User endpoint handlers."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from digitaltwin.errors import unknown_resource
from digitaltwin.handlers.registry import register
from digitaltwin.store.state import state


@register("GET", "/users/@me")
async def get_current_user(request: Request, **kwargs) -> dict:
    return state.bot_user


@register("PATCH", "/users/@me")
async def modify_current_user(request: Request, **kwargs) -> dict:
    body = await request.json()
    if "username" in body:
        state.bot_user["username"] = body["username"]
    if "avatar" in body:
        state.bot_user["avatar"] = body["avatar"]
    return state.bot_user


@register("GET", "/users/{user_id}")
async def get_user(request: Request, user_id: str, **kwargs) -> dict | JSONResponse:
    user = state.users.get(user_id)
    if not user:
        return unknown_resource("User").to_response()
    return user


@register("GET", "/users/@me/guilds")
async def get_current_user_guilds(request: Request, **kwargs) -> list:
    return list(state.guilds.values())


@register("GET", "/users/@me/channels")
async def get_user_dms(request: Request, **kwargs) -> list:
    return []


@register("GET", "/oauth2/applications/@me")
async def get_oauth2_application(request: Request, **kwargs) -> dict:
    return await get_my_application(request)


@register("GET", "/applications/@me")
async def get_my_application(request: Request, **kwargs) -> dict:
    app = dict(state.application)
    app.setdefault("owner", state.bot_user)
    app.setdefault("team", None)
    app.setdefault("verify_key", "e7aabbdd12345678" * 4)
    app.setdefault("install_params", {
        "scopes": ["applications.commands"],
        "permissions": "0",
    })
    app.setdefault("integration_types_config", {})
    return app


@register("PATCH", "/applications/@me")
async def update_my_application(request: Request, **kwargs) -> dict:
    body = await request.json()
    for key in ("name", "description", "icon", "interactions_endpoint_url", "tags"):
        if key in body:
            state.application[key] = body[key]
    return await get_my_application(request)
