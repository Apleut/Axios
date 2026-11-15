from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class ConfigError(Exception):
    """Raised when the environment configuration is missing or invalid."""


class Colors:
    """Embed colors, as integers (discord.Embed accepts these directly)."""

    GREEN = 0x02A100
    BLACK = 0x030303
    YELLOW = 0xFFF700
    RED = 0xFF0000


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is missing. Set it in your .env file.")
    return value


def _parse_ids(name: str) -> frozenset[int]:
    """Parse a comma-separated list of Discord IDs, e.g. '123,456'."""
    raw = os.getenv(name, "")
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            raise ConfigError(f"{name} contains a non-numeric value: {part!r}") from None
    return frozenset(ids)


def _parse_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:

    discord_token: str
    openai_api_key: str
    command_prefix: str = "$"
    # extra bot owners
    # if empty, discord.py falls back to the application's owner in the discord developer portal.
    owner_ids: frozenset[int] = frozenset()
    log_level: str = "INFO"
    # the /update-style git pull command is for development; off by default.
    enable_update_command: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()

        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in _VALID_LOG_LEVELS:
            raise ConfigError(
                f"LOG_LEVEL must be one of {sorted(_VALID_LOG_LEVELS)}, got {log_level!r}."
            )

        return cls(
            discord_token=_require("DISCORD_TOKEN"),
            openai_api_key=_require("OPENAI_API_KEY"),
            command_prefix=os.getenv("COMMAND_PREFIX", "$").strip() or "$",
            owner_ids=_parse_ids("OWNER_IDS"),
            log_level=log_level,
            enable_update_command=_parse_bool("ENABLE_UPDATE_COMMAND"),
        )