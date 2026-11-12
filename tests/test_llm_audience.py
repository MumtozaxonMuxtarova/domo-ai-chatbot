"""Customer-facing answer regressions; canonical internal prose must not leak.

All clients are fake. Catalog changes in the last test exist only in memory.
"""

import json

import pytest

from app.faq import load_catalog
from app.llm.service import DEMO_PREFIX, SAFE_FALLBACK, GroundedLLMService
from app.rag.chunking import build_chunks
from app.rag.retrieval import RetrievalHit


SECTIONS = {
    "uz": {
        "short": "Tasdiqlangan qisqa javob",
        "detailed": "Batafsil yo‘riqnoma",
        "unknown": "Aniqlashtirilmagan ma’lumotlar",
    },
    "ru": {
        "short": "Утверждённый краткий ответ",
        "detailed": "Подробная инструкция",
        "unknown": "Неуточнённые сведения",
    },
}
INTERNAL_PHRASES = {
    "uz": (
        "Faqat mavjud tasdiqlangan tekshirish yo‘riqnomasini ko‘rsating",
        "Qarz, penya, tarif va sababni taxmin qilmang.",
        "Hisob-kitob tartibi, tariflar va e’tiroz bildirish jarayoni.",
    ),
    "ru": (
        "Показывайте только имеющуюся подтверждённую инструкцию",
        "Не предполагайте долг, пеню, тариф или причину.",
        "Порядок расчётов, тарифы и процедура оспаривания.",
    ),
}


class SelectingClient:
    """Select every supplied context entry, reproducing the old leakage path."""

    def __init__(self, response=None):
        self.response = response
        self.envelopes = []

    async def complete(self, messages):
        message = next(message for message in reversed(messages) if message["role"] == "user")
        envelope = json.loads(message["content"])
        self.envelopes.append(envelope)
        if self.response is not None:
            return json.dumps(self.response, ensure_ascii=False)
        return json.dumps({
            "answerable": bool(envelope["context"]),
            "language": envelope["language"],
            "evidence": [
                {"chunk_id": chunk["chunk_id"], "quote": chunk["body"]}
                for chunk in envelope["context"]
            ],
        }, ensure_ascii=False)


@pytest.fixture
def knowledge():
    catalog = load_catalog()
    return catalog, build_chunks(catalog)


def body(chunk):
    return chunk.text.split("\n\n", 1)[1]


def pick(chunks, document_id, language, section):
    return next(chunk for chunk in chunks if chunk.document_id == document_id
                and chunk.language == language and chunk.section == section)


def debt_chunks(chunks, language):
    return tuple(pick(chunks, "debt_check", language, SECTIONS[language][kind])
                 for kind in ("detailed", "short", "unknown"))


def debt_question(language):
    return ("Kommunal xizmatlar bo‘yicha qarzimni qanday tekshiraman?" if language == "uz"
            else "Как проверить задолженность за коммунальные услуги?")


def assert_no_internal_text(text, language):
    assert "TECHNICAL_SYSTEM_ONLY" not in text
    assert all(phrase not in text for phrase in INTERNAL_PHRASES[language])


def assert_safe_fallback(result, language):
    assert result.status == "fallback"
    assert result.language == language
    assert result.text == SAFE_FALLBACK[language]
    assert result.references == ()
    assert_no_internal_text(result.text, language)


@pytest.mark.parametrize("language", ["uz", "ru"])
async def test_live_debt_hit_order_exposes_only_approved_customer_answer(knowledge, language):
    catalog, chunks = knowledge
    detailed, short, unknown = debt_chunks(chunks, language)
    client = SelectingClient()
    result = await GroundedLLMService(client, catalog).answer(
        debt_question(language),
        [RetrievalHit(detailed, 0.94), RetrievalHit(short, 0.91), RetrievalHit(unknown, 0.89)],
        language=language,
    )
    assert result.status == "answered"
    assert result.language == language
    assert result.text == DEMO_PREFIX[language] + "\n\n" + catalog.faq_items["debt_check"].answer.text(language)
    assert len(client.envelopes) == 1
    context = client.envelopes[0]["context"]
    assert len(context) == 1
    assert context[0]["chunk_id"] == short.id
    assert context[0]["body"] == body(short)
    assert tuple(reference.chunk_id for reference in result.references) == (short.id,)
    assert_no_internal_text(result.text, language)


