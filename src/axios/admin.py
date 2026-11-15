from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from axios.bot import Axios

log = logging.getLogger(__name__)


async def _git(*args: str) -> tuple[int, str]:
    """Run a git command and return (exit code, combined output)."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode or 0, stdout.decode(errors="replace").strip()


class Admin(commands.Cog):
    def __init__(self, bot: Axios) -> None:
        self.bot = bot

    async def _restart(self, ctx: commands.Context) -> None:
        await ctx.send("Rebooting...")
        log.info("Restart requested by %s (ID: %s)", ctx.author, ctx.author.id)
        self.bot.restart_requested = True
        await self.bot.close()

    @commands.command(name="reboot")
    @commands.is_owner()
    async def reboot(self, ctx: commands.Context) -> None:
        """Restart the bot (a process supervisor must bring it back up)."""
        await self._restart(ctx)

    @commands.command(name="update")
    @commands.is_owner()
    async def update(self, ctx: commands.Context) -> None:
        """Pull the latest changes from GitHub and restart if anything changed."""
        if not self.bot.settings.enable_update_command:
            await ctx.send(
                "❌ The update command is disabled. "
                "Set ENABLE_UPDATE_COMMAND=true in `.env` to enable it."
            )
            return

        async with ctx.typing():
            _, before = await _git("rev-parse", "HEAD")
            code, output = await _git("pull", "--ff-only")
            _, after = await _git("rev-parse", "HEAD")

        await ctx.send(f"```\n{output[:1800] or '(no output)'}\n```")

        if code != 0 or before == after:
            return
        await self._restart(ctx)


async def setup(bot: Axios) -> None:
    await bot.add_cog(Admin(bot))