"""Direct HTTP endpoint tests against the digital twin."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from digitaltwin.store.state import state
from tests.conftest import BOT_HEADERS

pytestmark = pytest.mark.anyio


async def test_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v10/users/@me")
    assert resp.status_code == 401


async def test_get_current_user(client: AsyncClient):
    resp = await client.get("/api/v10/users/@me", headers=BOT_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == state.bot_user["id"]
    assert data["bot"] is True


async def test_get_gateway_bot(client: AsyncClient):
    resp = await client.get("/api/v10/gateway/bot", headers=BOT_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "url" in data
    assert "session_start_limit" in data
    assert data["shards"] == 1


async def test_guild_crud(client: AsyncClient):
    # Create guild
    resp = await client.post(
        "/api/v10/guilds",
        json={"name": "Test Guild 2"},
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    guild = resp.json()
    guild_id = guild["id"]
    assert guild["name"] == "Test Guild 2"

    # Get guild
    resp = await client.get(f"/api/v10/guilds/{guild_id}", headers=BOT_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Guild 2"

    # Modify guild
    resp = await client.patch(
        f"/api/v10/guilds/{guild_id}",
        json={"name": "Renamed"},
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"

    # Delete guild
    resp = await client.delete(f"/api/v10/guilds/{guild_id}", headers=BOT_HEADERS)
    assert resp.status_code == 204


async def test_channel_crud(client: AsyncClient):
    guild_id = list(state.guilds.keys())[0]

    # Create channel
    resp = await client.post(
        f"/api/v10/guilds/{guild_id}/channels",
        json={"name": "test-channel", "type": 0},
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    ch = resp.json()
    channel_id = ch["id"]

    # Get channel
    resp = await client.get(f"/api/v10/channels/{channel_id}", headers=BOT_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["name"] == "test-channel"

    # Modify channel
    resp = await client.patch(
        f"/api/v10/channels/{channel_id}",
        json={"name": "renamed-channel"},
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed-channel"

    # Delete channel
    resp = await client.delete(f"/api/v10/channels/{channel_id}", headers=BOT_HEADERS)
    assert resp.status_code == 200  # returns the deleted channel object


async def test_message_crud(client: AsyncClient):
    channel_id = list(state.channels.keys())[0]

    # Send message
    resp = await client.post(
        f"/api/v10/channels/{channel_id}/messages",
        json={"content": "Hello, world!"},
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    msg = resp.json()
    msg_id = msg["id"]
    assert msg["content"] == "Hello, world!"

    # Get message
    resp = await client.get(
        f"/api/v10/channels/{channel_id}/messages/{msg_id}",
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Hello, world!"

    # Edit message
    resp = await client.patch(
        f"/api/v10/channels/{channel_id}/messages/{msg_id}",
        json={"content": "Edited!"},
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Edited!"

    # Delete message
    resp = await client.delete(
        f"/api/v10/channels/{channel_id}/messages/{msg_id}",
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 204


async def test_role_crud(client: AsyncClient):
    guild_id = list(state.guilds.keys())[0]

    resp = await client.post(
        f"/api/v10/guilds/{guild_id}/roles",
        json={"name": "Moderator", "color": 0xFF0000},
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    role = resp.json()
    role_id = role["id"]
    assert role["name"] == "Moderator"

    # Modify role
    resp = await client.patch(
        f"/api/v10/guilds/{guild_id}/roles/{role_id}",
        json={"name": "Admin"},
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Admin"

    # Delete role
    resp = await client.delete(
        f"/api/v10/guilds/{guild_id}/roles/{role_id}",
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 204


async def test_member_operations(client: AsyncClient):
    guild_id = list(state.guilds.keys())[0]
    from digitaltwin.snowflake import generate_snowflake
    user_id = generate_snowflake()

    # Add member
    resp = await client.put(
        f"/api/v10/guilds/{guild_id}/members/{user_id}",
        json={"access_token": "fake"},
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    member = resp.json()
    assert member["user"]["id"] == user_id

    # Get member
    resp = await client.get(
        f"/api/v10/guilds/{guild_id}/members/{user_id}",
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200

    # Remove member
    resp = await client.delete(
        f"/api/v10/guilds/{guild_id}/members/{user_id}",
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 204


async def test_ratelimit_headers(client: AsyncClient):
    resp = await client.get("/api/v10/users/@me", headers=BOT_HEADERS)
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Bucket" in resp.headers


async def test_webhook_crud(client: AsyncClient):
    channel_id = list(state.channels.keys())[0]

    resp = await client.post(
        f"/api/v10/channels/{channel_id}/webhooks",
        json={"name": "Test Hook"},
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    wh = resp.json()
    assert wh["name"] == "Test Hook"
    wh_id = wh["id"]

    # Get webhook
    resp = await client.get(f"/api/v10/webhooks/{wh_id}", headers=BOT_HEADERS)
    assert resp.status_code == 200

    # Delete webhook
    resp = await client.delete(f"/api/v10/webhooks/{wh_id}", headers=BOT_HEADERS)
    assert resp.status_code == 204


async def test_application_commands(client: AsyncClient):
    app_id = state.bot_user["id"]

    # Create global command
    resp = await client.post(
        f"/api/v10/applications/{app_id}/commands",
        json={"name": "ping", "description": "Ping!"},
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    cmd = resp.json()
    assert cmd["name"] == "ping"

    # List global commands
    resp = await client.get(
        f"/api/v10/applications/{app_id}/commands",
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Delete command
    resp = await client.delete(
        f"/api/v10/applications/{app_id}/commands/{cmd['id']}",
        headers=BOT_HEADERS,
    )
    assert resp.status_code == 204
