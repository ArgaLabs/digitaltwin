"""Role endpoint handlers."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from digitaltwin.errors import unknown_resource
from digitaltwin.handlers.registry import register
from digitaltwin.snowflake import generate_snowflake
from digitaltwin.store.state import state


@register("GET", "/guilds/{guild_id}/roles")
async def get_guild_roles(request: Request, guild_id: str, **kwargs) -> list | JSONResponse:
    guild = state.guilds.get(guild_id)
    if not guild:
        return unknown_resource("Guild").to_response()
    return guild.get("roles", [])


@register("POST", "/guilds/{guild_id}/roles")
async def create_guild_role(request: Request, guild_id: str, **kwargs) -> dict | JSONResponse:
    guild = state.guilds.get(guild_id)
    if not guild:
        return unknown_resource("Guild").to_response()
    body = await request.json()
    role_id = generate_snowflake()
    role = {
        "id": role_id,
        "name": body.get("name", "new role"),
        "color": body.get("color", 0),
        "hoist": body.get("hoist", False),
        "icon": body.get("icon"),
        "unicode_emoji": body.get("unicode_emoji"),
        "position": len(guild["roles"]),
        "permissions": body.get("permissions", "0"),
        "managed": False,
        "mentionable": body.get("mentionable", False),
        "flags": 0,
    }
    guild["roles"].append(role)
    state.roles[role_id] = role
    return role


@register("PATCH", "/guilds/{guild_id}/roles/{role_id}")
async def modify_guild_role(request: Request, guild_id: str, role_id: str, **kwargs) -> dict | JSONResponse:
    guild = state.guilds.get(guild_id)
    if not guild:
        return unknown_resource("Guild").to_response()
    role = state.roles.get(role_id)
    if not role:
        return unknown_resource("Role").to_response()
    body = await request.json()
    for key in ("name", "color", "hoist", "icon", "unicode_emoji", "permissions", "mentionable"):
        if key in body:
            role[key] = body[key]
    return role


@register("DELETE", "/guilds/{guild_id}/roles/{role_id}")
async def delete_guild_role(request: Request, guild_id: str, role_id: str, **kwargs) -> Response | JSONResponse:
    guild = state.guilds.get(guild_id)
    if not guild:
        return unknown_resource("Guild").to_response()
    guild["roles"] = [r for r in guild["roles"] if r["id"] != role_id]
    state.roles.pop(role_id, None)
    return Response(status_code=204)


@register("PATCH", "/guilds/{guild_id}/roles")
async def modify_guild_role_positions(request: Request, guild_id: str, **kwargs) -> list | JSONResponse:
    guild = state.guilds.get(guild_id)
    if not guild:
        return unknown_resource("Guild").to_response()
    body = await request.json()
    pos_map = {item["id"]: item.get("position", 0) for item in body}
    for role in guild["roles"]:
        if role["id"] in pos_map:
            role["position"] = pos_map[role["id"]]
    guild["roles"].sort(key=lambda r: r["position"])
    return guild["roles"]
