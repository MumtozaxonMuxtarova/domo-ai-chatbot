"""Load local configuration without printing secret values."""

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigurationError(ValueError):
    """An actionable configuration error containing no input values."""


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    bot_token: SecretStr
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    request_timeout: int = Field(default=30, ge=5, le=120)

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, value: SecretStr) -> SecretStr:
        # This validates shape only. Telegram validates the actual credential.
        if not re.fullmatch(r"[1-9][0-9]{4,}:[A-Za-z0-9_-]{20,}", value.get_secret_value()):
            raise ValueError("BotFather tokenining formati noto'g'ri")
        return value


def load_settings(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Environment variables override .env; relative CWD does not affect its path."""
    source = PROJECT_ROOT / ".env" if env_file is None else env_file
    try:
        values = dict(dotenv_values(source, encoding="utf-8-sig", interpolate=False))
    except (OSError, UnicodeError):
        raise ConfigurationError(".env faylini o'qib bo'lmadi. Ruxsat va UTF-8 formatini tekshiring.") from None
    values.update(os.environ if environ is None else environ)
    token = (values.get("BOT_TOKEN") or "").strip()
    if not token:
        raise ConfigurationError(
            "BOT_TOKEN kiritilmagan. .env.example nusxasidan .env yarating va BotFather tokenini kiriting."
        )
    try:
        return Settings(
            bot_token=SecretStr(token),
            log_level=(values.get("LOG_LEVEL") or "INFO").strip().upper(),
            request_timeout=(values.get("REQUEST_TIMEOUT") or "30").strip(),
        )
    except ValidationError as error:
        names = {"bot_token": "BOT_TOKEN", "log_level": "LOG_LEVEL", "request_timeout": "REQUEST_TIMEOUT"}
        fields = sorted({names.get(str(item["loc"][0]), "sozlama") for item in error.errors()})
        raise ConfigurationError(
            "Sozlama noto'g'ri: " + ", ".join(fields) + ". .env.example va README ko'rsatmalarini tekshiring."
        ) from None
