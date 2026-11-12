"""End-to-end static FAQ journeys through real aiogram dispatching, offline."""

import pytest

from app.bot.texts import TEXTS, Language


async def select_language(harness, language):
    await harness.send("🇺🇿 O‘zbekcha" if language == Language.UZ else "🇷🇺 Русский")


@pytest.mark.parametrize("language", list(Language))
async def test_topic_five_opens_all_four_services_with_operator_last(harness, language):
    await select_language(harness, language)
    await harness.send(TEXTS[language].utilities)
    labels = [button.text for row in harness.last.reply_markup.keyboard for button in row]
    assert all(item.question.text(language) in labels for item in harness.catalog.support.utilities)
    assert harness.catalog.support.safety_menu_label.text(language) in labels
    assert labels[-1] == TEXTS[language].operator
    assert harness.last.text == harness.catalog.faq_items["utility_issue"].answer.text(language)


@pytest.mark.parametrize("language", list(Language))
async def test_all_normal_services_keep_utility_menu_until_safety_button(harness, language):
    await select_language(harness, language)
    for item in harness.catalog.support.utilities:
        await harness.send(item.question.text(language))
        assert harness.last.text == harness.catalog.format_support("utility", item.id, language)
        labels = [button.text for row in harness.last.reply_markup.keyboard for button in row]
        assert all(value.question.text(language) in labels for value in harness.catalog.support.utilities)
        assert harness.catalog.support.safety_menu_label.text(language) in labels
        assert all(value.question.text(language) not in labels for value in harness.catalog.support.safety)
        assert harness.last.reply_markup.is_persistent is True
        assert labels[-1] == TEXTS[language].operator
        await harness.send(harness.catalog.support.safety_menu_label.text(language))
        assert harness.last.text == harness.catalog.support.safety_intro.text(language)
        labels = [button.text for row in harness.last.reply_markup.keyboard for button in row]
        assert all(value.question.text(language) in labels for value in harness.catalog.support.safety)
        assert labels[-1] == TEXTS[language].operator


@pytest.mark.parametrize("language", list(Language))
async def test_safety_journey_returns_immediate_guidance_with_corresponding_sources(harness, language):
    await select_language(harness, language)
    await harness.send(TEXTS[language].utilities)
    await harness.send(harness.catalog.support.safety_menu_label.text(language))
    assert harness.last.text == harness.catalog.support.safety_intro.text(language)
    for item in harness.catalog.support.safety:
        before = len(harness.session.calls)
        await harness.send(item.question.text(language))
        # One direct reply, not a promise or operator acceptance message.
        assert len(harness.session.calls) == before + 1
        assert harness.last.text == harness.catalog.format_support("safety", item.id, language)
        assert harness.last.link_preview_options.is_disabled is True
        for source_id in item.source_ids:
            source = harness.catalog.sources[source_id]
            assert str(source.url) in harness.last.text
            assert source.title.text(language) in harness.last.text
        assert harness.last.reply_markup.keyboard[-1][0].text == TEXTS[language].operator


async def test_switch_language_after_service_selection_and_accept_old_language_button(harness):
    await select_language(harness, Language.UZ)
    await harness.send(harness.catalog.utilities["gas"].question.uz)
    await harness.send("/language")
    await select_language(harness, Language.RU)
    await harness.send(harness.catalog.safety["gas_leak"].question.uz)
    assert harness.last.text == harness.catalog.format_support("safety", "gas_leak", "ru")
    assert harness.last.reply_markup.keyboard[-1][0].text == TEXTS[Language.RU].operator


@pytest.mark.parametrize("language", list(Language))
async def test_back_from_safety_to_services_then_home(harness, language):
    await select_language(harness, language)
    await harness.send(harness.catalog.support.safety_menu_label.text(language))
    await harness.send(TEXTS[language].utilities)
    assert harness.last.text == harness.catalog.faq_items["utility_issue"].answer.text(language)
    await harness.send(harness.catalog.support.home_label.text(language))
    assert harness.last.text == TEXTS[language].welcome
    labels = [button.text for row in harness.last.reply_markup.keyboard for button in row]
    assert all(label in labels for label in TEXTS[language].faq_buttons)


@pytest.mark.parametrize("language", list(Language))
async def test_operator_remains_honest_after_safety_instruction(harness, language):
    await select_language(harness, language)
    await harness.send(harness.catalog.safety["fire"].question.text(language))
    await harness.send(TEXTS[language].operator)
    assert harness.last.text == TEXTS[language].operator_pending


@pytest.mark.parametrize("text", ["gaz sizyapti", "электричество не работает", "Qarzim qancha?"])
async def test_free_text_without_ai_uses_safety_or_honest_fallback(harness, text):
    await harness.send(text)
    expected = (
        harness.catalog.format_support("safety", "gas_leak", "uz")
        if text == "gaz sizyapti" else TEXTS[Language.UZ].fallback
    )
    assert harness.last.text == expected
    assert text not in harness.last.text
