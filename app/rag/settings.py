"""Retrieval-only settings; does not require or expose Telegram/Groq credentials."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from app.config import PROJECT_ROOT
from app.rag.errors import RetrievalError

DEFAULT_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_REVISION = "614241f"


@dataclass(frozen=True)
class RagSettings:
    model: str = DEFAULT_MODEL
    revision: str = DEFAULT_REVISION
    cache_path: Path = PROJECT_ROOT / "data" / "models"
    chroma_path: Path = PROJECT_ROOT / "data" / "chroma"
    min_score: float = 0.80


def load_rag_settings() -> RagSettings:
    try:
        values = dict(dotenv_values(PROJECT_ROOT / ".env", interpolate=False, encoding="utf-8-sig"))
        values.update(os.environ)
        model = (values.get("EMBEDDING_MODEL") or DEFAULT_MODEL).strip()
        # A different model must explicitly select its own revision.
        revision = (values.get("EMBEDDING_REVISION") or (DEFAULT_REVISION if model == DEFAULT_MODEL else "")).strip()
        if not revision or revision in ("main", "master"):
            raise ValueError("A fixed model revision is required")
        def local_path(name: str, default: str) -> Path:
            candidate = Path(values.get(name) or default)
            return (candidate if candidate.is_absolute() else PROJECT_ROOT / candidate).resolve()
        score = float(values.get("RAG_MIN_SCORE") or "0.80")
        if not -1 <= score <= 1:
            raise ValueError
        return RagSettings(
            model=model, revision=revision,
            cache_path=local_path("EMBEDDING_CACHE_PATH", "data/models"),
            chroma_path=local_path("CHROMA_PATH", "data/chroma"), min_score=score,
        )
    except (OSError, UnicodeError, ValueError):
        raise RetrievalError("Retrieval sozlamalari noto'g'ri. Model, yo'llar va RAG_MIN_SCORE ni tekshiring.") from None
