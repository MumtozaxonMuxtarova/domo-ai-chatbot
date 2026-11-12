"""Natural grounded answers, bounded dialogue modes and original safety guidance."""

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
    "uz": "Bu bo‘yicha tasdiqlangan ma’lumotim yo‘q. Aniq javobni xizmat ko‘rsatuvchingizning rasmiy yordamidan olish kerak.",
    "ru": "У меня нет подтверждённых данных по этому вопросу. Уточните их в официальной поддержке поставщика услуги.",
}
DEMO_PREFIX = {
    "uz": "DEMO — bilim bazasidagi umumiy yo‘riqnoma:",
    "ru": "DEMO — общая инструкция из базы знаний:",
}

CONVERSATION_TEXT = {
    "greeting": {
        "uz": "Assalomu alaykum! Elektr, gaz, suv yoki isitish bo‘yicha qanday yordam kerak?",
        "ru": "Здравствуйте! Чем помочь по вопросам электричества, газа, воды или отопления?",
    },
    "thanks": {
        "uz": "Arzimaydi! Yana biror kommunal masala bo‘yicha yordam kerakmi?",
        "ru": "Пожалуйста! Могу ещё помочь с каким-нибудь коммунальным вопросом?",
    },
    "account_unavailable": {
        "uz": "Men hisobingizni yoki to‘lov holatini ko‘ra olmayman. Buni xizmat ko‘rsatuvchingizning rasmiy kanali orqali tekshiring.",
        "ru": "Я не могу проверить ваш счёт или статус платежа. Проверьте это через официальный канал поставщика услуги.",
    },
    "out_of_scope": {
        "uz": "Men elektr, gaz, suv va isitish masalalarida yordam beraman. Shu xizmatlardan biri bo‘yicha savolingiz bormi?",
        "ru": "Я помогаю с вопросами электричества, газа, воды и отопления. Есть вопрос по одной из этих услуг?",
    },
    "insufficient_context": SAFE_FALLBACK,
}
CLARIFICATION_TEXT = {
    "service": {
        "uz": "Qaysi xizmatda muammo bor: elektr, gaz, suv yoki isitish?",
        "ru": "С какой услугой возникла проблема: электричеством, газом, водой или отоплением?",
    },
    "supplier": {
        "uz": "Qaysi kommunal xizmat va qaysi ta’minotchi haqida so‘rayapsiz?",
        "ru": "О какой коммунальной услуге и каком поставщике идёт речь?",
    },
    "problem": {
        "uz": "Nima bo‘ldi? Qaysi xizmatda muammo borligini qisqacha yozing.",
        "ru": "Что случилось? Кратко опишите проблему и укажите услугу.",
    },
    "payment": {
        "uz": "Pul kartadan yechildimi yoki to‘lov umuman amalga oshmadimi?",
        "ru": "Деньги списались с карты или платёж вообще не прошёл?",
    },
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
    # Older internal clients may still send a quote. If supplied, validate it;
    # the Groq schema itself now asks only for IDs to avoid brittle recopying.
    quote: Annotated[str, Field(min_length=1, max_length=900)] | None = None


class _Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mode: Literal["grounded", "greeting", "thanks", "clarify", "account_unavailable", "insufficient_context", "out_of_scope"]
    language: Literal["uz", "ru"]
    answer: Annotated[str, Field(max_length=1200)]
    clarification: Literal["none", "service", "supplier", "problem", "payment"]
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


def _personal_amount_question(question: str) -> bool:
    """Known hard limit: no real account access, regardless of model wording."""
    text = question.casefold().replace("ё", "е").translate(str.maketrans({"‘": "'", "’": "'", "ʻ": "'", "ʼ": "'"}))
    if re.search(r"\b(?:qanday|qayer\w*|как|где)\b", text):
        return False  # General instructions on HOW to check remain answerable.
    uz_personal = re.search(r"\b(?:qarzim|qarzdorligim|balansim|hisobimda\w*|qoldig'im)\b", text)
    if uz_personal and re.search(r"\b(?:qancha|necha|miqdor\w*)\b", text):
        return True
    ru_personal = re.search(r"\b(?:мой|моя|моем|моей|мою|у\s+меня|я\s+должен)\b", text)
    return bool(ru_personal and re.search(r"\b(?:сколько|каков\w*|какой|сумм\w*)\b", text)
                and re.search(r"\b(?:баланс\w*|долг\w*|задолжен\w*|счет\w*|денег|должен)\b", text))


def _natural_answer_allowed(answer: str, chunks: list[Chunk], language: str) -> bool:
    """Reject concrete unsafe additions; these checks do not prove entailment."""
    if (not answer.strip() or suspicious_instruction(answer)
            or re.search(r"https?://|www\.|```|<[^>]+>|[\x00-\x08\x0b\x0c\x0e-\x1f]", answer)
            or re.search(
                r"chunk_id|document_id|json_schema|response_format|TECHNICAL_SYSTEM_ONLY|"
                r"\b(?:system|developer)\s*(?:prompt|message|instructions?)|"
                r"системн\w*\s+(?:промпт|инструкц)|ichki\s+(?:prompt|ko‘rsatma|ko'rsatma)|"
                r"Показывайте\s+только|Faqat\s+mavjud\s+tasdiqlangan\s+tekshirish|"
                r"\b(?:groq|embedding|sentence.?transformers)\b", answer, re.I)):
        return False
    normalized = answer.casefold().translate(str.maketrans({"‘": "'", "’": "'", "ʻ": "'", "ʼ": "'"}))
    if re.search(
        r"\b(?:balansingiz|qarzingiz|qarzdorligingiz|qoldig'ingiz)\s+(?:\d|nol|yo'q|bor\b|to'langan|yopilgan)|"
        r"\bsizda\s+qarz\s+(?:yo'q|bor)|"
        r"\bto'lovingiz\s+(?:tasdiqlandi|o'tdi|tushdi|qabul\s+qilindi)|"
        r"\b(?:pul(?:ingiz)?|to'lov(?:ingiz)?)\s+(?:albatta\s+)?qaytariladi|"
        r"\bваш[ае]?\s+(?:баланс|долг|задолженность|остаток)\w*\s+(?:\d|составля|рав|нул|погаш)|"
        r"\bу\s+вас\s+(?:нет|есть|отсутствует)\s+(?:долг|задолжен)|"
        r"\bваш\s+плат[её]ж\s+(?:зачислен|подтвержден|поступил)|"
        r"\bденьги\s+(?:вам\s+)?(?:обязательно\s+)?вернут", normalized,
    ):
        return False
    evidence_text = "\n".join(_body(chunk) for chunk in chunks)
    if any(word in normalized and word not in evidence_text.casefold()
           for word in ("ertaga", "bugun", "завтра", "сегодня")):
        return False
    if re.search(r"\bчерез\s+(?:несколько|один|два|две|три|четыре|пять)\s+(?:час|дн|ден|сут|недел)", normalized):
        return False
    for number in re.findall(r"\d+(?:[.,]\d+)?", answer):
        # The only numeric ordinary guidance currently approved is HET contact
        # 1154. Numeric account facts/tariffs cannot be inferred from a phone ID.
        if (number != "1154" or not any("het_contact" in chunk.source_ids for chunk in chunks)
                or not re.search(r"elektr|электр", answer, re.I)
                or re.search(r"1154\s*(?:so'm|so‘m|сум|руб)|(?:balans|qarz|баланс|долг)\w*\W{0,8}1154", normalized)):
            return False
    cyrillic = len(re.findall(r"[а-яё]", answer, re.I))
    latin = len(re.findall(r"[a-z]", answer, re.I))
    if language == "ru":
        return cyrillic >= 3 and cyrillic >= latin
    # A Latin alphabet alone does not distinguish Uzbek from English. These
    # lightweight utility-language markers reject obvious wrong-language output;
    # they are not a general-purpose language detector.
    words = re.findall(r"[a-z]+(?:'[a-z]+)*", normalized)
    markers = ("elektr", "gaz", "suv", "isitish", "to'lov", "hisob", "qarz", "chek",
               "ta'minot", "xizmat", "rasmiy", "murojaat", "tekshir", "saqla", "aniq",
               "tashkilot", "kvitansiya", "uchun", "bilan", "kerak", "mumkin", "emas",
               "bo'lsa", "qiling", "yordam", "bank", "qo'ng'iroq")
    return latin >= 3 and cyrillic <= latin // 3 and sum(word.startswith(markers) for word in words) >= 2


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
        if not isinstance(hits, (list, tuple)) or not 0 <= len(hits) <= 3:
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
        return chunks

    async def answer(self, question: str, hits: list[RetrievalHit], *, language: str | None = None) -> AnswerResult:
        selected = select_language(question, language)
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            return self._fallback(selected, "invalid_question")
        if suspicious_instruction(question):
            return self._fallback(selected, "unsafe_input")
        chunks = self._context(hits, selected)
        if chunks is None:
            return self._fallback(selected, "invalid_context")
        if _personal_amount_question(question):
            return AnswerResult(CONVERSATION_TEXT["account_unavailable"][selected], selected,
                                "answered", "account_unavailable")
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
            if decision.mode != "grounded":
                if decision.evidence:
                    raise ValueError
                if decision.mode == "clarify":
                    if decision.clarification == "none":
                        raise ValueError
                    text = CLARIFICATION_TEXT[decision.clarification][selected]
                else:
                    if decision.clarification != "none":
                        raise ValueError
                    text = CONVERSATION_TEXT[decision.mode][selected]
                if decision.mode == "insufficient_context":
                    return self._fallback(selected, "insufficient_context")
                return AnswerResult(text, selected, "answered", decision.mode)
            if not decision.evidence or decision.clarification != "none":
                raise ValueError
            allowed = {chunk.id: chunk for chunk in chunks}
            seen = set()
            quotes, references, cited = [], [], []
            for evidence in decision.evidence:
                chunk = allowed.get(evidence.chunk_id)
                if (chunk is None or chunk.id not in self._customer_ids or chunk.id in seen
                        or ("quote" in evidence.model_fields_set and evidence.quote != _body(chunk))):
                    raise ValueError
                seen.add(chunk.id)
                cited.append(chunk)
                quotes.append(_body(chunk))
                references.append(Reference(
                    chunk.id, chunk.document_id, chunk.filename, chunk.source_ids,
                    tuple(str(self.catalog.sources[key].url) for key in chunk.source_ids),
                ))
            is_safety = any(chunk.section.startswith(("Xavfsizlik javobi", "Ответ по безопасности")) for chunk in cited)
            if is_safety:
                text = "\n\n".join(quotes)
            elif _natural_answer_allowed(decision.answer, cited, selected):
                text = decision.answer.strip()
            else:
                raise ValueError
            return AnswerResult(
                DEMO_PREFIX[selected] + "\n\n" + text, selected,
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
                or suspicious_instruction(question) or _personal_amount_question(question)):
            return await self.llm.answer(question, [], language=selected)
        try:
            candidates = await asyncio.to_thread(
                self.retriever.search, question, language=selected,
                top_k=20, min_score=self.llm.min_score,
            )
        except (RetrievalError, ValueError):
            return self.llm._fallback(selected, "retrieval_error", status="error")
        if not isinstance(candidates, (list, tuple)) or len(candidates) > 20:
            return self.llm._fallback(selected, "invalid_context")
        public_hits = []
        for hit in candidates:
            # Internal sections must not crowd public answers out of the top-3.
            # Validate each candidate before filtering; forged text is not an
            # excuse to silently treat an unsafe result as an empty search.
            chunks = self.llm._context([hit], selected)
            if chunks is None:
                return self.llm._fallback(selected, "invalid_context")
            if chunks:
                public_hits.append(hit)
        return await self.llm.answer(question, public_hits[:3], language=selected)
