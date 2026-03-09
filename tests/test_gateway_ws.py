"""Tests for the WebSocket Gateway protocol."""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from digitaltwin.app import create_app
from digitaltwin.gateway_ws import _connected_clients
from digitaltwin.store.state import state
from tests.conftest import BOT_HEADERS

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _clean():
    state.reset()
    _connected_clients.clear()
    yield
    _connected_clients.clear()
    state.reset()


@pytest.fixture
def app():
    return create_app()


def test_gateway_hello_and_identify(app):
    """Connect, receive HELLO, send IDENTIFY, receive READY + GUILD_CREATE."""
    client = TestClient(app)
    with client.websocket_connect("/gateway") as ws:
        # Should receive HELLO immediately
        hello = ws.receive_json()
        assert hello["op"] == 10
        assert "heartbeat_interval" in hello["d"]

        # Send IDENTIFY
        ws.send_json({
            "op": 2,
            "d": {
                "token": "Bot fake-token",
                "intents": 513,
                "properties": {
                    "os": "linux",
                    "browser": "test",
                    "device": "test",
                },
            },
        })

        # Should receive READY (op 0, t=READY)
        ready = ws.receive_json()
        assert ready["op"] == 0
        assert ready["t"] == "READY"
        assert ready["s"] == 1
        assert ready["d"]["session_id"]
        assert ready["d"]["user"]["id"] == state.bot_user["id"]
        assert ready["d"]["user"]["bot"] is True
        assert len(ready["d"]["guilds"]) == 1
        assert ready["d"]["guilds"][0]["unavailable"] is True

        # Should receive GUILD_CREATE for the default guild
        guild_create = ws.receive_json()
        assert guild_create["op"] == 0
        assert guild_create["t"] == "GUILD_CREATE"
        assert guild_create["s"] == 2
        assert guild_create["d"]["id"] == list(state.guilds.keys())[0]
        assert guild_create["d"]["name"] == "Test Guild"
        assert guild_create["d"]["unavailable"] is False
        assert len(guild_create["d"]["channels"]) >= 1
        assert len(guild_create["d"]["members"]) >= 1


def test_heartbeat_ack(app):
    """Server responds to HEARTBEAT with HEARTBEAT_ACK."""
    client = TestClient(app)
    with client.websocket_connect("/gateway") as ws:
        ws.receive_json()  # HELLO

        ws.send_json({"op": 1, "d": None})
        ack = ws.receive_json()
        assert ack["op"] == 11


def test_gateway_url_points_to_twin(app):
    """GET /gateway/bot should return a URL pointing to the twin, not Discord."""
    sync_client = TestClient(app)
    resp = sync_client.get(
        "/api/v10/gateway/bot",
        headers={"Authorization": "Bot test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "gateway.discord.gg" not in data["url"]
    assert "/gateway" in data["url"]


def test_inject_message_broadcasts(app):
    """POST /test/inject/message creates a message and broadcasts MESSAGE_CREATE."""
    client = TestClient(app)
    channel_id = list(state.channels.keys())[0]

    with client.websocket_connect("/gateway") as ws:
        ws.receive_json()  # HELLO

        # IDENTIFY
        ws.send_json({
            "op": 2,
            "d": {"token": "Bot fake", "intents": 513, "properties": {}},
        })
        ws.receive_json()  # READY
        ws.receive_json()  # GUILD_CREATE

        # Inject a message via the HTTP endpoint
        from digitaltwin.snowflake import generate_snowflake
        user_id = generate_snowflake()
        resp = client.post(
            f"/api/v10/test/inject/message",
            json={
                "channel_id": channel_id,
                "content": "hello from a real user!",
                "author": {"id": user_id, "username": "TestUser"},
            },
            headers={"Authorization": "Bot test"},
        )
        assert resp.status_code == 200
        msg = resp.json()
        assert msg["content"] == "hello from a real user!"
        assert msg["author"]["username"] == "TestUser"

        # The Gateway client should receive MESSAGE_CREATE
        event = ws.receive_json()
        assert event["op"] == 0
        assert event["t"] == "MESSAGE_CREATE"
        assert event["d"]["content"] == "hello from a real user!"
        assert event["d"]["author"]["id"] == user_id


def test_inject_raw_event(app):
    """POST /test/inject/event broadcasts an arbitrary event."""
    client = TestClient(app)

    with client.websocket_connect("/gateway") as ws:
        ws.receive_json()  # HELLO
        ws.send_json({
            "op": 2,
            "d": {"token": "Bot fake", "intents": 513, "properties": {}},
        })
        ws.receive_json()  # READY
        ws.receive_json()  # GUILD_CREATE

        resp = client.post(
            "/api/v10/test/inject/event",
            json={
                "t": "TYPING_START",
                "d": {
                    "channel_id": list(state.channels.keys())[0],
                    "user_id": "12345",
                    "timestamp": 1234567890,
                },
            },
            headers={"Authorization": "Bot test"},
        )
        assert resp.status_code == 204

        event = ws.receive_json()
        assert event["t"] == "TYPING_START"
        assert event["d"]["user_id"] == "12345"


def test_bot_message_also_broadcasts(app):
    """When the bot sends a message via HTTP, it should also broadcast MESSAGE_CREATE."""
    client = TestClient(app)
    channel_id = list(state.channels.keys())[0]

    with client.websocket_connect("/gateway") as ws:
        ws.receive_json()  # HELLO
        ws.send_json({
            "op": 2,
            "d": {"token": "Bot fake", "intents": 513, "properties": {}},
        })
        ws.receive_json()  # READY
        ws.receive_json()  # GUILD_CREATE

        # Bot sends a message via the normal HTTP endpoint
        resp = client.post(
            f"/api/v10/channels/{channel_id}/messages",
            json={"content": "bot reply"},
            headers={"Authorization": "Bot test"},
        )
        assert resp.status_code == 200

        # Gateway should receive the MESSAGE_CREATE event
        event = ws.receive_json()
        assert event["op"] == 0
        assert event["t"] == "MESSAGE_CREATE"
        assert event["d"]["content"] == "bot reply"
        assert event["d"]["author"]["bot"] is True
