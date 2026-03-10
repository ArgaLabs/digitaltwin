"""Guild endpoint handlers."""

from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from digitaltwin.errors import DiscordError, unknown_resource
from digitaltwin.handlers.registry import register
from digitaltwin.snowflake import generate_snowflake
from digitaltwin.store.state import state


def _guild_or_404(guild_id: str):
    g = state.guilds.get(guild_id)
    if not g:
        raise unknown_resource("Guild")
    return g


@register("GET", "/guilds/{guild_id}")
async def get_guild(request: Request, guild_id: str, **kwargs) -> dict | JSONResponse:
    try:
        return _guild_or_404(guild_id)
    except Exception as e:
        return e.to_response()


@register("GET", "/guilds/{guild_id}/preview")
async def get_guild_preview(request: Request, guild_id: str, **kwargs) -> dict | JSONResponse:
    try:
        g = _guild_or_404(guild_id)
    except Exception as e:
        return e.to_response()
    return {
        "id": g["id"],
        "name": g["name"],
        "icon": g.get("icon"),
        "splash": g.get("splash"),
        "discovery_splash": g.get("discovery_splash"),
        "emojis": g.get("emojis", []),
        "features": g.get("features", []),
        "approximate_member_count": g.get("approximate_member_count", 1),
        "approximate_presence_count": g.get("approximate_presence_count", 1),
        "description": g.get("description"),
        "stickers": g.get("stickers", []),
    }


@register("POST", "/guilds")
async def create_guild(request: Request, **kwargs) -> dict:
    body = await request.json()
    guild_id = generate_snowflake()
    everyone_role_id = guild_id
    guild = {
        "id": guild_id,
        "name": body.get("name", "New Guild"),
        "icon": body.get("icon"),
        "icon_hash": None,
        "splash": None,
        "discovery_splash": None,
        "owner": True,
        "owner_id": state.bot_user["id"],
        "permissions": "2147483647",
        "region": body.get("region", "us-west"),
        "afk_channel_id": None,
        "afk_timeout": 300,
        "widget_enabled": False,
        "widget_channel_id": None,
        "verification_level": body.get("verification_level", 0),
        "default_message_notifications": body.get("default_message_notifications", 0),
        "explicit_content_filter": body.get("explicit_content_filter", 0),
        "roles": [
            {
                "id": everyone_role_id,
                "name": "@everyone",
                "color": 0,
                "hoist": False,
                "icon": None,
                "unicode_emoji": None,
                "position": 0,
                "permissions": "1071698660929",
                "managed": False,
                "mentionable": False,
                "flags": 0,
            }
        ],
        "emojis": [],
        "features": [],
        "mfa_level": 0,
        "application_id": None,
        "system_channel_id": None,
        "system_channel_flags": body.get("system_channel_flags", 0),
        "rules_channel_id": None,
        "max_presences": None,
        "max_members": 500000,
        "vanity_url_code": None,
        "description": None,
        "banner": None,
        "premium_tier": 0,
        "premium_subscription_count": 0,
        "preferred_locale": "en-US",
        "public_updates_channel_id": None,
        "max_video_channel_users": 25,
        "max_stage_video_channel_users": 50,
        "approximate_member_count": 1,
        "approximate_presence_count": 1,
        "nsfw_level": 0,
        "stickers": [],
        "premium_progress_bar_enabled": False,
        "safety_alerts_channel_id": None,
        "channels": [],
        "threads": [],
        "members": [],
    }
    state.guilds[guild_id] = guild
    state.roles[everyone_role_id] = guild["roles"][0]
    state.guild_channels[guild_id] = []
    state.members[guild_id] = {
        state.bot_user["id"]: {
            "user": state.bot_user,
            "nick": None,
            "avatar": None,
            "roles": [],
            "joined_at": datetime.now(timezone.utc).isoformat(),
            "premium_since": None,
            "deaf": False,
            "mute": False,
            "flags": 0,
            "pending": False,
            "communication_disabled_until": None,
        }
    }
    return guild


@register("PATCH", "/guilds/{guild_id}")
async def modify_guild(request: Request, guild_id: str, **kwargs) -> dict | JSONResponse:
    try:
        guild = _guild_or_404(guild_id)
    except Exception as e:
        return e.to_response()
    body = await request.json()
    for key in ("name", "icon", "splash", "banner", "description",
                "verification_level", "default_message_notifications",
                "explicit_content_filter", "afk_channel_id", "afk_timeout",
                "system_channel_id", "system_channel_flags"):
        if key in body:
            guild[key] = body[key]
    return guild


@register("DELETE", "/guilds/{guild_id}")
async def delete_guild(request: Request, guild_id: str, **kwargs) -> Response:
    if guild_id in state.guilds:
        del state.guilds[guild_id]
        for ch_id in state.guild_channels.pop(guild_id, []):
            state.channels.pop(ch_id, None)
        state.members.pop(guild_id, None)
    return Response(status_code=204)


@register("GET", "/guilds/{guild_id}/channels")
async def get_guild_channels(request: Request, guild_id: str, **kwargs) -> list | JSONResponse:
    try:
        _guild_or_404(guild_id)
    except Exception as e:
        return e.to_response()
    ch_ids = state.guild_channels.get(guild_id, [])
    return [state.channels[cid] for cid in ch_ids if cid in state.channels]


@register("POST", "/guilds/{guild_id}/channels")
async def create_guild_channel(request: Request, guild_id: str, **kwargs) -> dict | JSONResponse:
    try:
        _guild_or_404(guild_id)
    except Exception as e:
        return e.to_response()
    body = await request.json()
    name = body.get("name", "new-channel")
    existing_ids = state.guild_channels.get(guild_id, [])
    for cid in existing_ids:
        ch = state.channels.get(cid)
        if ch and ch["name"] == name:
            return DiscordError(
                50035,
                f"Channel name '{name}' already exists in this guild",
                400,
            ).to_response()
    channel_id = generate_snowflake()
    channel = {
        "id": channel_id,
        "type": body.get("type", 0),
        "guild_id": guild_id,
        "name": name,
        "topic": body.get("topic"),
        "position": body.get("position", 0),
        "permission_overwrites": body.get("permission_overwrites", []),
        "nsfw": body.get("nsfw", False),
        "last_message_id": None,
        "rate_limit_per_user": body.get("rate_limit_per_user", 0),
        "parent_id": body.get("parent_id"),
        "last_pin_timestamp": None,
        "flags": 0,
    }
    state.channels[channel_id] = channel
    state.guild_channels.setdefault(guild_id, []).append(channel_id)
    return channel


@register("GET", "/guilds/{guild_id}/bans")
async def get_guild_bans(request: Request, guild_id: str, **kwargs) -> list | JSONResponse:
    try:
        _guild_or_404(guild_id)
    except Exception as e:
        return e.to_response()
    bans = state.bans.get(guild_id, {})
    return list(bans.values())


@register("GET", "/guilds/{guild_id}/bans/{user_id}")
async def get_guild_ban(request: Request, guild_id: str, user_id: str, **kwargs) -> dict | JSONResponse:
    try:
        _guild_or_404(guild_id)
    except Exception as e:
        return e.to_response()
    ban = state.bans.get(guild_id, {}).get(user_id)
    if not ban:
        return unknown_resource("Ban").to_response()
    return ban
