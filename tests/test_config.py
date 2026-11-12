import pytest

from app.config import ConfigurationError, load_settings

TOKEN = "123456789:" + "a" * 35


def test_environment_overrides_dotenv(tmp_path):
    env = tmp_path / ".env"
    env.write_text("BOT_TOKEN=bad\nLOG_LEVEL=warning\n", encoding="utf-8")
    settings = load_settings(env, {"BOT_TOKEN": TOKEN})
    assert settings.bot_token.get_secret_value() == TOKEN
    assert settings.log_level == "WARNING"
    assert TOKEN not in repr(settings)


def test_no_token_reports_how_to_fix(tmp_path):
    with pytest.raises(ConfigurationError, match="BOT_TOKEN kiritilmagan"):
        load_settings(tmp_path / "missing", {})


@pytest.mark.parametrize("name,value", [
    ("BOT_TOKEN", "secret-invalid-value"),
    ("LOG_LEVEL", "secret-invalid-level"),
    ("REQUEST_TIMEOUT", "secret-invalid-timeout"),
    ("REQUEST_TIMEOUT", "0"),
    ("REQUEST_TIMEOUT", "121"),
])
def test_invalid_settings_never_echo_values(tmp_path, name, value):
    with pytest.raises(ConfigurationError) as error:
        load_settings(tmp_path / "missing", {"BOT_TOKEN": TOKEN, name: value})
    assert name in str(error.value)
    assert TOKEN not in str(error.value)
    if value.startswith("secret"):
        assert value not in str(error.value)


def test_bom_dotenv_and_no_interpolation(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"BOT_TOKEN={TOKEN}\n", encoding="utf-8-sig")
    assert load_settings(env, {}).bot_token.get_secret_value() == TOKEN


def test_unreadable_env_reports_safe_error(tmp_path):
    env = tmp_path / ".env"
    env.write_bytes(b"\xff\xfe\xff")
    with pytest.raises(ConfigurationError, match="UTF-8"):
        load_settings(env, {})
