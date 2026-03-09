"""Guild member endpoint handlers."""

from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from digitaltwin.errors import unknown_resource
from digitaltwin.handlers.registry import register
from digitaltwin.snowflake import generate_snowflake
from digitaltwin.store.state import state


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@register("GET", "/guilds/{guild_id}/members")
async def list_guild_members(request: Request, guild_id: str, **kwargs) -> list | JSONResponse:
    if guild_id not in state.guilds:
        return unknown_resource("Guild").to_response()
    limit = int(request.query_params.get("limit", "1000"))
    members = list(state.members.get(guild_id, {}).values())
    return members[:limit]


@register("GET", "/guilds/{guild_id}/members/{user_id}")
async def get_guild_member(request: Request, guild_id: str, user_id: str, **kwargs) -> dict | JSONResponse:
    if guild_id not in state.guilds:
        return unknown_resource("Guild").to_response()
    member = state.members.get(guild_id, {}).get(user_id)
    if not member:
        return unknown_resource("Member").to_response()
    return member


@register("PUT", "/guilds/{guild_id}/members/{user_id}")
async def add_guild_member(request: Request, guild_id: str, user_id: str, **kwargs) -> dict | JSONResponse:
    if guild_id not in state.guilds:
        return unknown_resource("Guild").to_response()

    user = state.users.get(user_id)
    if not user:
        user = {
            "id": user_id,
            "username": f"user_{user_id[:6]}",
            "discriminator": "0000",
            "global_name": None,
            "avatar": None,
            "bot": False,
            "system": False,
            "flags": 0,
            "public_flags": 0,
        }
        state.users[user_id] = user

    member = {
        "user": user,
        "nick": None,
        "avatar": None,
        "roles": [],
        "joined_at": _now_iso(),
        "premium_since": None,
        "deaf": False,
        "mute": False,
        "flags": 0,
        "pending": False,
        "communication_disabled_until": None,
    }
    state.members.setdefault(guild_id, {})[user_id] = member
    return member


@register("PATCH", "/guilds/{guild_id}/members/{user_id}")
async def modify_guild_member(request: Request, guild_id: str, user_id: str, **kwargs) -> dict | JSONResponse:
    if guild_id not in state.guilds:
        return unknown_resource("Guild").to_response()
    member = state.members.get(guild_id, {}).get(user_id)
    if not member:
        return unknown_resource("Member").to_response()
    body = await request.json()
    for key in ("nick", "roles", "mute", "deaf", "channel_id", "communication_disabled_until"):
        if key in body:
            member[key] = body[key]
    return member


@register("DELETE", "/guilds/{guild_id}/members/{user_id}")
async def remove_guild_member(request: Request, guild_id: str, user_id: str, **kwargs) -> Response | JSONResponse:
    if guild_id not in state.guilds:
        return unknown_resource("Guild").to_response()
    state.members.get(guild_id, {}).pop(user_id, None)
    return Response(status_code=204)


@register("PUT", "/guilds/{guild_id}/members/{user_id}/roles/{role_id}")
async def add_member_role(request: Request, guild_id: str, user_id: str, role_id: str, **kwargs) -> Response | JSONResponse:
    if guild_id not in state.guilds:
        return unknown_resource("Guild").to_response()
    member = state.members.get(guild_id, {}).get(user_id)
    if not member:
        return unknown_resource("Member").to_response()
    if role_id not in member["roles"]:
        member["roles"].append(role_id)
    return Response(status_code=204)


@register("DELETE", "/guilds/{guild_id}/members/{user_id}/roles/{role_id}")
async def remove_member_role(request: Request, guild_id: str, user_id: str, role_id: str, **kwargs) -> Response | JSONResponse:
    if guild_id not in state.guilds:
        return unknown_resource("Guild").to_response()
    member = state.members.get(guild_id, {}).get(user_id)
    if not member:
        return unknown_resource("Member").to_response()
    if role_id in member["roles"]:
        member["roles"].remove(role_id)
    return Response(status_code=204)


@register("PUT", "/guilds/{guild_id}/bans/{user_id}")
async def create_guild_ban(request: Request, guild_id: str, user_id: str, **kwargs) -> Response | JSONResponse:
    if guild_id not in state.guilds:
        return unknown_resource("Guild").to_response()
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    user = state.users.get(user_id, {"id": user_id, "username": f"user_{user_id[:6]}"})
    state.bans.setdefault(guild_id, {})[user_id] = {
        "reason": body.get("reason") or body.get("delete_message_days") and "Banned" or None,
        "user": user,
    }
    state.members.get(guild_id, {}).pop(user_id, None)
    return Response(status_code=204)


@register("DELETE", "/guilds/{guild_id}/bans/{user_id}")
async def remove_guild_ban(request: Request, guild_id: str, user_id: str, **kwargs) -> Response | JSONResponse:
    if guild_id not in state.guilds:
        return unknown_resource("Guild").to_response()
    state.bans.get(guild_id, {}).pop(user_id, None)
    return Response(status_code=204)
