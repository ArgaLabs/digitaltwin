"""discord.py compatibility tests.

These tests patch discord.py's base URL to hit our digital twin and verify
that core client operations work correctly.
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest
import uvicorn

from digitaltwin.app import create_app
from digitaltwin.store.state import state

pytestmark = pytest.mark.anyio

_PORT = 58321  # ephemeral port for testing


@pytest.fixture(scope="module")
def twin_server():
    """Start the digital twin server in a background thread."""
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=_PORT, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to be ready
    import httpx
    for _ in range(50):
        try:
            r = httpx.get(f"http://127.0.0.1:{_PORT}/api/v10/gateway", headers={"Authorization": "Bot test"})
            if r.status_code == 200:
                break
        except httpx.ConnectError:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError("Twin server failed to start")

    yield

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _reset():
    state.reset()


def _patch_discord():
    """Patch discord.py to point at the twin server."""
    import discord
    import discord.http
    import yarl
    from discord.gateway import DiscordWebSocket

    discord.http.Route.BASE = f"http://127.0.0.1:{_PORT}/api/v10"
    DiscordWebSocket.DEFAULT_GATEWAY = yarl.URL(f"ws://127.0.0.1:{_PORT}/gateway")


async def test_login(twin_server):
    """discord.py Client.login() calls GET /users/@me -- verify it works."""
    import discord

    _patch_discord()

    client = discord.Client(intents=discord.Intents.default())
    await client.login("fake-bot-token")

    assert client.user is not None
    assert client.user.bot is True
    assert client.user.name == state.bot_user["username"]

    await client.close()


async def test_fetch_guild(twin_server):
    import discord

    _patch_discord()

    client = discord.Client(intents=discord.Intents.default())
    await client.login("fake-bot-token")

    guild_id = int(list(state.guilds.keys())[0])
    guild = await client.fetch_guild(guild_id)
    assert guild.name == "Test Guild"

    await client.close()


async def test_fetch_channel(twin_server):
    import discord

    _patch_discord()

    client = discord.Client(intents=discord.Intents.default())
    await client.login("fake-bot-token")

    channel_id = int(list(state.channels.keys())[0])
    channel = await client.fetch_channel(channel_id)
    assert channel.name == "general"

    await client.close()


async def test_start_and_on_ready(twin_server):
    """client.start() connects to the Gateway, receives READY + GUILD_CREATE,
    and fires on_ready."""
    import discord

    _patch_discord()

    ready_event = asyncio.Event()

    class TestClient(discord.Client):
        async def on_ready(self):
            ready_event.set()

    client = TestClient(intents=discord.Intents.all())
    task = asyncio.create_task(client.start("fake-bot-token"))

    try:
        await asyncio.wait_for(ready_event.wait(), timeout=15)

        assert client.user is not None
        assert client.user.bot is True
        assert len(client.guilds) == 1

        guild = list(client.guilds)[0]
        assert guild.name == "Test Guild"
    finally:
        await client.close()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def test_on_message_from_injected(twin_server):
    """Inject a message via /test/inject/message and verify discord.py's
    on_message fires with the correct content."""
    import discord
    import httpx

    _patch_discord()

    ready_event = asyncio.Event()
    message_event = asyncio.Event()
    received_messages: list[discord.Message] = []

    class TestClient(discord.Client):
        async def on_ready(self):
            ready_event.set()

        async def on_message(self, message: discord.Message):
            received_messages.append(message)
            message_event.set()

    client = TestClient(intents=discord.Intents.all())
    task = asyncio.create_task(client.start("fake-bot-token"))

    try:
        await asyncio.wait_for(ready_event.wait(), timeout=15)

        channel_id = list(state.channels.keys())[0]
        from digitaltwin.snowflake import generate_snowflake
        user_id = generate_snowflake()

        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"http://127.0.0.1:{_PORT}/api/v10/test/inject/message",
                json={
                    "channel_id": channel_id,
                    "content": "hey @argabot what is Python?",
                    "author": {"id": user_id, "username": "RealUser"},
                },
                headers={"Authorization": "Bot test"},
            )
            assert resp.status_code == 200

        await asyncio.wait_for(message_event.wait(), timeout=10)

        assert len(received_messages) == 1
        msg = received_messages[0]
        assert msg.content == "hey @argabot what is Python?"
        assert msg.author.name == "RealUser"
        assert msg.author.id == int(user_id)
        assert msg.channel.id == int(channel_id)
    finally:
        await client.close()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
