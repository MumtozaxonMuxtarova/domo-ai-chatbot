"""Telegram routing integration with fake RAG services and no network access."""

import asyncio

import pytest
from aiogram.methods import SendMessage

from app.bot.keyboards import main_menu
from app.bot.texts import TEXTS, Language
from app.llm.service import AnswerResult, Reference, SAFE_FALLBACK
from app.rag.chunking import build_chunks


class FakeRagService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def answer(self, question, *, language):
        self.calls.append((question, language))
        if self.error is not None:
            raise self.error
        return self.result


async def choose_language(harness, language):
    await harness.send("🇺🇿 O‘zbekcha" if language == Language.UZ else "🇷🇺 Русский")


def answered(language, text="DEMO — fixture answer", references=()):
    return AnswerResult(text, str(language), "answered", "grounded_evidence", references)


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize("button_name,expected_id", [
    ("electricity", "electricity_balance"),
    ("payment", "utility_payment"),
    ("delayed_payment", "payment_delay"),
    ("debt", "debt_check"),
    ("utilities", "utility_issue"),
])
async def test_each_faq_keeps_one_exact_static_answer_without_calling_ai(harness, language, button_name, expected_id):
    service = FakeRagService(answered(language, "Must not replace an approved FAQ answer"))
    harness.dispatcher["rag_service"] = service
    await choose_language(harness, language)
    label = getattr(TEXTS[language], button_name)
    assert harness.catalog.find_question(label) == ("faq", expected_id)
    before = len(harness.session.calls)
    await harness.send(label)
    replies = harness.session.calls[before:]
    assert len(replies) == 1
    assert isinstance(replies[0], SendMessage)
    assert replies[0].text == harness.catalog.faq_items[expected_id].answer.text(language)
    assert service.calls == []


@pytest.mark.parametrize("language", list(Language))
async def test_free_text_calls_ai_once_with_saved_language_and_renders_known_sources(harness, language):
    await choose_language(harness, language)
    chunk = next(chunk for chunk in build_chunks(harness.catalog)
                 if chunk.document_id == "electricity_issues" and chunk.language == language
                 and chunk.section in ("Oddiy muammo uchun javob", "Ответ при обычной проблеме"))
    source = harness.catalog.sources["het_contact"]
    reference = Reference(chunk.id, chunk.document_id, chunk.filename, ("het_contact",), (str(source.url),))
    text = "DEMO — tayyor javob." if language == Language.UZ else "DEMO — готовый ответ."
    service = FakeRagService(answered(language, text, (reference,)))
    harness.dispatcher["rag_service"] = service
    question = ("Elektr uzilganda kimga murojaat qilaman?" if language == Language.UZ
                else "Куда обратиться по обычному отключению электричества?")
    opposite_locale = "ru" if language == Language.UZ else "uz"
    before = len(harness.session.calls)
    await harness.send(question, locale=opposite_locale)
    assert service.calls == [(question, language)]
    assert len(harness.session.calls) == before + 1
    assert harness.last.text.startswith(text)
    assert source.title.text(language) in harness.last.text
    assert str(source.url) in harness.last.text
    assert harness.last.reply_markup == main_menu(language)


@pytest.mark.parametrize("language,safety_id,message", [
    (Language.UZ, "gas_leak", "Uyda gaz hidi kelyapti."),
    (Language.RU, "gas_leak", "В квартире пахнет газом."),
    (Language.UZ, "electrical_wire", "Rozetkadan uchqun chiqyapti."),
    (Language.RU, "electrical_wire", "Розетка искрит."),
    (Language.UZ, "fire", "Uyda yong‘in boshlandi."),
    (Language.RU, "fire", "В квартире начался пожар."),
    (Language.UZ, "water_electric", "Suv rozetkaga tegdi."),
    (Language.RU, "water_electric", "Вода попала в розетку."),
])
async def test_clear_safety_messages_bypass_ai_and_return_existing_guidance(harness, language, safety_id, message):
    service = FakeRagService(answered(language, "AI must never delay this safety response"))
    harness.dispatcher["rag_service"] = service
    await choose_language(harness, language)
    before = len(harness.session.calls)
    await harness.send(message)
    assert service.calls == []
    assert len(harness.session.calls) == before + 1
    assert harness.last.text == harness.catalog.format_support("safety", safety_id, language)
    assert harness.last.reply_markup == main_menu(language)


