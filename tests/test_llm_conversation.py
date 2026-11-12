"""Natural utility-only conversation with a fake model and canonical evidence."""

import json

import pytest

from app.faq import load_catalog
from app.llm.service import (
    CLARIFICATION_TEXT,
    CONVERSATION_TEXT,
    DEMO_PREFIX,
    SAFE_FALLBACK,
    GroundedLLMService,
)
from app.rag.chunking import build_chunks
from app.rag.retrieval import RetrievalHit


class DecisionClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        return json.dumps(self.payload, ensure_ascii=False)


@pytest.fixture
def knowledge():
    catalog = load_catalog()
    return catalog, build_chunks(catalog)


def pick(chunks, document_id, language, kind="short"):
    sections = {
        "short": ("Tasdiqlangan qisqa javob", "Утверждённый краткий ответ"),
        "ordinary": ("Oddiy muammo uchun javob", "Ответ при обычной проблеме"),
        "safety": ("Xavfsizlik javobi", "Ответ по безопасности"),
    }
    return next(chunk for chunk in chunks if chunk.document_id == document_id
                and chunk.language == language and chunk.section.startswith(sections[kind]))


def body(chunk):
    return chunk.text.split("\n\n", 1)[1]


def payload(mode, language, answer="MODEL_TEXT_MUST_NOT_BE_FORWARDED", *, chunk=None, clarification="none"):
    return {
        "mode": mode, "language": language, "answer": answer, "clarification": clarification,
        "evidence": [{"chunk_id": chunk.id, "quote": body(chunk)}] if chunk is not None else [],
    }


def assert_fallback(result, language):
    assert result.status == "fallback"
    assert result.language == language
    assert result.text == SAFE_FALLBACK[language]
    assert result.references == ()


QUESTIONS = {
    "greeting": {"uz": "Assalomu alaykum!", "ru": "Здравствуйте!"},
    "thanks": {"uz": "Rahmat, tushundim.", "ru": "Спасибо, всё понятно."},
    "clarify": {"uz": "Kommunal xizmat bo‘yicha muammo bor.", "ru": "У меня проблема с коммунальными услугами."},
    "account_unavailable": {"uz": "Mening haqiqiy qarzim qancha?", "ru": "Сколько я должен по своему реальному счёту?"},
    "insufficient_context": {"uz": "Bu xizmatning aniq ish vaqti qanday?", "ru": "Какой точный график работы этой службы?"},
    "out_of_scope": {"uz": "Shokoladli tort qanday tayyorlanadi?", "ru": "Как приготовить шоколадный торт?"},
}


@pytest.mark.parametrize("language", ["uz", "ru"])
@pytest.mark.parametrize("mode", list(QUESTIONS))
async def test_empty_context_still_classifies_and_renders_fixed_conversation_modes(knowledge, language, mode):
    catalog, _ = knowledge
    client = DecisionClient(payload(
        mode, language, clarification="service" if mode == "clarify" else "none"
    ))
    result = await GroundedLLMService(client, catalog).answer(
        QUESTIONS[mode][language], [], language=language
    )
    assert len(client.calls) == (0 if mode == "account_unavailable" else 1)
    assert result.language == language
    assert result.references == ()
    assert "MODEL_TEXT_MUST_NOT_BE_FORWARDED" not in result.text
    if mode == "clarify":
        assert result.text == CLARIFICATION_TEXT["service"][language]
    elif mode == "insufficient_context":
        assert_fallback(result, language)
    else:
        assert result.text == CONVERSATION_TEXT[mode][language]
    if mode != "insufficient_context":
        assert result.status == "answered"
        assert result.reason == mode


@pytest.mark.parametrize("language,answer", [
    ("uz", "Kommunal to‘lovni ta’minotchingiz tasdiqlagan kanal orqali qiling. "
     "Xizmat turi, hisob raqami va summani tekshirib, chekni saqlang. "
     "Men pul qabul qilmayman va to‘lov o‘tkazmayman."),
    ("ru", "Оплачивайте коммунальные услуги через канал, подтверждённый поставщиком. "
     "Сверьте услугу, лицевой счёт и сумму и сохраните чек. "
     "Я не принимаю деньги и не провожу платежи."),
])
async def test_grounded_payment_answer_can_be_natural_without_copying_the_quote(knowledge, language, answer):
    catalog, chunks = knowledge
    chunk = pick(chunks, "utility_payments", language)
    assert answer != body(chunk)
    client = DecisionClient(payload("grounded", language, answer, chunk=chunk))
    result = await GroundedLLMService(client, catalog).answer(
        "To‘lovni qanday qilaman?" if language == "uz" else "Как произвести оплату?",
        [RetrievalHit(chunk, 0.95)], language=language,
    )
    assert result.status == "answered"
    assert result.language == language
    assert result.text.startswith(DEMO_PREFIX[language])
    assert result.text[len(DEMO_PREFIX[language]):].lstrip("\n") == answer
    assert len(result.references) == 1
    assert result.references[0].chunk_id == chunk.id
    assert result.references[0].document_id == "utility_payments"


