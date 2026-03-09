"""Channel endpoint handlers."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from digitaltwin.errors import unknown_resource
from digitaltwin.handlers.registry import register
from digitaltwin.store.state import state


def _channel_or_404(channel_id: str):
    ch = state.channels.get(channel_id)
    if not ch:
        raise unknown_resource("Channel")
    return ch


@register("GET", "/channels/{channel_id}")
async def get_channel(request: Request, channel_id: str, **kwargs) -> dict | JSONResponse:
    try:
        return _channel_or_404(channel_id)
    except Exception as e:
        return e.to_response()


@register("PATCH", "/channels/{channel_id}")
async def modify_channel(request: Request, channel_id: str, **kwargs) -> dict | JSONResponse:
    try:
        ch = _channel_or_404(channel_id)
    except Exception as e:
        return e.to_response()
    body = await request.json()
    for key in ("name", "topic", "position", "nsfw", "rate_limit_per_user",
                "parent_id", "permission_overwrites", "type"):
        if key in body:
            ch[key] = body[key]
    return ch


@register("DELETE", "/channels/{channel_id}")
async def delete_channel(request: Request, channel_id: str, **kwargs) -> Response | JSONResponse:
    try:
        ch = _channel_or_404(channel_id)
    except Exception as e:
        return e.to_response()
    guild_id = ch.get("guild_id")
    if guild_id and guild_id in state.guild_channels:
        chans = state.guild_channels[guild_id]
        if channel_id in chans:
            chans.remove(channel_id)
    state.channels.pop(channel_id, None)
    return ch


@register("POST", "/channels/{channel_id}/typing")
async def trigger_typing(request: Request, channel_id: str, **kwargs) -> Response:
    return Response(status_code=204)


@register("GET", "/channels/{channel_id}/pins")
async def get_pinned_messages(request: Request, channel_id: str, **kwargs) -> list | JSONResponse:
    try:
        _channel_or_404(channel_id)
    except Exception as e:
        return e.to_response()
    pin_ids = state.pins.get(channel_id, [])
    return [state.messages[mid] for mid in pin_ids if mid in state.messages]


@register("PUT", "/channels/{channel_id}/pins/{message_id}")
async def pin_message(request: Request, channel_id: str, message_id: str, **kwargs) -> Response | JSONResponse:
    try:
        _channel_or_404(channel_id)
    except Exception as e:
        return e.to_response()
    if message_id not in state.messages:
        return unknown_resource("Message").to_response()
    state.pins.setdefault(channel_id, [])
    if message_id not in state.pins[channel_id]:
        state.pins[channel_id].append(message_id)
        state.messages[message_id]["pinned"] = True
    return Response(status_code=204)


@register("DELETE", "/channels/{channel_id}/pins/{message_id}")
async def unpin_message(request: Request, channel_id: str, message_id: str, **kwargs) -> Response | JSONResponse:
    try:
        _channel_or_404(channel_id)
    except Exception as e:
        return e.to_response()
    pins = state.pins.get(channel_id, [])
    if message_id in pins:
        pins.remove(message_id)
        if message_id in state.messages:
            state.messages[message_id]["pinned"] = False
    return Response(status_code=204)


@register("GET", "/channels/{channel_id}/invites")
async def get_channel_invites(request: Request, channel_id: str, **kwargs) -> list | JSONResponse:
    try:
        _channel_or_404(channel_id)
    except Exception as e:
        return e.to_response()
    return []
