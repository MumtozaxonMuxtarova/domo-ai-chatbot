"""Groq configuration contracts using temporary dotenv files and fake keys only."""

import pytest
from pydantic import SecretStr

from app.llm.errors import LLMConfigurationError
from app.llm.settings import LLMSettings, load_llm_settings

FAKE_KEY = "gsk_offline_test_key_never_sent_to_a_server"
MODEL = "openai/gpt-oss-20b"


def write_env(tmp_path, values=None, *, encoding="utf-8"):
    content = {"GROQ_API_KEY": FAKE_KEY, "GROQ_MODEL": MODEL}
    if values is not None:
        content.update(values)
    target = tmp_path / ".env"
    target.write_text("\n".join(f"{key}={value}" for key, value in content.items()) + "\n", encoding=encoding)
    return target


def test_credentials_and_model_come_from_dotenv_not_process_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "private-process-environment-key")
    monkeypatch.setenv("GROQ_MODEL", "wrong-environment-model")
    result = load_llm_settings(write_env(tmp_path))
    assert result.api_key.get_secret_value() == FAKE_KEY
    assert result.model == MODEL
    assert FAKE_KEY not in str(result)
    assert FAKE_KEY not in repr(result)


def test_bom_dotenv_reads_explicit_timeout_and_token_limit(tmp_path):
    result = load_llm_settings(write_env(tmp_path, {
        "GROQ_TIMEOUT_SECONDS": "7.5", "GROQ_MAX_OUTPUT_TOKENS": "256",
    }, encoding="utf-8-sig"))
    assert result.api_key.get_secret_value() == FAKE_KEY
    assert result.timeout_seconds == 7.5
    assert result.max_output_tokens == 256


@pytest.mark.parametrize("missing", ["GROQ_API_KEY", "GROQ_MODEL"])
def test_missing_required_file_value_is_not_filled_from_environment(tmp_path, monkeypatch, missing):
    monkeypatch.setenv("GROQ_API_KEY", "private-environment-key")
    monkeypatch.setenv("GROQ_MODEL", MODEL)
    with pytest.raises(LLMConfigurationError) as error:
        load_llm_settings(write_env(tmp_path, {missing: ""}))
    assert FAKE_KEY not in str(error.value)
    assert "private-environment-key" not in str(error.value)


@pytest.mark.parametrize("value", ["0", "61", "private-invalid-timeout"])
def test_invalid_timeout_is_reported_without_input_values(tmp_path, value):
    with pytest.raises(LLMConfigurationError) as error:
        load_llm_settings(write_env(tmp_path, {"GROQ_TIMEOUT_SECONDS": value}))
    assert FAKE_KEY not in str(error.value)
    assert "private-invalid-timeout" not in str(error.value)


def test_invalid_output_token_limits_are_rejected_safely(tmp_path):
    for value in ("127", "4097"):
        with pytest.raises(LLMConfigurationError) as error:
            load_llm_settings(write_env(tmp_path, {"GROQ_MAX_OUTPUT_TOKENS": value}))
        assert FAKE_KEY not in str(error.value)


def test_unreadable_dotenv_is_an_actionable_safe_configuration_error(tmp_path):
    target = tmp_path / ".env"
    target.write_bytes(b"\xff\xfe\xff")
    with pytest.raises(LLMConfigurationError) as error:
        load_llm_settings(target)
    assert "Traceback" not in str(error.value)


def test_direct_settings_repr_masks_the_key():
    settings = LLMSettings(api_key=SecretStr(FAKE_KEY), model=MODEL)
    assert settings.api_key.get_secret_value() == FAKE_KEY
    assert FAKE_KEY not in repr(settings)
