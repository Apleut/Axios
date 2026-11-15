from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from axios.config import Colors
from axios.moderation.modlogs import (
    AUTOMATIC_ACTOR,
    LogType,
    ModLogEntry,
    ModLogger,
    build_embed,
    format_log_line,
)


# stand-in user whose string form is a username, like a real discord user
class FakeUser:
    def __init__(self, user_id: int, name: str) -> None:
        self.id = user_id
        self.name = name

    def __str__(self) -> str:
        return self.name


# stand-in guild that returns the given channel for any id
def make_guild(channel=None) -> SimpleNamespace:
    return SimpleNamespace(id=1, get_channel=MagicMock(return_value=channel))


# text channel mock that passes isinstance checks and records what it sends
def make_channel() -> MagicMock:
    channel = MagicMock(spec=discord.TextChannel)
    channel.send = AsyncMock()
    return channel


def make_entry(**overrides) -> ModLogEntry:
    values = {
        "log_type": LogType.BAN,
        "guild_id": 1,
        "actor": FakeUser(10, "mod"),
        "target": FakeUser(20, "spammer"),
        "description": "spam",
    }
    values.update(overrides)
    return ModLogEntry(**values)


def fields_of(embed: discord.Embed) -> dict[str, str]:
    return {field.name: field.value for field in embed.fields}


def test_embed_shows_type_color_actor_target_and_reason():
    embed = build_embed(make_entry())

    assert embed.title == LogType.BAN.value
    assert embed.description == "spam"
    assert embed.color.value == Colors.RED
    assert fields_of(embed) == {"Actor": "`mod` (ID: 10)", "Target": "`spammer` (ID: 20)"}


def test_embed_attributes_automatic_actions_to_axios():
    embed = build_embed(make_entry(actor=None))

    assert fields_of(embed)["Actor"] == AUTOMATIC_ACTOR


def test_embed_omits_the_target_field_when_there_is_no_target():
    embed = build_embed(make_entry(target=None))

    assert "Target" not in fields_of(embed)


def test_embed_has_a_default_reason():
    embed = build_embed(make_entry(description=None))

    assert embed.description == "No reason provided."


def test_embed_includes_extra_fields_and_respects_discords_limits():
    embed = build_embed(make_entry(description="x" * 5000, fields={"Note": "y" * 2000}))

    assert len(embed.description) == 4000
    assert len(fields_of(embed)["Note"]) == 1024


def test_console_line_uses_one_key_value_format():
    line = format_log_line(make_entry())

    assert line == "type=BAN guild=1 actor=10 target=20 reason='spam'"


def test_console_line_for_an_automatic_action_without_a_target():
    line = format_log_line(make_entry(actor=None, target=None, description=None))

    assert line == "type=BAN guild=1 actor=axios"


async def test_send_log_posts_an_embed_to_the_configured_channel():
    channel = make_channel()
    modlogger = ModLogger(bot=MagicMock())
    modlogger.set_channel(1, 555)

    await modlogger.send_log(
        LogType.BAN,
        guild=make_guild(channel),
        actor=FakeUser(10, "mod"),
        target=FakeUser(20, "spammer"),
        description="spam",
    )

    channel.send.assert_awaited_once()
    sent = channel.send.await_args.kwargs
    assert sent["embed"].title == LogType.BAN.value
    assert sent["allowed_mentions"].everyone is False


async def test_send_log_does_nothing_in_a_channel_when_none_is_configured():
    channel = make_channel()
    modlogger = ModLogger(bot=MagicMock())

    await modlogger.send_log(LogType.BAN, guild=make_guild(channel), actor=FakeUser(10, "mod"))

    channel.send.assert_not_awaited()


async def test_send_log_uses_an_injected_channel_lookup():
    channel = make_channel()
    guild = make_guild(channel)

    async def lookup(guild_id: int) -> int | None:
        return 777

    modlogger = ModLogger(bot=MagicMock(), channel_lookup=lookup)

    await modlogger.send_log(LogType.UNBAN, guild=guild, actor=FakeUser(10, "mod"))

    guild.get_channel.assert_called_once_with(777)
    channel.send.assert_awaited_once()


async def test_send_log_survives_a_missing_channel():
    modlogger = ModLogger(bot=MagicMock())
    modlogger.set_channel(1, 555)

    await modlogger.send_log(LogType.BAN, guild=make_guild(None), actor=FakeUser(10, "mod"))


async def test_send_log_survives_a_failed_send():
    channel = make_channel()
    channel.send.side_effect = discord.Forbidden(MagicMock(status=403, reason="Forbidden"), "no")
    modlogger = ModLogger(bot=MagicMock())
    modlogger.set_channel(1, 555)

    await modlogger.send_log(LogType.BAN, guild=make_guild(channel), actor=FakeUser(10, "mod"))


def test_clearing_a_channel_removes_it():
    modlogger = ModLogger(bot=MagicMock())
    modlogger.set_channel(1, 555)
    modlogger.set_channel(1, None)

    assert modlogger._channels == {}
