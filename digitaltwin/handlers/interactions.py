"""Application command (interaction) handlers."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from digitaltwin.errors import unknown_resource
from digitaltwin.handlers.registry import register
from digitaltwin.snowflake import generate_snowflake
from digitaltwin.store.state import state


def _app_id(request: Request) -> str:
    return state.bot_user["id"]


# --- Global application commands ---

@register("GET", "/applications/{application_id}/commands")
async def get_global_commands(request: Request, application_id: str, **kwargs) -> list:
    return list(state.application_commands.get("global", {}).values())


@register("POST", "/applications/{application_id}/commands")
async def create_global_command(request: Request, application_id: str, **kwargs) -> dict:
    body = await request.json()
    cmd_id = generate_snowflake()
    cmd = {
        "id": cmd_id,
        "type": body.get("type", 1),
        "application_id": application_id,
        "guild_id": None,
        "name": body.get("name", "unnamed"),
        "name_localizations": body.get("name_localizations"),
        "description": body.get("description", ""),
        "description_localizations": body.get("description_localizations"),
        "options": body.get("options", []),
        "default_member_permissions": body.get("default_member_permissions"),
        "dm_permission": body.get("dm_permission", True),
        "nsfw": body.get("nsfw", False),
        "version": generate_snowflake(),
    }
    state.application_commands.setdefault("global", {})[cmd_id] = cmd
    return cmd


@register("GET", "/applications/{application_id}/commands/{command_id}")
async def get_global_command(request: Request, application_id: str, command_id: str, **kwargs) -> dict | JSONResponse:
    cmd = state.application_commands.get("global", {}).get(command_id)
    if not cmd:
        return unknown_resource("ApplicationCommand").to_response()
    return cmd


@register("PATCH", "/applications/{application_id}/commands/{command_id}")
async def edit_global_command(request: Request, application_id: str, command_id: str, **kwargs) -> dict | JSONResponse:
    cmd = state.application_commands.get("global", {}).get(command_id)
    if not cmd:
        return unknown_resource("ApplicationCommand").to_response()
    body = await request.json()
    for key in ("name", "description", "options", "default_member_permissions", "dm_permission", "nsfw"):
        if key in body:
            cmd[key] = body[key]
    return cmd


@register("DELETE", "/applications/{application_id}/commands/{command_id}")
async def delete_global_command(request: Request, application_id: str, command_id: str, **kwargs) -> Response:
    state.application_commands.get("global", {}).pop(command_id, None)
    return Response(status_code=204)


@register("PUT", "/applications/{application_id}/commands")
async def bulk_overwrite_global_commands(request: Request, application_id: str, **kwargs) -> list:
    body = await request.json()
    new_cmds = {}
    for cmd_data in body:
        cmd_id = cmd_data.get("id") or generate_snowflake()
        cmd = {
            "id": cmd_id,
            "type": cmd_data.get("type", 1),
            "application_id": application_id,
            "guild_id": None,
            "name": cmd_data.get("name", "unnamed"),
            "description": cmd_data.get("description", ""),
            "options": cmd_data.get("options", []),
            "default_member_permissions": cmd_data.get("default_member_permissions"),
            "dm_permission": cmd_data.get("dm_permission", True),
            "nsfw": cmd_data.get("nsfw", False),
            "version": generate_snowflake(),
        }
        new_cmds[cmd_id] = cmd
    state.application_commands["global"] = new_cmds
    return list(new_cmds.values())


# --- Guild application commands ---

@register("GET", "/applications/{application_id}/guilds/{guild_id}/commands")
async def get_guild_commands(request: Request, application_id: str, guild_id: str, **kwargs) -> list:
    return list(state.application_commands.get(guild_id, {}).values())


@register("POST", "/applications/{application_id}/guilds/{guild_id}/commands")
async def create_guild_command(request: Request, application_id: str, guild_id: str, **kwargs) -> dict:
    body = await request.json()
    cmd_id = generate_snowflake()
    cmd = {
        "id": cmd_id,
        "type": body.get("type", 1),
        "application_id": application_id,
        "guild_id": guild_id,
        "name": body.get("name", "unnamed"),
        "description": body.get("description", ""),
        "options": body.get("options", []),
        "default_member_permissions": body.get("default_member_permissions"),
        "nsfw": body.get("nsfw", False),
        "version": generate_snowflake(),
    }
    state.application_commands.setdefault(guild_id, {})[cmd_id] = cmd
    return cmd


@register("PATCH", "/applications/{application_id}/guilds/{guild_id}/commands/{command_id}")
async def edit_guild_command(request: Request, application_id: str, guild_id: str, command_id: str, **kwargs) -> dict | JSONResponse:
    cmd = state.application_commands.get(guild_id, {}).get(command_id)
    if not cmd:
        return unknown_resource("ApplicationCommand").to_response()
    body = await request.json()
    for key in ("name", "description", "options", "default_member_permissions", "nsfw"):
        if key in body:
            cmd[key] = body[key]
    return cmd


@register("DELETE", "/applications/{application_id}/guilds/{guild_id}/commands/{command_id}")
async def delete_guild_command(request: Request, application_id: str, guild_id: str, command_id: str, **kwargs) -> Response:
    state.application_commands.get(guild_id, {}).pop(command_id, None)
    return Response(status_code=204)