@pytest.mark.parametrize("language", list(Language))
async def test_absent_context_uses_fixed_language_fallback(harness, language):
    await choose_language(harness, language)
    service = FakeRagService(AnswerResult(
        "private-untrusted-fallback-message", str(language), "fallback", "insufficient_context"
    ))
    harness.dispatcher["rag_service"] = service
    before = len(harness.session.calls)
    await harness.send("Boshqa savolim bor" if language == Language.UZ else "У меня другой вопрос")
    assert len(service.calls) == 1
    assert len(harness.session.calls) == before + 1
    assert harness.last.text == SAFE_FALLBACK[language]
    assert "private-untrusted" not in harness.last.text


@pytest.mark.parametrize("failure,language", [
    ("unexpected", Language.UZ), ("timeout", Language.RU), ("rate_limit", Language.UZ),
])
async def test_service_failures_are_safe_and_help_still_works(harness, failure, language, caplog):
    await choose_language(harness, language)
    if failure == "rate_limit":
        service = FakeRagService(AnswerResult(
            "private-rate-limit-detail", str(language), "error", "rate_limit", retry_after=10
        ))
    else:
        error = (RuntimeError("private-unexpected-detail") if failure == "unexpected"
                 else asyncio.TimeoutError("private-timeout-detail"))
        service = FakeRagService(error=error)
    harness.dispatcher["rag_service"] = service
    before = len(harness.session.calls)
    await harness.send("To‘lov haqida tushuntiring" if language == Language.UZ else "Расскажите об оплате")
    assert len(service.calls) == 1
    assert len(harness.session.calls) == before + 1
    assert harness.last.text == TEXTS[language].error
    assert "private-" not in caplog.text
    await harness.send("/help")
    assert harness.last.text == TEXTS[language].help
    assert len(service.calls) == 1


async def test_commands_menus_and_unknown_slash_never_reach_ai(harness):
    language = Language.UZ
    service = FakeRagService(answered(language, "Must not replace static routes"))
    harness.dispatcher["rag_service"] = service
    await choose_language(harness, language)
    labels = [
        "/start", "/help", "/language", "🇺🇿 O‘zbekcha", "/unknown_command",
        TEXTS[language].language, TEXTS[language].help_button, TEXTS[language].operator,
        harness.catalog.support.home_label.text(language),
        harness.catalog.support.safety_menu_label.text(language),
        *(item.question.text(language) for item in harness.catalog.support.utilities),
        *(item.question.text(language) for item in harness.catalog.support.safety),
    ]
    for label in labels:
        before = len(harness.session.calls)
        await harness.send(label)
        assert len(harness.session.calls) == before + 1
        assert service.calls == []


async def test_dispatcher_without_ai_preserves_existing_static_fallback(harness):
    assert harness.dispatcher["rag_service"] is None
    before = len(harness.session.calls)
    await harness.send("Oddiy kommunal ma’lumot kerak.")
    assert len(harness.session.calls) == before + 1
    assert harness.last.text == TEXTS[Language.UZ].fallback


