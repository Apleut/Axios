from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from axios.moderation.converters import UserTarget
from axios.moderation.modlogs import LogType

if TYPE_CHECKING:
    from axios.bot import Axios

log = logging.getLogger(__name__)


# role hierarchy check
def outranks(actor: discord.Member, target: discord.Member) -> bool:
    """Check whether the actor outranks the target."""
    if actor.id == actor.guild.owner_id:
        return True
    return actor.top_role > target.top_role


# audit log reason
# includes the moderator so the audit log shows who ran the command
def build_audit_reason(moderator: discord.abc.User, reason: str | None) -> str:
    """Build the audit log reason for a moderation action."""
    text = f"{moderator} (ID: {moderator.id}): {reason or 'No reason provided.'}"
    return text[:512]


class Ban(commands.Cog):
    """Handles banning and unbanning users."""

    def __init__(self, bot: Axios) -> None:
        self.bot = bot

    @commands.command(name="ban", aliases=["b", "banish"])
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)  # what the invoker needs
    @commands.bot_has_permissions(ban_members=True)  # what the bot needs
    async def ban(
        self, ctx: commands.Context, user: UserTarget, *, reason: str | None = None
    ) -> None:
        """Ban a user from the server, even if they have left.

        Usage: ban <mention, ID, or username> [reason]. Quote usernames that contain spaces.
        Use an ID for people who have left, since usernames only match current members.
        """
        # refuse targets that can never be banned
        if user.id == ctx.author.id:
            await ctx.send("❌ You can't ban yourself.")
            return
        if user.id == ctx.guild.me.id:
            await ctx.send("❌ Well, that's rather rude.")
            return
        if user.id == ctx.guild.owner_id:
            await ctx.send("❌ The server owner can't be banned.")
            return

        # role checks if they're in the server
        member = ctx.guild.get_member(user.id)
        if member is not None:
            if not outranks(ctx.author, member):
                await ctx.send("❌ You can't ban someone with an equal or higher role than yours.")
                return
            if member.top_role >= ctx.guild.me.top_role:
                await ctx.send("❌ I can't ban someone with an equal or higher role than mine.")
                return

        try:
            await ctx.guild.ban(user, reason=build_audit_reason(ctx.author, reason))
        except discord.Forbidden:
            await ctx.send("❌ Axios doesn't have permission to ban this user.")
        except discord.HTTPException as exc:
            log.warning("Failed to ban %s in guild %s: %s", user.id, ctx.guild.id, exc)
            await ctx.send(f"❌ Failed to ban user: {exc}")
        else:
            await self.bot.modlogs.send_log(
                LogType.BAN,
                guild=ctx.guild,
                actor=ctx.author,
                target=user,
                description=reason,
            )
            await ctx.send(f"Banned `{user}` (ID: {user.id}).")

    @commands.command(name="unban", aliases=["ub", "pardon"])
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)  # what the invoker needs
    @commands.bot_has_permissions(ban_members=True)  # what the bot needs
    async def unban(
        self, ctx: commands.Context, user: discord.User, *, reason: str | None = None
    ) -> None:
        """Unban a user from the server. Usage: unban <user ID> [reason]"""
        try:
            await ctx.guild.unban(user, reason=build_audit_reason(ctx.author, reason))
        except discord.NotFound:
            await ctx.send("❌ That user isn't banned.")
        except discord.Forbidden:
            await ctx.send("❌ Axios doesn't have permission to unban this user.")
        except discord.HTTPException as exc:
            log.warning("Failed to unban %s in guild %s: %s", user.id, ctx.guild.id, exc)
            await ctx.send(f"❌ Failed to unban user: {exc}")
        else:
            await self.bot.modlogs.send_log(
                LogType.UNBAN,
                guild=ctx.guild,
                actor=ctx.author,
                target=user,
                description=reason,
            )
            await ctx.send(f"Unbanned `{user}` (ID: {user.id}).")


async def setup(bot: Axios) -> None:
    await bot.add_cog(Ban(bot))
