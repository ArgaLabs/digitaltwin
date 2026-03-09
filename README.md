# Discord API Digital Twin

A behavioral clone of the Discord HTTP API (v10) for local testing. All **233 endpoints** are dynamically registered from the [official OpenAPI spec](https://github.com/discord/discord-api-spec), with stateful CRUD handlers for core entities and schema-compliant mock responses for everything else.

## Why

- **High-volume testing** without hitting Discord rate limits or abuse detection
- **Dangerous failure mode testing** (mass deletes, bans, etc.) on a disposable local server
- **Deterministic** — in-memory state, no external dependencies, fully reproducible
- **discord.py compatible** — patch `Route.BASE` and your bot code works unchanged

## Quick start

```bash
# Install dependencies
uv sync --all-extras

# Start the server
uv run python main.py
# → http://localhost:8080/api/v10
```

## Using with discord.py

```python
import discord
import discord.http

# Point discord.py at the digital twin
discord.http.Route.BASE = "http://localhost:8080/api/v10"

client = discord.Client(intents=discord.Intents.default())

async def main():
    await client.login("any-token-works")
    print(client.user)  # DigitalTwinBot
    await client.close()

import asyncio
asyncio.run(main())
```

## Stateful endpoints

Full CRUD with in-memory state for:

| Entity | Operations |
|---|---|
| Users | `GET /users/@me`, `PATCH /users/@me`, `GET /users/{id}` |
| Guilds | Create, get, edit, delete, list channels/members/bans |
| Channels | Create, get, edit, delete, typing, pins |
| Messages | Send, get, edit, delete, list, bulk delete, pin/unpin |
| Roles | List, create, edit, delete, reorder |
| Members | List, get, add, edit, remove, add/remove role, ban/unban |
| Gateway | `GET /gateway/bot` stub |
| App commands | Global + guild CRUD, bulk overwrite |
| Webhooks | CRUD + execute |

All other endpoints (139 paths × methods from the spec) return schema-compliant mock responses.

## Running tests

```bash
uv run pytest tests/ -v
```

## Architecture

```
Client (discord.py)
  │  HTTP requests to localhost:8080
  ▼
Auth Middleware ─── accepts any Bot token
  │
Rate Limit Layer ── injects X-RateLimit-* headers
  │
Dynamic Router ──── 233 routes from OpenAPI spec
  │
  ├─▶ Stateful Handlers (core entities → in-memory dicts)
  └─▶ Mock Response Generator (schema-based fallback)
```

## Project structure

```
digitaltwin/
  app.py              # FastAPI app + dynamic route registration
  config.py           # API version, port, Discord epoch
  snowflake.py        # Discord snowflake ID generator
  auth.py             # Bot token auth middleware
  ratelimit.py        # Rate limit header injection
  errors.py           # Discord error response format
  mock.py             # Schema-based mock response generator
  spec_loader.py      # OpenAPI spec parser
  models/
    generated.py      # 5,000+ lines of Pydantic models (auto-generated)
  store/
    state.py          # Global state container with seed data
  handlers/
    registry.py       # Handler dispatch registry
    users.py          # User + application handlers
    guilds.py         # Guild CRUD
    channels.py       # Channel CRUD
    messages.py       # Message CRUD
    roles.py          # Role CRUD
    members.py        # Member + ban handlers
    gateway.py        # Gateway stubs
    interactions.py   # Application command handlers
    webhooks.py       # Webhook CRUD + execute
specs/
  openapi.json        # Discord API OpenAPI spec (v10)
tests/
  test_api.py                # Direct HTTP endpoint tests
  test_discordpy_compat.py   # discord.py client compatibility tests
```
