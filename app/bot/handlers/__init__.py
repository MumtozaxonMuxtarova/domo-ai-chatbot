"""Static commands/FAQ first; guarded free-text RAG answers last."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, LinkPreviewOptions, Message

from app.bot.keyboards import language_menu, main_menu, safety_menu, utility_menu
from app.bot.safety import detect_safety
from app.bot.texts import CHOOSE_LANGUAGE, LANGUAGE_BUTTONS, TEXTS, Language, default_language
from app.faq import KnowledgeCatalog

if TYPE_CHECKING:
    from app.llm.service import AnswerResult

logger = logging.getLogger(__name__)


async def current_language(message: Message, state: FSMContext) -> Language:
    saved = (await state.get_data()).get("language")
    if saved in (Language.UZ, Language.RU):
        return Language(saved)
    return default_language(message.from_user.language_code if message.from_user else None)


async def start(message: Message, state: FSMContext) -> None:
    language = await current_language(message, state)
    if (await state.get_data()).get("language") not in (Language.UZ, Language.RU):
        await message.answer(CHOOSE_LANGUAGE, reply_markup=language_menu(language))
        return
    await message.answer(TEXTS[language].welcome, reply_markup=main_menu(language))


async def choose_language(message: Message, state: FSMContext) -> None:
    language = await current_language(message, state)
    await message.answer(CHOOSE_LANGUAGE, reply_markup=language_menu(language))


async def save_language(message: Message, state: FSMContext) -> None:
    language = LANGUAGE_BUTTONS[message.text]
    await state.update_data(language=language.value)
    texts = TEXTS[language]
    await message.answer(
        f"{texts.language_saved}\n\n{texts.welcome}", reply_markup=main_menu(language)
    )


async def help_message(message: Message, state: FSMContext) -> None:
    language = await current_language(message, state)
    await message.answer(TEXTS[language].help, reply_markup=main_menu(language))


async def menu_or_text(message: Message, state: FSMContext, faq_catalog: KnowledgeCatalog) -> None:
    language = await current_language(message, state)
    await state.update_data(reply_revision=time.monotonic_ns())
    texts = TEXTS[language]
    # Recognize buttons from both languages after a language switch.
    if message.text in {value.language for value in TEXTS.values()}:
        await choose_language(message, state)
        return
    if message.text in {value.help_button for value in TEXTS.values()}:
        await help_message(message, state)
        return
    if message.text in {faq_catalog.support.home_label.uz, faq_catalog.support.home_label.ru}:
        await message.answer(texts.welcome, reply_markup=main_menu(language))
        return
    if message.text in {faq_catalog.support.safety_menu_label.uz, faq_catalog.support.safety_menu_label.ru}:
        await message.answer(
            faq_catalog.support.safety_intro.text(language), reply_markup=safety_menu(language, faq_catalog)
        )
        return
    if message.text in {value.operator for value in TEXTS.values()}:
        answer = texts.operator_pending
    else:
        match = faq_catalog.find_question(message.text)
        if match is not None:
            group, item_id = match
            if group == "faq":
                answer = faq_catalog.faq_items[item_id].answer.text(language)
                keyboard = utility_menu(language, faq_catalog) if item_id == "utility_issue" else main_menu(language)
            else:
                answer = faq_catalog.format_support(group, item_id, language)
                keyboard = (
                    utility_menu(language, faq_catalog)
                    if group == "utility"
                    else safety_menu(language, faq_catalog)
                )
            await message.answer(
                answer, reply_markup=keyboard, link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
            return
        answer = texts.fallback
    await message.answer(answer, reply_markup=main_menu(language))


async def is_menu_text(message: Message, faq_catalog: KnowledgeCatalog) -> bool:
    text = message.text or ""
    navigation = {
        label for texts in TEXTS.values()
        for label in (texts.language, texts.help_button, texts.operator)
    } | {
        faq_catalog.support.home_label.uz, faq_catalog.support.home_label.ru,
        faq_catalog.support.safety_menu_label.uz, faq_catalog.support.safety_menu_label.ru,
    }
    # Unknown Telegram commands must not be sent to an external model.
    return text.startswith("/") or text in navigation or faq_catalog.find_question(text) is not None


def _ai_text(result: AnswerResult, language: Language, catalog: KnowledgeCatalog) -> str:
    from app.llm.service import SAFE_FALLBACK

    if result.language != language or result.status == "error":
        return TEXTS[language].error
    if result.status != "answered":
        return SAFE_FALLBACK[language]
    # Display only catalogue-owned source titles/URLs, never model-supplied URLs,
    # filesystem paths, retrieval scores, internal reason codes or raw JSON.
    sources = []
    seen = set()
    for reference in result.references:
        document = catalog.documents.get(reference.document_id)
        if document is None:
            return SAFE_FALLBACK[language]
        if document.id not in seen:
            sources.append(document.title.text(language))
            seen.add(document.id)
        for source_id in reference.source_ids:
            if source_id not in document.source_ids or source_id not in catalog.sources:
                return SAFE_FALLBACK[language]
            if source_id not in seen:
                source = catalog.sources[source_id]
                sources.append(f"{source.title.text(language)}\n{source.url}")
                seen.add(source_id)
    heading = "Manbalar:" if language == Language.UZ else "Источники:"
    text = result.text + ("\n\n" + heading + "\n" + "\n".join(sources) if sources else "")
    if len(text.encode("utf-16-le")) // 2 > 4096:
        # Omit optional source decoration, never truncate approved guidance.
        text = result.text
    return text if len(text.encode("utf-16-le")) // 2 <= 4096 else SAFE_FALLBACK[language]


async def free_text(
    message: Message, state: FSMContext, faq_catalog: KnowledgeCatalog, rag_service=None,
) -> None:
    language = await current_language(message, state)
    reply_revision = (await state.get_data()).get("reply_revision")
    safety_id = detect_safety(message.text)
    if safety_id is not None:
        await state.update_data(reply_revision=time.monotonic_ns())
        await message.answer(
            faq_catalog.format_support("safety", safety_id, language),
            reply_markup=main_menu(language), link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return
    text = TEXTS[language].fallback
    if rag_service is not None:
        try:
            from app.llm.service import AnswerResult

            result = await rag_service.answer(message.text, language=language.value)
            if not isinstance(result, AnswerResult):
                raise TypeError("Invalid answer service result")
            text = _ai_text(result, language, faq_catalog)
        except Exception as error:
            logger.warning("Erkin savol bajarilmadi. error_type=%s", type(error).__name__)
            text = TEXTS[language].error
    # Newer menu choices/emergencies take priority over an older ordinary answer.
    # Language changes must not restore an obsolete reply keyboard either.
    if (await state.get_data()).get("reply_revision") != reply_revision:
        return
    latest_language = await current_language(message, state)
    if latest_language != language:
        language = latest_language
        text = TEXTS[language].fallback
    await message.answer(
        text, reply_markup=main_menu(language), parse_mode=None,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def unsupported(message: Message, state: FSMContext) -> None:
    language = await current_language(message, state)
    await message.answer(TEXTS[language].unsupported, reply_markup=main_menu(language))


async def handle_error(event: ErrorEvent, state: FSMContext | None = None) -> bool:
    # Never log the Update or exception message: either may contain personal data.
    logger.error("Xabarni qayta ishlashda xatolik. error_type=%s", type(event.exception).__name__)
    message = event.update.message
    if message is not None and message.chat.type == ChatType.PRIVATE:
        language = default_language(message.from_user.language_code if message.from_user else None)
        if state is not None:
            try:
                language = await current_language(message, state)
            except Exception as error:
                logger.error("Til holatini o'qish xatosi. error_type=%s", type(error).__name__)
        try:
            await message.answer(TEXTS[language].error, reply_markup=main_menu(language))
        except TelegramAPIError as error:
            logger.warning("Xatolik xabarini yetkazib bo'lmadi. error_type=%s", type(error).__name__)
    return True


def build_router() -> Router:
    router = Router(name="foundation")
    # The prototype supports private user conversations only.
    router.message.filter(F.chat.type == ChatType.PRIVATE)
    router.message.register(start, CommandStart())
    router.message.register(help_message, Command("help"))
    router.message.register(choose_language, Command("language"))
    router.message.register(save_language, F.text.in_(tuple(LANGUAGE_BUTTONS)))
    router.message.register(menu_or_text, F.text, is_menu_text)
    router.message.register(free_text, F.text)
    router.message.register(unsupported)
    router.errors.register(handle_error)
    return router
