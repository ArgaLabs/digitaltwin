"""WebSocket Gateway implementing the Discord Gateway protocol.

Supports the minimum protocol needed for discord.py's client.start():
  HELLO -> IDENTIFY -> READY -> GUILD_CREATE -> heartbeat loop -> event dispatch
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

from digitaltwin.store.state import state

log = logging.getLogger(__name__)

# Discord Gateway opcodes
OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_PRESENCE = 3
OP_VOICE_STATE = 4
OP_RESUME = 6
OP_RECONNECT = 7
OP_REQUEST_MEMBERS = 8
OP_INVALIDATE_SESSION = 9
OP_HELLO = 10
OP_HEARTBEAT_ACK = 11

HEARTBEAT_INTERVAL_MS = 41250

_connected_clients: set[GatewayClient] = set()


class GatewayClient:
    """Represents a single WebSocket connection to the Gateway."""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.seq = 0
        self.session_id = uuid.uuid4().hex
        self.token: str | None = None
        self._closed = False

    def _next_seq(self) -> int:
        self.seq += 1
        return self.seq

    async def send_json(self, payload: dict) -> None:
        if not self._closed:
            try:
                await self.ws.send_text(json.dumps(payload))
            except Exception:
                self._closed = True

    async def send_dispatch(self, event_name: str, data: dict) -> None:
        await self.send_json({
            "op": OP_DISPATCH,
            "s": self._next_seq(),
            "t": event_name,
            "d": data,
        })

    async def send_hello(self) -> None:
        await self.send_json({
            "op": OP_HELLO,
            "d": {"heartbeat_interval": HEARTBEAT_INTERVAL_MS},
        })

    async def send_heartbeat_ack(self) -> None:
        await self.send_json({"op": OP_HEARTBEAT_ACK})

    async def send_ready(self, gateway_url: str) -> None:
        unavailable_guilds = [
            {"id": gid, "unavailable": True}
            for gid in state.guilds
        ]
        await self.send_dispatch("READY", {
            "v": 10,
            "user": state.bot_user,
            "guilds": unavailable_guilds,
            "session_id": self.session_id,
            "resume_gateway_url": gateway_url,
            "application": {
                "id": state.bot_user["id"],
                "flags": state.application.get("flags", 0),
            },
            "shard": [0, 1],
        })

    async def send_guild_creates(self) -> None:
        for guild_id, guild in state.guilds.items():
            payload = state.guild_create_payload(guild_id)
            if payload:
                await self.send_dispatch("GUILD_CREATE", payload)


async def gateway_ws_handler(ws: WebSocket) -> None:
    """Starlette WebSocket endpoint implementing the Discord Gateway."""
    await ws.accept()
    client = GatewayClient(ws)
    _connected_clients.add(client)

    host = ws.headers.get("host", "localhost:8080")
    gateway_url = f"ws://{host}/gateway"

    try:
        await client.send_hello()

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            op = msg.get("op")
            data = msg.get("d")

            if op == OP_HEARTBEAT:
                await client.send_heartbeat_ack()

            elif op == OP_IDENTIFY:
                client.token = data.get("token") if data else None
                await client.send_ready(gateway_url)
                await asyncio.sleep(0.05)
                await client.send_guild_creates()

            elif op == OP_RESUME:
                await client.send_hello()

            elif op == OP_REQUEST_MEMBERS:
                guild_id = str(data.get("guild_id", "")) if data else ""
                members_list = list(state.members.get(guild_id, {}).values())
                await client.send_dispatch("GUILD_MEMBERS_CHUNK", {
                    "guild_id": guild_id,
                    "members": members_list,
                    "chunk_index": 0,
                    "chunk_count": 1,
                    "not_found": [],
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.debug("Gateway connection error: %s", e)
    finally:
        client._closed = True
        _connected_clients.discard(client)


async def broadcast_event(event_name: str, data: dict) -> None:
    """Send a dispatch event to all connected Gateway clients."""
    dead: list[GatewayClient] = []
    for client in _connected_clients:
        try:
            await client.send_dispatch(event_name, data)
        except Exception:
            dead.append(client)
    for c in dead:
        c._closed = True
        _connected_clients.discard(c)
