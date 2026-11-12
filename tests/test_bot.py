import pytest
from aiogram.methods import SendMessage
from aiogram.types import PhotoSize

from app.bot.keyboards import main_menu
from app.bot.texts import CHOOSE_LANGUAGE, LANGUAGE_BUTTONS, TEXTS, Language


@pytest.mark.parametrize("language", list(Language))
def test_persistent_main_menu_operator_is_last(language):
    keyboard = main_menu(language)
    labels = [button.text for row in keyboard.keyboard for button in row]
    assert keyboard.is_persistent is True
    assert keyboard.one_time_keyboard is False
    assert labels[-1] == TEXTS[language].operator
    assert all(button in labels for button in TEXTS[language].faq_buttons)
    assert TEXTS[language].language in labels


async def test_start_offers_explicit_language_choice(harness):
    await harness.send("/start")
    assert harness.last.text == CHOOSE_LANGUAGE
    labels = [button.text for row in harness.last.reply_markup.keyboard for button in row]
    assert all(label in labels for label in LANGUAGE_BUTTONS)
    assert labels[-1] == TEXTS[Language.UZ].operator


@pytest.mark.parametrize("label,language", LANGUAGE_BUTTONS.items())
async def test_language_selection_and_start_remember_choice(harness, label, language):
    await harness.send(label)
    assert TEXTS[language].language_saved in harness.last.text
    await harness.send("/start", locale="en")
    assert harness.last.text == TEXTS[language].welcome
    assert harness.last.reply_markup.keyboard[-1][0].text == TEXTS[language].operator


async def test_language_can_be_changed_and_is_isolated_between_users(harness):
    await harness.send("🇷🇺 Русский", user_id=101)
    await harness.send("🇺🇿 O‘zbekcha", user_id=202)
    await harness.send("/help", user_id=101)
    assert harness.last.text == TEXTS[Language.RU].help
    await harness.send("/help", user_id=202)
    assert harness.last.text == TEXTS[Language.UZ].help
    await harness.send("/language", user_id=101)
    assert harness.last.text == CHOOSE_LANGUAGE
    await harness.send("🇺🇿 O‘zbekcha", user_id=101)
    await harness.send("/help", user_id=101, locale="ru")
    assert harness.last.text == TEXTS[Language.UZ].help


@pytest.mark.parametrize("language", list(Language))
async def test_language_and_help_menu_buttons(harness, language):
    await harness.send(next(label for label, lang in LANGUAGE_BUTTONS.items() if lang == language))
    await harness.send(TEXTS[language].language)
    assert harness.last.text == CHOOSE_LANGUAGE
    await harness.send(TEXTS[language].help_button)
    assert harness.last.text == TEXTS[language].help


@pytest.mark.parametrize("language", list(Language))
async def test_faq_buttons_return_approved_answers(harness, language):
    await harness.send(next(label for label, lang in LANGUAGE_BUTTONS.items() if lang == language))
    for label in TEXTS[language].faq_buttons:
        await harness.send(label)
        match = harness.catalog.find_question(label)
        assert match is not None
        assert harness.last.text == harness.catalog.faq_items[match[1]].answer.text(language)


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize("button_name,expected_id", [
    ("electricity", "electricity_balance"),
    ("payment", "utility_payment"),
    ("delayed_payment", "payment_delay"),
    ("debt", "debt_check"),
    ("utilities", "utility_issue"),
])
async def test_each_faq_sends_exactly_one_matching_approved_answer(harness, language, button_name, expected_id):
    await harness.send("🇺🇿 O‘zbekcha" if language == Language.UZ else "🇷🇺 Русский")
    button_text = getattr(TEXTS[language], button_name)
    assert harness.catalog.find_question(button_text) == ("faq", expected_id)
    expected_item = harness.catalog.faq_items[expected_id]
    assert expected_item.status == "approved"
    expected_text = expected_item.answer.text(language)
    # FAQ 1–4 already have independent exact-text contracts in test_faq.py.
    # Pin the user's approved FAQ 5 as well, independently of the live catalogue.
    if expected_id == "utility_issue":
        approved_five = {
            Language.UZ: "Qaysi xizmatda muammo bor: elektr, gaz, suv yoki isitish?\n\n"
            "Agar xavfli belgilar bo‘lmasa, viloyat/tumaningizni, muammo boshlangan vaqtni va u "
            "faqat xonadoningizdami yoki boshqa joylarda ham kuzatilayotganini yozing.\n\n"
            "Men uzilish sababini yoki xizmat tiklanish vaqtini ko‘ra olmayman. "
            "Mavjud tasdiqlangan ma’lumot asosida keyingi qadamni tushuntiraman.",
            Language.RU: "С какой услугой возникла проблема: электричество, газ, вода или отопление?\n\n"
            "Если опасных признаков нет, укажите область/район, время возникновения проблемы и наблюдается "
            "ли она только в вашей квартире или также в других местах.\n\n"
            "Я не вижу причину отключения или время восстановления услуги. "
            "Я объясню следующий шаг на основе имеющейся подтверждённой информации.",
        }
        assert expected_text == approved_five[language]

    before = len(harness.session.calls)
    await harness.send(button_text)
    new_calls = harness.session.calls[before:]
    assert len(new_calls) == 1
    response = new_calls[0]
    assert isinstance(response, SendMessage)
    assert response.chat_id == 101
    assert response.text == expected_text


@pytest.mark.parametrize("language", list(Language))
async def test_operator_button_does_not_pretend_to_create_ticket(harness, language):
    await harness.send(next(label for label, lang in LANGUAGE_BUTTONS.items() if lang == language))
    await harness.send(TEXTS[language].operator)
    assert harness.last.text == TEXTS[language].operator_pending
    assert len(harness.session.calls) == 2


@pytest.mark.parametrize("text", ["Salom", "Мой вопрос", "/unknown", "<script>private-text</script>"])
async def test_unknown_text_has_safe_fallback_without_echo(harness, text):
    await harness.send(text)
    assert harness.last.text == TEXTS[Language.UZ].fallback
    assert text not in harness.last.text


async def test_telegram_russian_locale_is_used_before_selection(harness):
    await harness.send("/help", locale="ru-RU")
    assert harness.last.text == TEXTS[Language.RU].help


async def test_non_text_update_has_friendly_fallback(harness):
    await harness.send(photo=[PhotoSize(file_id="demo", file_unique_id="demo", width=1, height=1)])
    assert harness.last.text == TEXTS[Language.UZ].unsupported


async def test_group_messages_are_ignored(harness):
    await harness.send("/start", chat_type="group")
    assert harness.session.calls == []


async def test_send_failure_produces_localized_error_without_leaking_details(harness, caplog):
    await harness.send("🇷🇺 Русский")
    harness.session.failures_remaining = 1
    await harness.send("private-user-message")
    assert harness.last.text == TEXTS[Language.RU].error
    assert "private-user-message" not in caplog.text
    assert "private-error-content" not in caplog.text


async def test_error_notification_failure_is_logged_without_crashing(harness, caplog):
    harness.session.failures_remaining = 2
    await harness.send("private-user-message")
    assert len(harness.session.calls) == 2
    assert "TelegramNetworkError" in caplog.text
    assert "private-error-content" not in caplog.text
