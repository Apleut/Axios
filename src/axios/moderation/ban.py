from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from axios.bot import Axios

log = logging.getLogger(__name__)


class Ban(commands.Cog):
    """Handles banning and unbanning members."""

    def __init__(self, bot: Axios) -> None:
        self.bot = bot


async def setup(bot: Axios) -> None:
    await bot.add_cog(Ban(bot))
