from pathlib import Path

import pytest

from axios.config import ConfigError, Settings

ENV_VARS = (
    "DISCORD_TOKEN",
    "OPENAI_API_KEY",
    "COMMAND_PREFIX",
    "OWNER_IDS",
    "LOG_LEVEL",
    "ENABLE_UPDATE_COMMAND",
    "SERVERS_FILE",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Start every test with no Axios settings, and ignore any local .env file."""
    monkeypatch.setattr("axios.config.load_dotenv", lambda: None)
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def required_env(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_defaults_are_applied(required_env):
    settings = Settings.from_env()

    assert settings.discord_token == "test-token"
    assert settings.command_prefix == "$"
    assert settings.owner_ids == frozenset()
    assert settings.log_level == "INFO"
    assert settings.enable_update_command is False


def test_missing_discord_token_raises(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with pytest.raises(ConfigError, match="DISCORD_TOKEN"):
        Settings.from_env()


def test_missing_openai_key_raises(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")

    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        Settings.from_env()


def test_owner_ids_are_parsed(required_env, monkeypatch):
    monkeypatch.setenv("OWNER_IDS", "123, 456,")

    assert Settings.from_env().owner_ids == frozenset({123, 456})


def test_non_numeric_owner_id_raises(required_env, monkeypatch):
    monkeypatch.setenv("OWNER_IDS", "123,abc")

    with pytest.raises(ConfigError, match="OWNER_IDS"):
        Settings.from_env()


def test_invalid_log_level_raises(required_env, monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")

    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        Settings.from_env()


def test_update_command_can_be_enabled(required_env, monkeypatch):
    monkeypatch.setenv("ENABLE_UPDATE_COMMAND", "true")

    assert Settings.from_env().enable_update_command is True


def test_servers_file_defaults_to_the_data_folder(required_env):
    assert Settings.from_env().servers_file == Path("data/servers.json")


def test_servers_file_can_be_overridden(required_env, monkeypatch):
    monkeypatch.setenv("SERVERS_FILE", "/srv/axios/servers.json")

    assert Settings.from_env().servers_file == Path("/srv/axios/servers.json")
