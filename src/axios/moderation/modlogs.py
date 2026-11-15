from __future__ import annotations

import enum
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord

from axios.config import Colors

if TYPE_CHECKING:
    from axios.bot import Axios

log = logging.getLogger(__name__)

# returns the log channel id for a guild, or None when no channel is set up
ChannelLookup = Callable[[int], Awaitable[int | None]]

# shown as the actor when axios acts on its own
AUTOMATIC_ACTOR = "Axios (automatic)"

# discord's embed limits
MAX_DESCRIPTION = 4000
MAX_FIELD_NAME = 256
MAX_FIELD_VALUE = 1024


# the kinds of moderation events that get logged
# the value is the embed title
class LogType(enum.Enum):
    BAN = "Member banned"
    UNBAN = "Member unbanned"
    KICK = "Member kicked"
    TIMEOUT = "Member timed out"
    WARN = "Member warned"


# embed color per log type
LOG_COLORS: dict[LogType, int] = {
    LogType.BAN: Colors.RED,
    LogType.UNBAN: Colors.GREEN,
    LogType.KICK: Colors.RED,
    LogType.TIMEOUT: Colors.YELLOW,
    LogType.WARN: Colors.YELLOW,
}


# this is the record the database layer should store later for the audit trail
@dataclass(frozen=True)
class ModLogEntry:
    log_type: LogType
    guild_id: int
    actor: discord.abc.User | None = None
    target: discord.abc.User | None = None
    description: str | None = None
    fields: Mapping[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# username in code style plus the id
# no mentions to avoid ghost pings
def describe_user(user: discord.abc.User) -> str:
    return f"`{user}` (ID: {user.id})"


# every moderation log is built here so they all look the same
def build_embed(entry: ModLogEntry) -> discord.Embed:
    """Build the embed for a moderation log entry."""
    embed = discord.Embed(
        title=entry.log_type.value,
        description=(entry.description or "No reason provided.")[:MAX_DESCRIPTION],
        color=LOG_COLORS[entry.log_type],
        timestamp=entry.created_at,
    )
    actor = AUTOMATIC_ACTOR if entry.actor is None else describe_user(entry.actor)
    embed.add_field(name="Actor", value=actor, inline=True)
    if entry.target is not None:
        embed.add_field(name="Target", value=describe_user(entry.target), inline=True)
    for name, value in entry.fields.items():
        embed.add_field(name=name[:MAX_FIELD_NAME], value=value[:MAX_FIELD_VALUE], inline=False)
    embed.set_footer(text="Axios moderation log")
    return embed


# for the python logger, so console logs are uniform too
def format_log_line(entry: ModLogEntry) -> str:
    """Build the single console line for a moderation log entry."""
    actor = "axios" if entry.actor is None else str(entry.actor.id)
    parts = [f"type={entry.log_type.name}", f"guild={entry.guild_id}", f"actor={actor}"]
    if entry.target is not None:
        parts.append(f"target={entry.target.id}")
    if entry.description:
        parts.append(f"reason={entry.description!r}")
    return " ".join(parts)


class ModLogger:
    """Sends uniform moderation logs to the console and to each server's log channel."""

    def __init__(self, bot: Axios, channel_lookup: ChannelLookup | None = None) -> None:
        self.bot = bot
        # TODO: replace the in-memory channels with the database layer once it exists
        self._channels: dict[int, int] = {}
        self._channel_lookup = channel_lookup or self._memory_lookup

    # in-memory lookup
    # the default until a database-backed lookup is passed in
    async def _memory_lookup(self, guild_id: int) -> int | None:
        return self._channels.get(guild_id)

    def set_channel(self, guild_id: int, channel_id: int | None) -> None:
        """Set, or clear with None, the log channel for a guild."""
        if channel_id is None:
            self._channels.pop(guild_id, None)
        else:
            self._channels[guild_id] = channel_id

    async def send_log(
        self,
        log_type: LogType,
        *,
        guild: discord.Guild,
        actor: discord.abc.User | None = None,
        target: discord.abc.User | None = None,
        description: str | None = None,
        fields: Mapping[str, str] | None = None,
    ) -> None:
        """Log a moderation event. This never raises, so a logging problem can't break an action."""
        entry = ModLogEntry(
            log_type=log_type,
            guild_id=guild.id,
            actor=actor,
            target=target,
            description=description,
            fields=fields or {},
        )

        log.info("mod log: %s", format_log_line(entry))

        channel_id = await self._channel_lookup(guild.id)
        if channel_id is None:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            log.warning(
                "Log channel %s in guild %s is missing or not a text channel.", channel_id, guild.id
            )
            return

        try:
            await channel.send(
                embed=build_embed(entry),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException as exc:
            log.warning(
                "Could not send a mod log to channel %s in guild %s: %s", channel_id, guild.id, exc
            )
