"""Test injection endpoints for simulating external activity.

These are NOT part of the Discord API -- they let test code inject
messages (as arbitrary users) and raw Gateway events.
"""

from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from digitaltwin.errors import unknown_resource
from digitaltwin.gateway_ws import broadcast_event
from digitaltwin.handlers.registry import register
from digitaltwin.snowflake import generate_snowflake
from digitaltwin.store.state import state


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_user(author_data: dict) -> dict:
    """Get or create a user from the provided author data."""
    user_id = author_data.get("id") or generate_snowflake()
    existing = state.users.get(user_id)
    if existing:
        return existing
    user = {
        "id": user_id,
        "username": author_data.get("username", f"user_{user_id[:6]}"),
        "discriminator": author_data.get("discriminator", "0000"),
        "global_name": author_data.get("global_name"),
        "avatar": author_data.get("avatar"),
        "bot": author_data.get("bot", False),
        "system": False,
        "flags": 0,
        "public_flags": 0,
    }
    state.users[user_id] = user
    return user


@register("POST", "/test/inject/message")
async def inject_message(request: Request, **kwargs) -> dict | JSONResponse:
    """Create a message as an arbitrary user and broadcast MESSAGE_CREATE."""
    body = await request.json()
    channel_id = body.get("channel_id")
    if not channel_id or channel_id not in state.channels:
        return unknown_resource("Channel").to_response()

    author_data = body.get("author", {})
    author = _ensure_user(author_data)

    msg_id = generate_snowflake()
    guild_id = state.channels[channel_id].get("guild_id")

    message = {
        "id": msg_id,
        "type": 0,
        "content": body.get("content", ""),
        "channel_id": channel_id,
        "author": author,
        "attachments": [],
        "embeds": body.get("embeds", []),
        "mentions": body.get("mentions", []),
        "mention_roles": body.get("mention_roles", []),
        "pinned": False,
        "mention_everyone": body.get("mention_everyone", False),
        "tts": body.get("tts", False),
        "timestamp": _now_iso(),
        "edited_timestamp": None,
        "flags": 0,
        "components": [],
        "nonce": body.get("nonce"),
        "referenced_message": None,
    }
    if guild_id:
        message["guild_id"] = guild_id
        member = state.members.get(guild_id, {}).get(author["id"])
        if member:
            message["member"] = {
                k: v for k, v in member.items() if k != "user"
            }

    state.messages[msg_id] = message
    state.channel_messages.setdefault(channel_id, []).append(msg_id)
    state.channels[channel_id]["last_message_id"] = msg_id

    await broadcast_event("MESSAGE_CREATE", message)
    return message


@register("POST", "/test/inject/event")
async def inject_event(request: Request, **kwargs) -> Response:
    """Broadcast a raw Gateway event to all connected clients."""
    body = await request.json()
    event_name = body.get("t")
    event_data = body.get("d", {})
    if not event_name:
        return JSONResponse(
            {"code": 50035, "message": "Missing 't' (event name)"},
            status_code=400,
        )
    await broadcast_event(event_name, event_data)
    return Response(status_code=204)