@pytest.mark.parametrize("language,paraphrase", [
    ("uz", "Mutaxassisga murojaat qiling."), ("ru", "Обратитесь к специалисту."),
])
async def test_safety_answer_ignores_shortened_paraphrase_and_keeps_complete_instructions(knowledge, language, paraphrase):
    catalog, chunks = knowledge
    chunk = pick(chunks, "gas_issues", language, "safety")
    client = DecisionClient(payload("grounded", language, paraphrase, chunk=chunk))
    result = await GroundedLLMService(client, catalog).answer(
        "Gaz hidi bo‘lsa nima qilaman?" if language == "uz" else "Что делать при запахе газа?",
        [RetrievalHit(chunk, 0.95)], language=language,
    )
    assert result.status == "answered"
    assert result.text.startswith(DEMO_PREFIX[language])
    assert result.text[len(DEMO_PREFIX[language]):].lstrip("\n") == body(chunk)
    assert "104" in result.text and "112" in result.text
    assert result.references[0].source_ids == chunk.source_ids


@pytest.mark.parametrize("language,fabricated", [
    ("uz", "Balansingiz 1154 so‘m."), ("ru", "Ваш баланс 1154 сум."),
])
async def test_sourced_contact_number_cannot_be_reused_as_real_account_balance(knowledge, language, fabricated):
    catalog, chunks = knowledge
    chunk = pick(chunks, "electricity_issues", language, "ordinary")
    assert "1154" in body(chunk)
    client = DecisionClient(payload("grounded", language, fabricated, chunk=chunk))
    result = await GroundedLLMService(client, catalog).answer(
        "Elektr bo‘yicha kimga murojaat qilaman?" if language == "uz" else "Куда обратиться по электричеству?",
        [RetrievalHit(chunk, 0.95)], language=language,
    )
    assert_fallback(result, language)
    assert fabricated not in result.text


@pytest.mark.parametrize("fabricated", [
    "Tarif 987654 so‘m.",
    "To‘lash uchun https://example.com/pay manziliga kiring.",
    "```python\nDispatcher(document_id='utility_payments')\n```",
    "To‘lovingiz tasdiqlandi.",
    "Gaz ertaga keladi.",
])
async def test_valid_evidence_does_not_authorize_invented_numbers_urls_or_internal_code(knowledge, fabricated):
    catalog, chunks = knowledge
    chunk = pick(chunks, "utility_payments", "uz")
    client = DecisionClient(payload("grounded", "uz", fabricated, chunk=chunk))
    result = await GroundedLLMService(client, catalog).answer(
        "Kommunal to‘lov tartibini tushuntiring", [RetrievalHit(chunk, 0.95)], language="uz"
    )
    assert_fallback(result, "uz")
    assert "987654" not in result.text
    assert "example.com" not in result.text
    assert "Dispatcher" not in result.text


async def test_russian_time_promise_is_not_confused_with_payment_through_a_channel(knowledge):
    catalog, chunks = knowledge
    chunk = pick(chunks, "utility_payments", "ru")
    client = DecisionClient(payload("grounded", "ru", "Воду включат через три дня.", chunk=chunk))
    result = await GroundedLLMService(client, catalog).answer(
        "Когда включат воду?", [RetrievalHit(chunk, 0.95)], language="ru",
    )
    assert_fallback(result, "ru")


@pytest.mark.parametrize("language,wrong_text", [
    ("uz", "Use the official payment channel and keep your receipt."),
    ("ru", "Для оплаты use the official payment channel and keep your receipt."),
])
async def test_model_language_tag_does_not_authorize_obviously_wrong_language(knowledge, language, wrong_text):
    catalog, chunks = knowledge
    chunk = pick(chunks, "utility_payments", language)
    client = DecisionClient(payload("grounded", language, wrong_text, chunk=chunk))
    result = await GroundedLLMService(client, catalog).answer(
        "To‘lov haqida ayting" if language == "uz" else "Расскажите об оплате",
        [RetrievalHit(chunk, 0.95)], language=language,
    )
    assert_fallback(result, language)


