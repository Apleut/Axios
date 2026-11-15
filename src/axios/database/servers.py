from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from axios.config import ConfigError

log = logging.getLogger(__name__)

DEFAULT_PATH = Path("data/servers.json")


# settings for one server
# extra keys are rejected so a typo in a hand-edited file is an error, not silently ignored
class ServerSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mod_log_channel_id: int | None = None


# the whole servers.json file
# schema_version lets a future format change be detected instead of misread
class ServerFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    servers: dict[int, ServerSettings] = Field(default_factory=dict)


# atomic write
# write a temp file, then swap it in, so a crash mid-write can't leave a half-written file
def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


class ServerStore:
    """Reads and writes per-server settings in a human-editable JSON file."""

    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self.path = path
        self._data = ServerFile()
        self._mtime: int | None = None
        self._lock = asyncio.Lock()

    def _parse(self, text: str) -> ServerFile:
        # a blank file counts as empty, so a freshly created file works
        if not text.strip():
            return ServerFile()
        try:
            return ServerFile.model_validate_json(text)
        except ValidationError as exc:
            raise ConfigError(f"{self.path} is invalid:\n{exc}") from exc

    def load(self) -> None:
        """Load the file at startup. Raises ConfigError if it is invalid."""
        # relative paths depend on where the bot was launched, so log exactly which file is used
        log.info("Using the server settings file %s", self.path.resolve())
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._data = ServerFile()
            self._mtime = None
            return
        self._data = self._parse(text)
        self._mtime = self.path.stat().st_mtime_ns

    # hand-edit pickup
    # while running, a bad edit keeps the last good settings and logs the error instead of crashing
    def _reload_if_changed(self) -> None:
        try:
            mtime: int | None = self.path.stat().st_mtime_ns
        except FileNotFoundError:
            mtime = None
        if mtime == self._mtime:
            return

        # remember the new mtime first, so a broken file is reported once, not on every lookup
        self._mtime = mtime
        if mtime is None:
            self._data = ServerFile()
            return
        try:
            self._data = self._parse(self.path.read_text(encoding="utf-8"))
        except ConfigError as exc:
            log.error(
                "Ignoring the change to %s and keeping the last good settings: %s", self.path, exc
            )

    def get(self, guild_id: int) -> ServerSettings:
        """Return a server's settings, or the defaults if it has none saved."""
        self._reload_if_changed()
        return self._data.servers.get(guild_id, ServerSettings())

    async def mod_log_channel(self, guild_id: int) -> int | None:
        """Return the mod log channel for a server. Matches ModLogger's channel lookup."""
        return self.get(guild_id).mod_log_channel_id

    async def update(self, guild_id: int, **changes: object) -> ServerSettings:
        """Change some of a server's settings and save. Raises ValidationError if invalid."""
        async with self._lock:
            # pick up any hand edits first, so saving never overwrites them
            self._reload_if_changed()

            current = self._data.servers.get(guild_id, ServerSettings())
            updated = ServerSettings.model_validate({**current.model_dump(), **changes})
            new_data = self._data.model_copy(
                update={"servers": {**self._data.servers, guild_id: updated}}
            )

            text = new_data.model_dump_json(indent=2) + "\n"
            await asyncio.to_thread(_write_atomic, self.path, text)

            self._data = new_data
            self._mtime = self.path.stat().st_mtime_ns
            return updated
