"""Global in-memory state container with seed data."""

from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
from typing import Any

from digitaltwin.snowflake import generate_snowflake

_BOT_USER_ID = generate_snowflake()
_DEFAULT_GUILD_ID = generate_snowflake()
_DEFAULT_CHANNEL_ID = generate_snowflake()
_EVERYONE_ROLE_ID = _DEFAULT_GUILD_ID  # @everyone role ID == guild ID


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_bot_user() -> dict:
    return {
        "id": _BOT_USER_ID,
        "username": "DigitalTwinBot",
        "discriminator": "0001",
        "global_name": "DigitalTwinBot",
        "avatar": None,
        "bot": True,
        "system": False,
        "mfa_enabled": False,
        "banner": None,
        "accent_color": None,
        "locale": "en-US",
        "verified": True,
        "email": None,
        "flags": 0,
        "premium_type": 0,
        "public_flags": 0,
    }


def _make_default_guild() -> dict:
    return {
        "id": _DEFAULT_GUILD_ID,
        "name": "Test Guild",
        "icon": None,
        "icon_hash": None,
        "splash": None,
        "discovery_splash": None,
        "owner": True,
        "owner_id": _BOT_USER_ID,
        "permissions": "2147483647",
        "region": "us-west",
        "afk_channel_id": None,
        "afk_timeout": 300,
        "widget_enabled": False,
        "widget_channel_id": None,
        "verification_level": 0,
        "default_message_notifications": 0,
        "explicit_content_filter": 0,
        "roles": [
            {
                "id": _EVERYONE_ROLE_ID,
                "name": "@everyone",
                "color": 0,
                "hoist": False,
                "icon": None,
                "unicode_emoji": None,
                "position": 0,
                "permissions": "1071698660929",
                "managed": False,
                "mentionable": False,
                "flags": 0,
            }
        ],
        "emojis": [],
        "features": [],
        "mfa_level": 0,
        "application_id": None,
        "system_channel_id": None,
        "system_channel_flags": 0,
        "rules_channel_id": None,
        "max_presences": None,
        "max_members": 500000,
        "vanity_url_code": None,
        "description": None,
        "banner": None,
        "premium_tier": 0,
        "premium_subscription_count": 0,
        "preferred_locale": "en-US",
        "public_updates_channel_id": None,
        "max_video_channel_users": 25,
        "max_stage_video_channel_users": 50,
        "approximate_member_count": 1,
        "approximate_presence_count": 1,
        "nsfw_level": 0,
        "stickers": [],
        "premium_progress_bar_enabled": False,
        "safety_alerts_channel_id": None,
        "channels": [],
        "threads": [],
        "members": [],
    }


def _make_default_channel() -> dict:
    return {
        "id": _DEFAULT_CHANNEL_ID,
        "type": 0,  # GUILD_TEXT
        "guild_id": _DEFAULT_GUILD_ID,
        "name": "general",
        "topic": None,
        "position": 0,
        "permission_overwrites": [],
        "nsfw": False,
        "last_message_id": None,
        "rate_limit_per_user": 0,
        "parent_id": None,
        "last_pin_timestamp": None,
        "flags": 0,
    }


def _make_application() -> dict:
    return {
        "id": _BOT_USER_ID,
        "name": "DigitalTwinBot",
        "icon": None,
        "description": "Digital Twin test application",
        "bot_public": True,
        "bot_require_code_grant": False,
        "flags": 0,
        "approximate_guild_count": 1,
        "interactions_endpoint_url": None,
        "redirect_uris": [],
        "tags": [],
    }


class State:
    """In-memory store for all Discord entities."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        bot_user = _make_bot_user()
        default_guild = _make_default_guild()
        default_channel = _make_default_channel()

        self.bot_user: dict = bot_user
        self.application: dict = _make_application()

        self.users: dict[str, dict] = {bot_user["id"]: bot_user}
        self.guilds: dict[str, dict] = {default_guild["id"]: default_guild}
        self.channels: dict[str, dict] = {default_channel["id"]: default_channel}
        self.messages: dict[str, dict] = {}
        self.roles: dict[str, dict] = {
            _EVERYONE_ROLE_ID: default_guild["roles"][0]
        }
        self.members: dict[str, dict[str, dict]] = {
            default_guild["id"]: {
                bot_user["id"]: {
                    "user": bot_user,
                    "nick": None,
                    "avatar": None,
                    "roles": [],
                    "joined_at": _now_iso(),
                    "premium_since": None,
                    "deaf": False,
                    "mute": False,
                    "flags": 0,
                    "pending": False,
                    "communication_disabled_until": None,
                }
            }
        }

        # guild_id -> channel_id -> [message_id]
        self.guild_channels: dict[str, list[str]] = {
            default_guild["id"]: [default_channel["id"]]
        }

        self.pins: dict[str, list[str]] = {}

        self.bans: dict[str, dict[str, dict]] = {}

        # Application commands: guild_id|"global" -> command_id -> command
        self.application_commands: dict[str, dict[str, dict]] = {"global": {}}

        # Webhooks: webhook_id -> webhook
        self.webhooks: dict[str, dict] = {}

        # channel_id -> [message_ids] ordered by time
        self.channel_messages: dict[str, list[str]] = {}

    def guild_create_payload(self, guild_id: str) -> dict | None:
        """Build a full GUILD_CREATE event payload for the Gateway."""
        guild = self.guilds.get(guild_id)
        if not guild:
            return None
        channel_ids = self.guild_channels.get(guild_id, [])
        channels = [self.channels[cid] for cid in channel_ids if cid in self.channels]
        members_map = self.members.get(guild_id, {})
        members = list(members_map.values())
        payload = dict(guild)
        payload.update({
            "channels": channels,
            "members": members,
            "voice_states": [],
            "presences": [],
            "stage_instances": [],
            "guild_scheduled_events": [],
            "threads": guild.get("threads", []),
            "unavailable": False,
            "joined_at": _now_iso(),
            "large": len(members) > 250,
            "member_count": len(members),
        })
        return payload


state = State()
