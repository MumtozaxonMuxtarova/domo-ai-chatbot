"""Lifecycle adapter for the existing local retriever and Groq answer service."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.faq import KnowledgeCatalog
from app.rag.chunking import build_chunks
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.errors import RetrievalError
from app.rag.retrieval import Retriever
from app.rag.settings import load_rag_settings

if TYPE_CHECKING:
    from app.llm import AnswerResult

logger = logging.getLogger(__name__)


class TelegramAI:
    def __init__(self, pipeline, client, *, timeout_seconds: float = 30):
        self.pipeline = pipeline
        self.client = client
        self.timeout_seconds = timeout_seconds
        self._slot = asyncio.Semaphore(1)
        self._tasks: set[asyncio.Task] = set()
        self._closed = False

    @staticmethod
    def _error(language: str, reason: str) -> AnswerResult:
        from app.llm.service import AnswerResult, SAFE_FALLBACK

        return AnswerResult(SAFE_FALLBACK[language], language, "error", reason)

    async def _execute(self, question, language):
        try:
            return await self.pipeline.answer(question, language=language)
        except Exception as error:
            logger.warning("AI javobi bajarilmadi. error_type=%s", type(error).__name__)
            return self._error(language, "service_error")
        finally:
            self._slot.release()

    async def answer(self, question: str, *, language: str) -> AnswerResult:
        if self._closed or self._slot.locked():
            return self._error(language, "busy")
        await self._slot.acquire()
        task = asyncio.create_task(self._execute(question, language))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        try:
            # A timed-out embedding thread cannot be killed. Its task keeps the
            # slot until it really finishes, so more CPU jobs cannot accumulate.
            return await asyncio.wait_for(asyncio.shield(task), timeout=self.timeout_seconds)
        except TimeoutError:
            return self._error(language, "timeout")

    async def aclose(self):
        self._closed = True
        try:
            if self._tasks:
                tasks = tuple(self._tasks)
                _, pending = await asyncio.wait(tasks, timeout=min(5, self.timeout_seconds))
                for task in pending:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await self.client.aclose()


def _local_retriever(catalog: KnowledgeCatalog):
    settings = load_rag_settings()
    if not settings.cache_path.is_dir() or not (settings.chroma_path / "chroma.sqlite3").is_file():
        raise RetrievalError("Mavjud model keshi yoki lokal indeks topilmadi.")
    embedder = SentenceTransformerEmbedder(settings, allow_download=False)
    chunks = build_chunks(catalog, token_counter=embedder.token_count)
    retriever = Retriever(chunks, embedder, settings.chroma_path, min_score=settings.min_score)
    retriever._open_index()  # Validate the existing snapshot; never build/reindex.
    return retriever, embedder.token_count, settings.min_score


async def create_ai_runtime(catalog: KnowledgeCatalog) -> TelegramAI | None:
    client = None
    try:
        # Optional AI dependencies must not prevent the FAQ-only bot from starting.
        from app.llm import GroqClient, GroundedLLMService, RagAnswerService, load_llm_settings

        settings = load_llm_settings()
        retriever, token_counter, min_score = await asyncio.to_thread(_local_retriever, catalog)
        client = GroqClient(settings, allow_live_api=True)
        grounded = GroundedLLMService(client, catalog, min_score=min_score, token_counter=token_counter)
        return TelegramAI(
            RagAnswerService(retriever, grounded), client,
            timeout_seconds=settings.timeout_seconds + 10,
        )
    except Exception as error:
        if client is not None:
            await client.aclose()
        logger.warning("AI tayyorlanmadi; FAQ ishlashda davom etadi. error_type=%s", type(error).__name__)
        return None
