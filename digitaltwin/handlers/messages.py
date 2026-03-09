"""Message endpoint handlers."""

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


@register("POST", "/channels/{channel_id}/messages")
async def create_message(request: Request, channel_id: str, **kwargs) -> dict | JSONResponse:
    ch = state.channels.get(channel_id)
    if not ch:
        return unknown_resource("Channel").to_response()

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = {}
        if "payload_json" in form:
            import json
            body = json.loads(form["payload_json"])
        elif "content" in form:
            body["content"] = form["content"]

    msg_id = generate_snowflake()
    message = {
        "id": msg_id,
        "type": 0,
        "content": body.get("content", ""),
        "channel_id": channel_id,
        "author": state.bot_user,
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
        "components": body.get("components", []),
        "nonce": body.get("nonce"),
        "referenced_message": None,
    }
    state.messages[msg_id] = message
    state.channel_messages.setdefault(channel_id, []).append(msg_id)
    ch["last_message_id"] = msg_id

    guild_id = ch.get("guild_id")
    dispatch_msg = dict(message)
    if guild_id:
        dispatch_msg["guild_id"] = guild_id
    await broadcast_event("MESSAGE_CREATE", dispatch_msg)

    return message


@register("GET", "/channels/{channel_id}/messages")
async def get_channel_messages(request: Request, channel_id: str, **kwargs) -> list | JSONResponse:
    ch = state.channels.get(channel_id)
    if not ch:
        return unknown_resource("Channel").to_response()

    limit = int(request.query_params.get("limit", "50"))
    msg_ids = state.channel_messages.get(channel_id, [])
    recent = msg_ids[-limit:]
    return [state.messages[mid] for mid in reversed(recent) if mid in state.messages]


@register("GET", "/channels/{channel_id}/messages/{message_id}")
async def get_message(request: Request, channel_id: str, message_id: str, **kwargs) -> dict | JSONResponse:
    msg = state.messages.get(message_id)
    if not msg or msg.get("channel_id") != channel_id:
        return unknown_resource("Message").to_response()
    return msg


@register("PATCH", "/channels/{channel_id}/messages/{message_id}")
async def edit_message(request: Request, channel_id: str, message_id: str, **kwargs) -> dict | JSONResponse:
    msg = state.messages.get(message_id)
    if not msg or msg.get("channel_id") != channel_id:
        return unknown_resource("Message").to_response()
    body = await request.json()
    for key in ("content", "embeds", "flags", "components"):
        if key in body:
            msg[key] = body[key]
    msg["edited_timestamp"] = _now_iso()
    return msg


@register("DELETE", "/channels/{channel_id}/messages/{message_id}")
async def delete_message(request: Request, channel_id: str, message_id: str, **kwargs) -> Response | JSONResponse:
    msg = state.messages.get(message_id)
    if not msg or msg.get("channel_id") != channel_id:
        return unknown_resource("Message").to_response()
    state.messages.pop(message_id, None)
    ch_msgs = state.channel_messages.get(channel_id, [])
    if message_id in ch_msgs:
        ch_msgs.remove(message_id)
    return Response(status_code=204)


@register("POST", "/channels/{channel_id}/messages/bulk-delete")
async def bulk_delete_messages(request: Request, channel_id: str, **kwargs) -> Response | JSONResponse:
    ch = state.channels.get(channel_id)
    if not ch:
        return unknown_resource("Channel").to_response()
    body = await request.json()
    msg_ids = body.get("messages", [])
    ch_msgs = state.channel_messages.get(channel_id, [])
    for mid in msg_ids:
        state.messages.pop(mid, None)
        if mid in ch_msgs:
            ch_msgs.remove(mid)
    return Response(status_code=204)
