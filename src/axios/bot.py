from __future__ import annotations

import asyncio
import logging
import sys

import discord
from discord.ext import commands

from axios.config import Colors, ConfigError, Settings

log = logging.getLogger("axios")

EXTENSIONS: tuple[str, ...] = (
    "axios.admin",
    "axios.moderation.ban",
)

# exit code meaning "restart me"
# direct docker, systemd, or a launcher script to restart the bot if it exits with this code
RESTART_EXIT_CODE = 3


class Axios(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(settings.command_prefix),
            intents=intents,
            help_command=None,
            owner_ids=set(settings.owner_ids),
        )
        self.settings = settings
        self.restart_requested = False

    async def setup_hook(self) -> None:
        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                log.info("Loaded extension %s", extension)
            except Exception:
                log.exception("Failed to load extension %s", extension)

    async def on_ready(self) -> None:
        # may fire more than once (reconnects), so keep this idempotent
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        await self._update_presence()

    async def on_guild_join(self, guild: discord.Guild) -> None:
        log.info("Joined guild %s (ID: %s)", guild.name, guild.id)
        await self._update_presence()

        embed = discord.Embed(
            title="👋 Thanks for adding Axios to your server!",
            description="Placeholder",  # TODO: add setup instructions
            color=Colors.GREEN,
        )
        try:
            owner = guild.owner or await self.fetch_user(guild.owner_id)
            await owner.send(embed=embed)
        except discord.HTTPException as exc:
            log.warning("Could not DM the owner of guild %s: %s", guild.id, exc)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        log.info("Removed from guild %s (ID: %s)", guild.name, guild.id)
        await self._update_presence()

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        # ignore unknown commands so typos don't spam the channel
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ Only the bot owner can use this command.")
            return
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("❌ This command can only be used in a server.")
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to do that.")
            return
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ Axios doesn't have permission to do that.")
            return
        # missing argument
        if isinstance(error, commands.MissingRequiredArgument):
            usage = f"{ctx.clean_prefix}{ctx.command.qualified_name} {ctx.command.signature}"
            await ctx.send(f"❌ Missing required argument `{error.param.name}`.\nUsage: `{usage}`")
            return

        # member lookup failed
        if isinstance(error, (commands.MemberNotFound, commands.UserNotFound)):
            typed = discord.utils.escape_mentions(error.argument)[:50]
            await ctx.send(f"❌ Couldn't find user `{typed}`.")
            return

        # any other bad argument
        if isinstance(error, commands.BadArgument):
            usage = f"{ctx.clean_prefix}{ctx.command.qualified_name} {ctx.command.signature}"
            await ctx.send(f"❌ One of the arguments wasn't valid.\nUsage: `{usage}`")
            return
        # anything else is unexpected, so log it with the full traceback
        log.error("Unhandled error in command %s", ctx.command, exc_info=error)

    async def _update_presence(self) -> None:
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(self.guilds)} servers",
        )
        await self.change_presence(status=discord.Status.online, activity=activity)


async def _run(settings: Settings) -> bool:
    """Run the bot until it stops. Returns True if a restart was requested."""
    bot = Axios(settings)
    async with bot:
        await bot.start(settings.discord_token)
    return bot.restart_requested


def main() -> None:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        sys.exit(f"Configuration error: {exc}")

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    try:
        restart = asyncio.run(_run(settings))
    except discord.LoginFailure:
        sys.exit("Login failed: DISCORD_TOKEN is invalid.")
    except discord.PrivilegedIntentsRequired:
        sys.exit(
            "Privileged intents are not enabled. Turn on Message Content and "
            "Server Members intents in the Discord Developer Portal."
        )
    except KeyboardInterrupt:
        log.info("Stopped by keyboard interrupt.")
        return

    if restart:
        log.info("Restart requested; exiting with code %d.", RESTART_EXIT_CODE)
        sys.exit(RESTART_EXIT_CODE)