@pytest.mark.parametrize("language", ["uz", "ru"])
async def test_detailed_only_hits_fallback_without_calling_model(knowledge, language):
    catalog, chunks = knowledge
    detailed, _, _ = debt_chunks(chunks, language)
    client = SelectingClient()
    result = await GroundedLLMService(client, catalog).answer(
        debt_question(language), [RetrievalHit(detailed, 0.95)], language=language
    )
    assert_safe_fallback(result, language)
    assert client.envelopes == []


@pytest.mark.parametrize("language", ["uz", "ru"])
async def test_old_model_payload_with_internal_and_public_quotes_is_rejected_entirely(knowledge, language):
    catalog, chunks = knowledge
    detailed, short, _ = debt_chunks(chunks, language)
    client = SelectingClient(response={
        "answerable": True, "language": language,
        "evidence": [
            {"chunk_id": detailed.id, "quote": body(detailed)},
            {"chunk_id": short.id, "quote": body(short)},
        ],
    })
    result = await GroundedLLMService(client, catalog).answer(
        debt_question(language), [RetrievalHit(detailed, 0.94), RetrievalHit(short, 0.91)],
        language=language,
    )
    assert_safe_fallback(result, language)
    assert len(client.envelopes) == 1
    assert [entry["chunk_id"] for entry in client.envelopes[0]["context"]] == [short.id]


@pytest.mark.parametrize("language", ["uz", "ru"])
async def test_internal_prose_cannot_be_cited_under_public_short_answer_id(knowledge, language):
    catalog, chunks = knowledge
    detailed, short, _ = debt_chunks(chunks, language)
    client = SelectingClient(response={
        "answerable": True, "language": language,
        "evidence": [{"chunk_id": short.id, "quote": "TECHNICAL_SYSTEM_ONLY\n" + body(detailed)}],
    })
    result = await GroundedLLMService(client, catalog).answer(
        debt_question(language), [RetrievalHit(short, 0.95)], language=language
    )
    assert_safe_fallback(result, language)
    assert len(client.envelopes) == 1


@pytest.mark.parametrize("language", ["uz", "ru"])
@pytest.mark.parametrize("kind", ["safety", "demo_scope"])
async def test_approved_public_safety_and_demo_capabilities_remain_answerable(knowledge, language, kind):
    catalog, chunks = knowledge
    if kind == "safety":
        chunk = next(chunk for chunk in chunks if chunk.document_id == "gas_issues"
                     and chunk.language == language
                     and chunk.section.startswith(("Xavfsizlik javobi", "Ответ по безопасности")))
        question = "Gaz hidi bo‘lsa nima qilish kerak?" if language == "uz" else "Что делать при запахе газа?"
    else:
        chunk = pick(chunks, "demo_scope", language, "Overview")
        question = "Bot nimalarni qila oladi?" if language == "uz" else "Что умеет этот бот?"
    client = SelectingClient()
    result = await GroundedLLMService(client, catalog).answer(
        question, [RetrievalHit(chunk, 0.95)], language=language
    )
    assert result.status == "answered"
    assert result.language == language
    assert result.text == DEMO_PREFIX[language] + "\n\n" + body(chunk)
    assert tuple(reference.chunk_id for reference in result.references) == (chunk.id,)
    assert len(client.envelopes) == 1


@pytest.mark.parametrize("language", ["uz", "ru"])
async def test_new_or_contaminated_heading_is_fail_closed_with_catalog_changes_only_in_memory(knowledge, language):
    catalog, original_chunks = knowledge
    _, short, _ = debt_chunks(original_chunks, language)
    key = ("debt_check", language)
    original = catalog.document_texts[key]
    internal = "TECHNICAL_SYSTEM_ONLY. " + INTERNAL_PHRASES[language][0]
    # A new heading is not automatically customer-facing. An allowed heading is
    # also insufficient if its body no longer matches approved catalogue text.
    for variant in ("new_heading", "contaminated_public_heading"):
        if variant == "new_heading":
            section = "New unreviewed customer section"
            catalog.document_texts[key] = original + f"\n\n## {section}\n\n{internal}\n"
        else:
            section = short.section
            catalog.document_texts[key] = original.replace(body(short), internal, 1)
        changed_chunks = build_chunks(catalog)
        chunk = pick(changed_chunks, "debt_check", language, section)
        client = SelectingClient()
        result = await GroundedLLMService(client, catalog).answer(
            debt_question(language), [RetrievalHit(chunk, 0.95)], language=language
        )
        assert_safe_fallback(result, language)
        assert client.envelopes == []
