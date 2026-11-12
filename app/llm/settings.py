"""Explicit .env-only loading; importing this module does not load credentials."""

from pathlib import Path
from typing import Annotated

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from app.config import PROJECT_ROOT
from app.llm.errors import LLMConfigurationError


class LLMSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    api_key: SecretStr
    model: Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,127}$")]
    timeout_seconds: Annotated[float, Field(ge=0.1, le=60, allow_inf_nan=False)] = 15.0
    max_output_tokens: Annotated[int, Field(ge=128, le=4096)] = 1200

    @field_validator("api_key")
    @classmethod
    def valid_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if (not raw.strip() or len(raw) > 512 or not raw.isascii()
                or any(char.isspace() or ord(char) < 33 or ord(char) == 127 for char in raw)):
            raise ValueError("GROQ_API_KEY noto'g'ri")
        return value


def load_llm_settings(env_file: Path | None = None) -> LLMSettings:
    """Read only the named .env file, without interpolation or process overrides."""
    try:
        values = dotenv_values(
            PROJECT_ROOT / ".env" if env_file is None else env_file,
            interpolate=False, encoding="utf-8-sig",
        )
        return LLMSettings(
            api_key=SecretStr(values.get("GROQ_API_KEY") or ""),
            model=values.get("GROQ_MODEL") or "",
            timeout_seconds=values.get("GROQ_TIMEOUT_SECONDS") or 15.0,
            max_output_tokens=values.get("GROQ_MAX_OUTPUT_TOKENS") or 1200,
        )
    except (OSError, UnicodeError, ValueError, ValidationError):
        raise LLMConfigurationError(
            ".env ichidagi GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT_SECONDS va "
            "GROQ_MAX_OUTPUT_TOKENS sozlamalarini tekshiring."
        ) from None