@pytest.mark.parametrize("language", ["uz", "ru"])
@pytest.mark.parametrize("kind", ["short", "safety"])
async def test_id_only_evidence_uses_canonical_source_without_model_recopying(knowledge, language, kind):
    catalog, chunks = knowledge
    chunk = pick(chunks, "utility_payments" if kind == "short" else "gas_issues", language, kind)
    decision = payload("grounded", language, body(chunk), chunk=chunk)
    decision["evidence"] = [{"chunk_id": chunk.id}]
    result = await GroundedLLMService(DecisionClient(decision), catalog).answer(
        "Kommunal savol" if language == "uz" else "Коммунальный вопрос",
        [RetrievalHit(chunk, 0.95)], language=language,
    )
    assert result.status == "answered"
    assert result.references[0].chunk_id == chunk.id
    assert result.text == DEMO_PREFIX[language] + "\n\n" + body(chunk)


@pytest.mark.parametrize("bad_quote", [None, ""])
async def test_present_legacy_quote_must_not_bypass_validation_with_null_or_empty(knowledge, bad_quote):
    catalog, chunks = knowledge
    chunk = pick(chunks, "utility_payments", "uz")
    decision = payload("grounded", "uz", body(chunk), chunk=chunk)
    decision["evidence"][0]["quote"] = bad_quote
    result = await GroundedLLMService(DecisionClient(decision), catalog).answer(
        "To‘lov haqida ayting", [RetrievalHit(chunk, 0.95)], language="uz",
    )
    assert_fallback(result, "uz")


@pytest.mark.parametrize("language,question", [
    ("uz", "Mening elektr bo‘yicha qarzim hozir qancha?"),
    ("uz", "Hisobimda qancha pul bor?"),
    ("uz", "Qarzim qancha?"),
    ("ru", "Сколько я должен за электричество?"),
    ("ru", "Какой у меня баланс?"),
])
async def test_actual_account_amount_gets_honest_answer_without_model_or_redundant_question(knowledge, language, question):
    catalog, _ = knowledge
    client = DecisionClient(payload("grounded", language, "Unsupported account assertion"))
    result = await GroundedLLMService(client, catalog).answer(question, [], language=language)
    assert result.text == CONVERSATION_TEXT["account_unavailable"][language]
    assert result.status == "answered"
    assert result.reason == "account_unavailable"
    assert "?" not in result.text
    assert client.calls == []


@pytest.mark.parametrize("language,question", [
    ("uz", "Qarzimni qanday tekshiraman?"),
    ("ru", "Как проверить мой баланс?"),
])
async def test_how_to_check_account_is_not_mistaken_for_a_live_account_lookup(knowledge, language, question):
    catalog, chunks = knowledge
    chunk = pick(chunks, "debt_check", language)
    client = DecisionClient(payload("grounded", language, body(chunk), chunk=chunk))
    result = await GroundedLLMService(client, catalog).answer(question, [RetrievalHit(chunk, 0.95)], language=language)
    assert result.status == "answered"
    assert result.reason == "grounded_evidence"
    assert len(client.calls) == 1


async def test_grounded_mode_without_evidence_is_rejected(knowledge):
    catalog, chunks = knowledge
    chunk = pick(chunks, "utility_payments", "uz")
    client = DecisionClient(payload("grounded", "uz", "To‘lov bo‘yicha tayyor javob."))
    result = await GroundedLLMService(client, catalog).answer(
        "To‘lov haqida ayting", [RetrievalHit(chunk, 0.95)], language="uz"
    )
    assert_fallback(result, "uz")


async def test_non_grounded_mode_must_not_smuggle_evidence(knowledge):
    catalog, chunks = knowledge
    chunk = pick(chunks, "utility_payments", "uz")
    client = DecisionClient(payload("greeting", "uz", chunk=chunk))
    result = await GroundedLLMService(client, catalog).answer(
        "Salom", [RetrievalHit(chunk, 0.95)], language="uz"
    )
    assert_fallback(result, "uz")


@pytest.mark.parametrize("mode,clarification", [("clarify", "none"), ("greeting", "service")])
async def test_mode_and_clarification_type_must_be_consistent(knowledge, mode, clarification):
    catalog, _ = knowledge
    client = DecisionClient(payload(mode, "uz", clarification=clarification))
    result = await GroundedLLMService(client, catalog).answer(
        "Kommunal xizmat bo‘yicha savolim bor", [], language="uz"
    )
    assert_fallback(result, "uz")
