"""Shared test fixtures."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from digitaltwin.app import create_app
from digitaltwin.store.state import state


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset in-memory state before each test."""
    state.reset()
    yield
    state.reset()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


BOT_HEADERS = {"Authorization": "Bot test-token-123"}
