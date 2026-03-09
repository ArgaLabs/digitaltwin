"""Webhook endpoint handlers."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from digitaltwin.errors import unknown_resource
from digitaltwin.handlers.registry import register
from digitaltwin.snowflake import generate_snowflake
from digitaltwin.store.state import state


@register("POST", "/channels/{channel_id}/webhooks")
async def create_webhook(request: Request, channel_id: str, **kwargs) -> dict | JSONResponse:
    ch = state.channels.get(channel_id)
    if not ch:
        return unknown_resource("Channel").to_response()
    body = await request.json()
    wh_id = generate_snowflake()
    token = f"webhook-token-{wh_id}"
    webhook = {
        "id": wh_id,
        "type": 1,
        "guild_id": ch.get("guild_id"),
        "channel_id": channel_id,
        "user": state.bot_user,
        "name": body.get("name", "Captain Hook"),
        "avatar": body.get("avatar"),
        "token": token,
        "application_id": None,
        "url": f"https://discord.com/api/webhooks/{wh_id}/{token}",
    }
    state.webhooks[wh_id] = webhook
    return webhook


@register("GET", "/channels/{channel_id}/webhooks")
async def get_channel_webhooks(request: Request, channel_id: str, **kwargs) -> list | JSONResponse:
    if channel_id not in state.channels:
        return unknown_resource("Channel").to_response()
    return [wh for wh in state.webhooks.values() if wh["channel_id"] == channel_id]


@register("GET", "/guilds/{guild_id}/webhooks")
async def get_guild_webhooks(request: Request, guild_id: str, **kwargs) -> list | JSONResponse:
    if guild_id not in state.guilds:
        return unknown_resource("Guild").to_response()
    return [wh for wh in state.webhooks.values() if wh["guild_id"] == guild_id]


@register("GET", "/webhooks/{webhook_id}")
async def get_webhook(request: Request, webhook_id: str, **kwargs) -> dict | JSONResponse:
    wh = state.webhooks.get(webhook_id)
    if not wh:
        return unknown_resource("Webhook").to_response()
    return wh


@register("PATCH", "/webhooks/{webhook_id}")
async def modify_webhook(request: Request, webhook_id: str, **kwargs) -> dict | JSONResponse:
    wh = state.webhooks.get(webhook_id)
    if not wh:
        return unknown_resource("Webhook").to_response()
    body = await request.json()
    for key in ("name", "avatar", "channel_id"):
        if key in body:
            wh[key] = body[key]
    return wh


@register("DELETE", "/webhooks/{webhook_id}")
async def delete_webhook(request: Request, webhook_id: str, **kwargs) -> Response | JSONResponse:
    if webhook_id not in state.webhooks:
        return unknown_resource("Webhook").to_response()
    state.webhooks.pop(webhook_id)
    return Response(status_code=204)


@register("POST", "/webhooks/{webhook_id}/{webhook_token}")
async def execute_webhook(request: Request, webhook_id: str, webhook_token: str, **kwargs) -> dict | JSONResponse:
    wh = state.webhooks.get(webhook_id)
    if not wh:
        return unknown_resource("Webhook").to_response()
    body = await request.json()
    from digitaltwin.handlers.messages import _now_iso
    msg_id = generate_snowflake()
    channel_id = wh["channel_id"]
    message = {
        "id": msg_id,
        "type": 0,
        "content": body.get("content", ""),
        "channel_id": channel_id,
        "author": {
            "id": wh["id"],
            "username": body.get("username", wh["name"]),
            "discriminator": "0000",
            "avatar": body.get("avatar_url"),
            "bot": True,
        },
        "attachments": [],
        "embeds": body.get("embeds", []),
        "mentions": [],
        "mention_roles": [],
        "pinned": False,
        "mention_everyone": False,
        "tts": body.get("tts", False),
        "timestamp": _now_iso(),
        "edited_timestamp": None,
        "flags": 0,
        "webhook_id": webhook_id,
        "components": body.get("components", []),
    }
    state.messages[msg_id] = message
    state.channel_messages.setdefault(channel_id, []).append(msg_id)
    wait = request.query_params.get("wait", "false").lower() == "true"
    if wait:
        return message
    return Response(status_code=204)