async def test_slow_ai_does_not_block_same_user_help_or_gas_alert(harness):
    language = Language.UZ
    await choose_language(harness, language)
    started = asyncio.Event()
    release = asyncio.Event()

    class SlowService:
        def __init__(self):
            self.calls = []

        async def answer(self, question, *, language):
            self.calls.append((question, language))
            started.set()
            await release.wait()
            return answered(language, "DEMO — slow answer completed")

    service = SlowService()
    harness.dispatcher["rag_service"] = service
    slow_task = asyncio.create_task(harness.send("Kommunal to‘lov haqida batafsil yordam kerak"))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        await asyncio.wait_for(harness.send("/help"), timeout=2)
        assert harness.last.text == TEXTS[language].help
        await asyncio.wait_for(harness.send("Uyda gaz hidi bor"), timeout=2)
        assert harness.last.text == harness.catalog.format_support("safety", "gas_leak", language)
        assert harness.last.reply_markup == main_menu(language)
        assert len(service.calls) == 1
        assert not slow_task.done()
    finally:
        release.set()
        await asyncio.wait_for(slow_task, timeout=2)
    # Do not publish an obsolete ordinary answer after a newer emergency alert.
    assert harness.last.text == harness.catalog.format_support("safety", "gas_leak", language)


async def test_language_switch_during_ai_does_not_restore_obsolete_language_keyboard(harness):
    await choose_language(harness, Language.UZ)
    started, release = asyncio.Event(), asyncio.Event()

    class SlowService:
        async def answer(self, question, *, language):
            assert language == "uz"
            started.set()
            await release.wait()
            return answered(language, "Old Uzbek response must not be delivered")

    harness.dispatcher["rag_service"] = SlowService()
    slow = asyncio.create_task(harness.send("Kommunal to‘lov haqida ma’lumot kerak"))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        await asyncio.wait_for(choose_language(harness, Language.RU), timeout=2)
    finally:
        release.set()
        await asyncio.wait_for(slow, timeout=2)
    assert harness.last.text == TEXTS[Language.RU].fallback
    assert harness.last.reply_markup == main_menu(Language.RU)


@pytest.mark.parametrize("menu_action", ["safety", "faq_five"])
async def test_new_static_menu_response_is_not_overwritten_by_older_ai(harness, menu_action):
    started, release = asyncio.Event(), asyncio.Event()

    class SlowService:
        async def answer(self, question, *, language):
            started.set()
            await release.wait()
            return answered(language, "Obsolete ordinary answer")

    harness.dispatcher["rag_service"] = SlowService()
    slow = asyncio.create_task(harness.send("Kommunal masala haqida savol bermoqchiman"))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        label = (harness.catalog.safety["fire"].question.uz if menu_action == "safety"
                 else TEXTS[Language.UZ].utilities)
        await asyncio.wait_for(harness.send(label), timeout=2)
        static_response = harness.last
        after_menu = len(harness.session.calls)
    finally:
        release.set()
        await asyncio.wait_for(slow, timeout=2)
    assert harness.last is static_response
    assert len(harness.session.calls) == after_menu


@pytest.mark.parametrize("variant", ["unknown_document", "unknown_source", "oversize", "wrong_language"])
async def test_invalid_sources_or_oversize_result_never_leak_to_telegram(harness, variant):
    text = "DEMO — tasdiqlangan javob"
    reference = Reference("test", "electricity_issues", "private-file-path", (), ("https://untrusted.example/",))
    language = "uz"
    if variant == "unknown_document":
        reference = Reference("test", "untrusted_document", "private-file-path", (), ())
    elif variant == "unknown_source":
        reference = Reference("test", "electricity_issues", "private-file-path", ("untrusted_source",), ())
    elif variant == "oversize":
        text = "😀" * 2100  # UTF-16 length, not Python character count.
    else:
        language = "ru"
    harness.dispatcher["rag_service"] = FakeRagService(answered(language, text, (reference,)))
    before = len(harness.session.calls)
    await harness.send("Oddiy kommunal ma’lumot bering")
    assert len(harness.session.calls) == before + 1
    assert harness.last.text in (SAFE_FALLBACK["uz"], TEXTS[Language.UZ].error)
    assert "private-file-path" not in harness.last.text
    assert "untrusted.example" not in harness.last.text
    assert harness.last.parse_mode is None
