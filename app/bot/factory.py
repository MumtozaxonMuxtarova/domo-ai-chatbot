"""Construct fresh bot components; no network calls at import time."""

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import DisabledEventIsolation, MemoryStorage

from app.bot.handlers import build_router
from app.bot.texts import TEXTS
from app.config import Settings
from app.faq import KnowledgeBaseError, KnowledgeCatalog, load_catalog


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token.get_secret_value(),
        session=AiohttpSession(timeout=settings.request_timeout),
    )


def create_dispatcher(catalog: KnowledgeCatalog | None = None, *, rag_service=None) -> Dispatcher:
    content = load_catalog() if catalog is None else catalog
    # Fail early if main-menu labels no longer correspond to approved FAQ entries.
    for texts in TEXTS.values():
        for label in texts.faq_buttons:
            match = content.find_question(label)
            if match is None or match[0] != "faq":
                raise KnowledgeBaseError("Asosiy menyudagi FAQ uchun tasdiqlangan javob topilmadi.")
    dispatcher = Dispatcher(
        # MemoryStorage updates these simple language/safety markers without I/O.
        # Do not lock a user's /help or safety alert behind an API await.
        storage=MemoryStorage(), events_isolation=DisabledEventIsolation(),
        faq_catalog=content, rag_service=rag_service,
    )
    dispatcher.include_router(build_router())
    return dispatcher
