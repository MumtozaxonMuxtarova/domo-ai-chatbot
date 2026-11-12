"""Grounded, extractive answers over the existing bilingual retrieval results."""

import asyncio
import json
import math
import re
from collections.abc import Callable
from collections import Counter
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.faq import KnowledgeCatalog
from app.llm.errors import LLMServiceError
from app.llm.prompts import build_messages, suspicious_instruction
from app.rag.chunking import Chunk, build_chunks
from app.rag.errors import RetrievalError
from app.rag.retrieval import RetrievalHit, Retriever

SAFE_FALLBACK = {
    "uz": "Bilim bazasida bu savolga tasdiqlangan javob yetarli emas. Taxmin qilmayman. "
          "Savolni aniqlashtiring yoki xizmat ko‘rsatuvchining rasmiy yordamiga murojaat qiling. "
          "Bot haqiqiy hisoblar va to‘lovlarni tekshira olmaydi.",
    "ru": "В базе знаний недостаточно подтверждённых данных для ответа на этот вопрос. "
          "Я не буду делать предположения. Уточните вопрос или обратитесь в официальную "
          "поддержку поставщика услуги. Бот не может проверять реальные счета и платежи.",
}
DEMO_PREFIX = {
    "uz": "DEMO — bilim bazasidagi umumiy yo‘riqnoma:",
    "ru": "DEMO — общая инструкция из базы знаний:",
}


@dataclass(frozen=True)
class Reference:
    chunk_id: str
    document_id: str
    filename: str
    source_ids: tuple[str, ...]
    source_urls: tuple[str, ...]


@dataclass(frozen=True)
class AnswerResult:
    text: str
    language: str
    status: Literal["answered", "fallback", "error"]
    reason: str
    references: tuple[Reference, ...] = ()
    retry_after: float | None = None


class CompletionClient(Protocol):
    async def complete(self, messages: list[dict]) -> str: ...


class _Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    chunk_id: Annotated[str, Field(min_length=1, max_length=128)]
    quote: Annotated[str, Field(min_length=1, max_length=900)]


class _Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answerable: bool
    language: Literal["uz", "ru"]
    evidence: Annotated[list[_Evidence], Field(max_length=3)]


def select_language(question: object, language: str | None = None) -> str:
    if language is not None:
        if language not in ("uz", "ru"):
            raise ValueError("language must be uz or ru")
        return language
    if not isinstance(question, str):
        return "uz"
    if re.search("[ўқғҳЎҚҒҲ]", question):
        return "uz"
    return "ru" if re.search("[а-яёА-ЯЁ]", question) else "uz"


def _body(chunk: Chunk) -> str:
    return chunk.text.split("\n\n", 1)[1]


def _customer_facing(chunk: Chunk, catalog: KnowledgeCatalog) -> bool:
    """Require both a public section and a complete, approved answer for its doc."""
    short, ordinary, safety = {
        "uz": ("Tasdiqlangan qisqa javob", "Oddiy muammo uchun javob",
               "Xavfsizlik javobi — rasmiy manbalarga tayangan"),
        "ru": ("Утверждённый краткий ответ", "Ответ при обычной проблеме",
               "Ответ по безопасности — на основе официальных источников"),
    }[chunk.language]
    body = _body(chunk)
    if chunk.section == short:
        return any(
            item.status == "approved" and chunk.document_id in item.source_ids
            and body == item.answer.text(chunk.language) for item in catalog.faq.items
        )
    if chunk.section in (ordinary, safety):
        items = catalog.support.utilities if chunk.section == ordinary else catalog.support.safety
        return any(
            chunk.document_id in item.document_ids and body == item.answer.text(chunk.language)
            for item in items
        )
    return (chunk.document_id == "demo_scope" and chunk.section == "Overview"
            and body == catalog.support.limitations.text(chunk.language))


def _unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


