from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from axios.bot import Axios

log = logging.getLogger(__name__)


class Example(commands.Cog):
    """<One-line description of this cog.>"""

    def __init__(self, bot: Axios) -> None:
        self.bot = bot

    @commands.command(name="example")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)  # what the invoker needs
    @commands.bot_has_permissions(manage_messages=True)  # what the bot needs
    async def example(self, ctx: commands.Context, member: discord.Member) -> None:
        """<Shown to users: what the command does and how to use it.>"""
        # TODO: implement
        await ctx.send(f"Example command for {member.mention}.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        # TODO: react to the message


async def setup(bot: Axios) -> None:
    await bot.add_cog(Example(bot))
