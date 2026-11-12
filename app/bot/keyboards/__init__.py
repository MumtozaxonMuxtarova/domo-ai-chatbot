"""Persistent Telegram keyboards."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.bot.texts import LANGUAGE_BUTTONS, TEXTS, Language
from app.faq import KnowledgeCatalog


def main_menu(language: Language) -> ReplyKeyboardMarkup:
    texts = TEXTS[language]
    rows = [[KeyboardButton(text=label)] for label in texts.faq_buttons]
    rows.append([KeyboardButton(text=texts.language), KeyboardButton(text=texts.help_button)])
    # Keep the operator on the final row, outside the FAQ choices.
    rows.append([KeyboardButton(text=texts.operator)])
    return ReplyKeyboardMarkup(
        keyboard=rows, resize_keyboard=True, is_persistent=True, one_time_keyboard=False,
        input_field_placeholder=texts.placeholder,
    )


def language_menu(language: Language) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=label) for label in LANGUAGE_BUTTONS],
            [KeyboardButton(text=TEXTS[language].operator)],
        ],
        resize_keyboard=True, is_persistent=True, one_time_keyboard=False,
    )


def _navigation(language: Language, catalog: KnowledgeCatalog) -> list[list[KeyboardButton]]:
    texts = TEXTS[language]
    return [
        [KeyboardButton(text=catalog.support.home_label.text(language))],
        [KeyboardButton(text=texts.language), KeyboardButton(text=texts.help_button)],
        [KeyboardButton(text=texts.operator)],
    ]


def utility_menu(language: Language, catalog: KnowledgeCatalog) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=item.question.text(language))] for item in catalog.support.utilities]
    rows.append([KeyboardButton(text=catalog.support.safety_menu_label.text(language))])
    return ReplyKeyboardMarkup(
        keyboard=rows + _navigation(language, catalog), resize_keyboard=True,
        is_persistent=True, one_time_keyboard=False,
    )


def safety_menu(language: Language, catalog: KnowledgeCatalog) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=item.question.text(language))] for item in catalog.support.safety]
    rows.append([KeyboardButton(text=TEXTS[language].utilities)])
    return ReplyKeyboardMarkup(
        keyboard=rows + _navigation(language, catalog), resize_keyboard=True,
        is_persistent=True, one_time_keyboard=False,
    )
