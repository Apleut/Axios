from __future__ import annotations

import re
from collections.abc import Iterable

import discord
from discord.ext import commands

# matches <@123>, <@!123>, or a bare 15 to 20 digit snowflake
ID_OR_MENTION = re.compile(r"<@!?(\d{15,20})>|\d{15,20}")


class AmbiguousUserError(commands.BadArgument):
    """Raised when a username matches more than one server member."""

    def __init__(self, argument: str) -> None:
        self.argument = argument
        typed = discord.utils.escape_mentions(argument)[:50].replace("`", "'")
        super().__init__(f"More than one member matches `{typed}`. Use their ID or a mention.")


# lowercased username, display name, and nickname
def _match_names(member: discord.Member) -> set[str]:
    names = (member.name, member.global_name, member.nick)
    return {name.casefold() for name in names if name}


# exact match only, ignoring case
def find_members_by_name(members: Iterable[discord.Member], text: str) -> list[discord.Member]:
    """Return the members whose username, display name, or nickname equals the text."""
    needle = text.lstrip("@").casefold()
    if not needle:
        return []
    return [member for member in members if needle in _match_names(member)]


class UserTarget(commands.Converter):
    """Resolve a mention, an ID, or a username to a user."""

    async def convert(self, ctx: commands.Context, argument: str) -> discord.User | discord.Member:
        # mentions and ids go through discord.py's converter, which also finds people who left
        if ID_OR_MENTION.fullmatch(argument):
            return await commands.UserConverter().convert(ctx, argument)

        # names only match members of this server
        matches = find_members_by_name(ctx.guild.members if ctx.guild else [], argument)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise AmbiguousUserError(argument)
        raise commands.UserNotFound(argument)
