import json
import os
import time

import pytest
from pydantic import ValidationError

from axios.config import ConfigError
from axios.database.servers import ServerSettings, ServerStore


# store pointed at a file inside the test's temporary folder
@pytest.fixture
def store(tmp_path) -> ServerStore:
    return ServerStore(tmp_path / "servers.json")


# rewrites the file and bumps its mtime, so the store notices the change on any filesystem
def edit_file(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    later = time.time_ns() + 10_000_000_000
    os.utime(path, ns=(later, later))


def test_a_missing_file_gives_defaults(store):
    store.load()

    assert store.get(1) == ServerSettings()
    assert store.get(1).mod_log_channel_id is None


def test_a_blank_file_counts_as_empty(store):
    store.path.write_text("\n", encoding="utf-8")

    store.load()

    assert store.get(1) == ServerSettings()


def test_load_reads_settings_and_converts_string_keys_to_ids(store):
    store.path.write_text(
        json.dumps({"schema_version": 1, "servers": {"123": {"mod_log_channel_id": 456}}}),
        encoding="utf-8",
    )

    store.load()

    assert store.get(123).mod_log_channel_id == 456


def test_load_rejects_invalid_json(store):
    store.path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ConfigError):
        store.load()


def test_load_rejects_a_typo_in_a_setting_name(store):
    store.path.write_text(
        json.dumps({"servers": {"123": {"mod_log_chanel_id": 456}}}),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="mod_log_chanel_id"):
        store.load()


def test_load_rejects_an_unknown_schema_version(store):
    store.path.write_text(json.dumps({"schema_version": 2, "servers": {}}), encoding="utf-8")

    with pytest.raises(ConfigError):
        store.load()


async def test_update_saves_a_readable_file_that_a_new_store_can_load(store):
    store.load()

    await store.update(123, mod_log_channel_id=456)

    saved = json.loads(store.path.read_text(encoding="utf-8"))
    assert saved == {"schema_version": 1, "servers": {"123": {"mod_log_channel_id": 456}}}

    reopened = ServerStore(store.path)
    reopened.load()
    assert reopened.get(123).mod_log_channel_id == 456


async def test_update_leaves_no_temp_file_behind(store):
    store.load()

    await store.update(123, mod_log_channel_id=456)

    assert not store.path.with_name("servers.json.tmp").exists()


async def test_update_can_clear_a_setting(store):
    store.load()
    await store.update(123, mod_log_channel_id=456)

    await store.update(123, mod_log_channel_id=None)

    assert store.get(123).mod_log_channel_id is None


async def test_update_rejects_invalid_values_without_touching_the_file(store):
    store.load()
    await store.update(123, mod_log_channel_id=456)
    before = store.path.read_text(encoding="utf-8")

    with pytest.raises(ValidationError):
        await store.update(123, mod_log_channel_id="not a number")

    assert store.path.read_text(encoding="utf-8") == before
    assert store.get(123).mod_log_channel_id == 456


async def test_update_rejects_unknown_setting_names(store):
    store.load()

    with pytest.raises(ValidationError):
        await store.update(123, mod_log_chanel_id=456)


async def test_update_keeps_hand_edits_made_while_the_bot_is_running(store):
    store.load()
    await store.update(1, mod_log_channel_id=100)

    edit_file(
        store.path,
        json.dumps(
            {"servers": {"1": {"mod_log_channel_id": 100}, "2": {"mod_log_channel_id": 200}}}
        ),
    )
    await store.update(3, mod_log_channel_id=300)

    saved = json.loads(store.path.read_text(encoding="utf-8"))["servers"]
    assert set(saved) == {"1", "2", "3"}


def test_get_picks_up_a_hand_edit(store):
    store.load()

    edit_file(store.path, json.dumps({"servers": {"123": {"mod_log_channel_id": 456}}}))

    assert store.get(123).mod_log_channel_id == 456


def test_a_bad_hand_edit_keeps_the_last_good_settings(store):
    store.path.write_text(
        json.dumps({"servers": {"123": {"mod_log_channel_id": 456}}}), encoding="utf-8"
    )
    store.load()

    edit_file(store.path, "{broken")

    assert store.get(123).mod_log_channel_id == 456


def test_deleting_the_file_while_running_resets_to_defaults(store):
    store.path.write_text(
        json.dumps({"servers": {"123": {"mod_log_channel_id": 456}}}), encoding="utf-8"
    )
    store.load()

    store.path.unlink()

    assert store.get(123).mod_log_channel_id is None


async def test_mod_log_channel_matches_the_modlogger_lookup(store):
    store.load()
    await store.update(123, mod_log_channel_id=456)

    assert await store.mod_log_channel(123) == 456
    assert await store.mod_log_channel(999) is None


async def test_update_creates_the_missing_folder(tmp_path):
    store = ServerStore(tmp_path / "data" / "servers.json")
    store.load()

    await store.update(123, mod_log_channel_id=456)

    assert (tmp_path / "data" / "servers.json").exists()
