from types import SimpleNamespace

import pytest
from discord.ext import commands

from axios.moderation.converters import (
    AmbiguousUserError,
    UserTarget,
    find_members_by_name,
)


# stand-in member with only the attributes name matching reads
def make_member(name: str, global_name: str | None = None, nick: str | None = None):
    return SimpleNamespace(name=name, global_name=global_name, nick=nick)


# stand-in context with a guild that holds the given members
def make_ctx(*members) -> SimpleNamespace:
    return SimpleNamespace(guild=SimpleNamespace(members=list(members)))


def test_matches_username_ignoring_case():
    alex = make_member("alex")

    assert find_members_by_name([alex], "ALEX") == [alex]


def test_matches_display_name_and_nickname():
    alex = make_member("alex_123", global_name="Alex Smith", nick="Fat Albert")

    assert find_members_by_name([alex], "alex smith") == [alex]
    assert find_members_by_name([alex], "fat albert") == [alex]


def test_leading_at_sign_is_ignored():
    alex = make_member("alex")

    assert find_members_by_name([alex], "@alex") == [alex]


def test_partial_names_do_not_match():
    alex = make_member("alexander")

    assert find_members_by_name([alex], "alex") == []


def test_empty_text_matches_nobody():
    assert find_members_by_name([make_member("alex")], "") == []
    assert find_members_by_name([make_member("alex")], "@") == []


async def test_converter_returns_the_single_matching_member():
    alex = make_member("alex")
    ctx = make_ctx(alex, make_member("sam"))

    assert await UserTarget().convert(ctx, "alex") is alex


async def test_converter_refuses_to_guess_between_several_members():
    ctx = make_ctx(make_member("alex"), make_member("other", nick="Alex"))

    with pytest.raises(AmbiguousUserError):
        await UserTarget().convert(ctx, "alex")


async def test_converter_raises_user_not_found_when_nobody_matches():
    ctx = make_ctx(make_member("sam"))

    with pytest.raises(commands.UserNotFound):
        await UserTarget().convert(ctx, "alex")


async def test_converter_sends_ids_and_mentions_to_discordpys_converter(monkeypatch):
    sentinel = object()
    seen = []

    async def fake_convert(self, ctx, argument):
        seen.append(argument)
        return sentinel

    monkeypatch.setattr(commands.UserConverter, "convert", fake_convert)
    ctx = make_ctx()

    assert await UserTarget().convert(ctx, "123456789012345678") is sentinel
    assert await UserTarget().convert(ctx, "<@123456789012345678>") is sentinel
    assert seen == ["123456789012345678", "<@123456789012345678>"]
