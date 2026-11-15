from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from axios.bot import Axios

log = logging.getLogger(__name__)


# role hierarchy check
def outranks(actor: discord.Member, target: discord.Member) -> bool:
    """Check whether the actor outranks the target."""
    if actor.id == actor.guild.owner_id:
        return True
    return actor.top_role > target.top_role


class Ban(commands.Cog):
    """Handles banning members."""

    def __init__(self, bot: Axios) -> None:
        self.bot = bot

    @commands.command(name="ban", aliases=["b", "banish"])
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)  # what the invoker needs
    @commands.bot_has_permissions(ban_members=True)  # what the bot needs
    async def ban(
        self, ctx: commands.Context, member: discord.Member, *, reason: str | None = None
    ) -> None:
        """Ban a member from the server. Usage: ban <member> [reason]"""
        # refuse targets that can never be banned
        if member == ctx.author:
            await ctx.send("❌ You can't ban yourself.")
            return
        if member == ctx.guild.me:
            await ctx.send("❌ I won't ban myself.")
            return
        if member.id == ctx.guild.owner_id:
            await ctx.send("❌ The server owner can't be banned.")
            return

        # role hierarchy checks for the moderator and for the bot
        if not outranks(ctx.author, member):
            await ctx.send("❌ You can't ban someone with an equal or higher role than yours.")
            return
        if member.top_role >= ctx.guild.me.top_role:
            await ctx.send("❌ I can't ban someone with an equal or higher role than mine.")
            return

        # include command author in audit log reason
        audit_reason = f"{ctx.author} (ID: {ctx.author.id}): {reason or 'No reason provided.'}"
        try:
            await member.ban(reason=audit_reason[:512])
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to ban this member.")
        except discord.HTTPException as exc:
            log.warning("Failed to ban %s in guild %s: %s", member.id, ctx.guild.id, exc)
            await ctx.send(f"❌ Failed to ban member: {exc}")
        else:
            log.info("%s banned %s in guild %s: %s", ctx.author.id, member.id, ctx.guild.id, reason)
            await ctx.send(f"{member.mention} has been banned.")


async def setup(bot: Axios) -> None:
    await bot.add_cog(Ban(bot))