class GroundedLLMService:
    def __init__(
        self, client: CompletionClient, catalog: KnowledgeCatalog, *, min_score: float = 0.80,
        token_counter: Callable[[str], int] | None = None,
    ):
        if not math.isfinite(min_score) or not -1 <= min_score <= 1:
            raise ValueError("min_score must be between -1 and 1")
        self.client = client
        self.catalog = catalog
        self.min_score = min_score
        # Only catalogue-owned data is trusted, never a supplied/replaced hit body.
        self._chunks = {
            chunk.id: chunk for chunk in build_chunks(catalog, token_counter=token_counter)
        }
        self._customer_ids = {
            chunk.id for chunk in self._chunks.values() if _customer_facing(chunk, catalog)
        }
        section_counts = Counter(
            (chunk.document_id, chunk.language, chunk.section) for chunk in self._chunks.values()
            if chunk.section.startswith(("Xavfsizlik javobi", "Ответ по безопасности"))
        )
        # A tokenizer may split a future safety section. Never expose only its tail
        # or first half as if it were the complete approved emergency instruction.
        self._split_safety = {key for key, count in section_counts.items() if count > 1}

    @staticmethod
    def _fallback(language, reason, *, status="fallback", retry_after=None):
        return AnswerResult(SAFE_FALLBACK[language], language, status, reason, retry_after=retry_after)

    def _context(self, hits, language: str) -> list[Chunk] | None:
        if not isinstance(hits, (list, tuple)) or not 1 <= len(hits) <= 3:
            return None
        chunks = []
        seen = set()
        for hit in hits:
            if not isinstance(hit, RetrievalHit) or not isinstance(hit.chunk, Chunk):
                return None
            chunk = hit.chunk
            if (not isinstance(hit.score, (int, float)) or isinstance(hit.score, bool)
                    or not math.isfinite(hit.score) or not self.min_score <= hit.score <= 1
                    or chunk.language != language or not isinstance(chunk.id, str) or chunk.id in seen
                    or self._chunks.get(chunk.id) != chunk or suspicious_instruction(chunk.text)):
                return None
            if (chunk.document_id, chunk.language, chunk.section) in self._split_safety:
                return None
            seen.add(chunk.id)
            # Canonical KB text can still be an internal instruction. Deny by
            # default; expose only complete customer-facing, approved answers.
            if chunk.id not in self._customer_ids:
                continue
            chunks.append(chunk)
        return chunks or None

    async def answer(self, question: str, hits: list[RetrievalHit], *, language: str | None = None) -> AnswerResult:
        selected = select_language(question, language)
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            return self._fallback(selected, "invalid_question")
        if suspicious_instruction(question):
            return self._fallback(selected, "unsafe_input")
        chunks = self._context(hits, selected)
        if not chunks:
            return self._fallback(selected, "invalid_context")
        context = [{
            "chunk_id": chunk.id, "document_id": chunk.document_id,
            "language": chunk.language, "title": chunk.title, "section": chunk.section,
            "body": _body(chunk), "source_ids": list(chunk.source_ids),
            "content_type": chunk.content_type,
        } for chunk in chunks]
        try:
            raw = await self.client.complete(build_messages(question.strip(), selected, context))
        except LLMServiceError as error:
            return self._fallback(selected, error.code, status="error", retry_after=error.retry_after)
        try:
            if not isinstance(raw, str) or len(raw) > 16_000:
                raise ValueError
            decision = _Decision.model_validate(json.loads(raw, object_pairs_hook=_unique_json_pairs))
            if decision.language != selected:
                raise ValueError
            if not decision.answerable:
                if decision.evidence:
                    raise ValueError
                return self._fallback(selected, "insufficient_context")
            if not decision.evidence:
                raise ValueError
            allowed = {chunk.id: chunk for chunk in chunks}
            seen = set()
            quotes, references = [], []
            for evidence in decision.evidence:
                chunk = allowed.get(evidence.chunk_id)
                if (chunk is None or chunk.id not in self._customer_ids or chunk.id in seen
                        or evidence.quote != _body(chunk)
                        or suspicious_instruction(evidence.quote)):
                    raise ValueError
                seen.add(chunk.id)
                # Full bodies preserve conditions and emergency guidance; no model prose.
                quotes.append(evidence.quote)
                references.append(Reference(
                    chunk.id, chunk.document_id, chunk.filename, chunk.source_ids,
                    tuple(str(self.catalog.sources[key].url) for key in chunk.source_ids),
                ))
            return AnswerResult(
                DEMO_PREFIX[selected] + "\n\n" + "\n\n".join(quotes), selected,
                "answered", "grounded_evidence", tuple(references),
            )
        except (ValueError, TypeError, ValidationError, RecursionError):
            return self._fallback(selected, "invalid_answer")


class RagAnswerService:
    """Connect an already-created/indexed retriever; do not build/download at import."""

    def __init__(self, retriever: Retriever, llm: GroundedLLMService):
        self.retriever = retriever
        self.llm = llm

    async def answer(self, question: str, *, language: str | None = None) -> AnswerResult:
        selected = select_language(question, language)
        if (not isinstance(question, str) or not question.strip() or len(question) > 2000
                or suspicious_instruction(question)):
            return await self.llm.answer(question, [], language=selected)
        try:
            hits = await asyncio.to_thread(
                self.retriever.search, question, language=selected,
                top_k=3, min_score=self.llm.min_score,
            )
        except (RetrievalError, ValueError):
            return self.llm._fallback(selected, "retrieval_error", status="error")
        return await self.llm.answer(question, hits, language=selected)
