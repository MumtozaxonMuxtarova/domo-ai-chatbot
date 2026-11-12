"""Telegram AI lifecycle tests with in-memory fakes and no external services."""

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

import app.llm as llm
from app.bot import ai
from app.llm import AnswerResult
from app.llm.errors import LLMConfigurationError
from app.llm.service import SAFE_FALLBACK
from app.llm.settings import LLMSettings
from app.rag.errors import RetrievalError


class FakeClient:
    def __init__(self):
        self.close_calls = 0
        self.complete_calls = 0

    async def complete(self, messages):
        self.complete_calls += 1
        raise AssertionError("Runtime construction must never request a completion")

    async def aclose(self):
        self.close_calls += 1


def answered(language):
    return AnswerResult("Tasdiqlangan javob" if language == "uz" else "Подтверждённый ответ",
                        language, "answered", "grounded_evidence")


def assert_safe_error(result, language, reason):
    assert result.text == SAFE_FALLBACK[language]
    assert result.language == language
    assert result.status == "error"
    assert result.reason == reason
    assert result.references == ()


@pytest.mark.parametrize("language,question", [
    ("uz", "To‘lovim hisobda ko‘rinmasa nima qilaman?"),
    ("ru", "Как проверить задолженность?"),
])
async def test_runtime_preserves_question_language_and_verified_result(language, question):
    expected = answered(language)
    calls = []

    class Pipeline:
        async def answer(self, question, *, language):
            calls.append((question, language))
            return expected

    client = FakeClient()
    runtime = ai.TelegramAI(Pipeline(), client)
    try:
        assert await runtime.answer(question, language=language) is expected
        assert calls == [(question, language)]
        assert client.complete_calls == 0
    finally:
        await runtime.aclose()
    assert client.close_calls == 1


async def test_concurrent_question_returns_busy_without_starting_another_pipeline_call():
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    class Pipeline:
        async def answer(self, question, *, language):
            calls.append((question, language))
            started.set()
            await release.wait()
            return answered(language)

    runtime = ai.TelegramAI(Pipeline(), FakeClient())
    first = asyncio.create_task(runtime.answer("Birinchi savol", language="uz"))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        result = await asyncio.wait_for(runtime.answer("Второй вопрос", language="ru"), timeout=1)
        assert_safe_error(result, "ru", "busy")
        assert calls == [("Birinchi savol", "uz")]
        release.set()
        assert (await first).status == "answered"
    finally:
        release.set()
        await first
        await runtime.aclose()


async def test_timeout_keeps_slot_busy_until_existing_work_really_finishes():
    started, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = []

    class Pipeline:
        async def answer(self, question, *, language):
            calls.append((question, language))
            if len(calls) == 1:
                started.set()
                try:
                    await release.wait()
                finally:
                    finished.set()
            return answered(language)

    runtime = ai.TelegramAI(Pipeline(), FakeClient(), timeout_seconds=0.02)
    first = asyncio.create_task(runtime.answer("Sekin savol", language="uz"))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        assert_safe_error(await first, "uz", "timeout")
        assert not finished.is_set()
        assert_safe_error(await runtime.answer("Ещё вопрос", language="ru"), "ru", "busy")
        assert len(calls) == 1
        release.set()
        await asyncio.wait_for(finished.wait(), timeout=1)
        assert (await runtime.answer("Yangi savol", language="uz")).status == "answered"
        assert calls == [("Sekin savol", "uz"), ("Yangi savol", "uz")]
    finally:
        release.set()
        await first
        await runtime.aclose()


async def test_pipeline_failure_hides_details_and_releases_slot_for_next_question(caplog):
    calls = []

    class Pipeline:
        async def answer(self, question, *, language):
            calls.append((question, language))
            if len(calls) == 1:
                raise RuntimeError("private-key-and-context")
            return answered(language)

    runtime = ai.TelegramAI(Pipeline(), FakeClient())
    try:
        result = await runtime.answer("private-question", language="ru")
        assert_safe_error(result, "ru", "service_error")
        assert (await runtime.answer("Keyingi savol", language="uz")).status == "answered"
        assert "RuntimeError" in caplog.text
        assert "private-key-and-context" not in caplog.text
        assert "private-question" not in caplog.text
    finally:
        await runtime.aclose()


async def test_close_waits_for_active_work_then_closes_client_and_rejects_new_work():
    started, release = asyncio.Event(), asyncio.Event()

    class Pipeline:
        async def answer(self, question, *, language):
            started.set()
            await release.wait()
            return answered(language)

    client = FakeClient()
    runtime = ai.TelegramAI(Pipeline(), client)
    first = asyncio.create_task(runtime.answer("Savol", language="uz"))
    close = None
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        close = asyncio.create_task(runtime.aclose())
        await asyncio.sleep(0)  # Let shutdown mark the runtime closed.
        assert not close.done()
        assert client.close_calls == 0
        assert_safe_error(await runtime.answer("Новый вопрос", language="ru"), "ru", "busy")
        release.set()
        assert (await first).status == "answered"
        await asyncio.wait_for(close, timeout=1)
        assert client.close_calls == 1
        assert_safe_error(await runtime.answer("Yana savol", language="uz"), "uz", "busy")
    finally:
        release.set()
        await first
        if close is not None:
            await close
        else:
            await runtime.aclose()


async def test_close_cancels_stalled_worker_after_bounded_wait_and_closes_client():
    started, release, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class Pipeline:
        async def answer(self, question, *, language):
            started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return answered(language)

    client = FakeClient()
    runtime = ai.TelegramAI(Pipeline(), client, timeout_seconds=0.02)
    waiter = asyncio.create_task(runtime.answer("Sekin savol", language="uz"))
    closed = False
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        # Cancelling the caller leaves its shielded worker for runtime cleanup.
        waiter.cancel()
        outcome = await asyncio.gather(waiter, return_exceptions=True)
        assert isinstance(outcome[0], asyncio.CancelledError)
        assert not cancelled.is_set()
        await asyncio.wait_for(runtime.aclose(), timeout=1)
        closed = True
        assert cancelled.is_set()
        assert not release.is_set()
        assert client.close_calls == 1
        assert_safe_error(await runtime.answer("Yangi savol", language="uz"), "uz", "busy")
    finally:
        release.set()
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)
        if not closed:
            await runtime.aclose()


@pytest.fixture
def runtime_factory(monkeypatch):
    settings = LLMSettings(api_key=SecretStr("offline-test-key"), model="offline-test-model",
                           timeout_seconds=12)
    catalog, retriever, grounded, pipeline = object(), object(), object(), object()
    client = FakeClient()
    calls = []

    def load_settings():
        calls.append(("settings",))
        return settings

    def local_retriever(content):
        calls.append(("local", content))
        return retriever, None, 0.8

    async def run_inline(function, *args):
        calls.append(("worker", function, args))
        return function(*args)

    def client_factory(config, *, allow_live_api):
        calls.append(("client", config, allow_live_api))
        return client

    def grounded_factory(completion_client, content, *, min_score, token_counter):
        calls.append(("grounded", completion_client, content, min_score, token_counter))
        return grounded

    def pipeline_factory(local, llm):
        calls.append(("pipeline", local, llm))
        return pipeline

    monkeypatch.setattr(llm, "load_llm_settings", load_settings)
    monkeypatch.setattr(ai, "_local_retriever", local_retriever)
    monkeypatch.setattr(ai.asyncio, "to_thread", run_inline)
    monkeypatch.setattr(llm, "GroqClient", client_factory)
    monkeypatch.setattr(llm, "GroundedLLMService", grounded_factory)
    monkeypatch.setattr(llm, "RagAnswerService", pipeline_factory)
    return SimpleNamespace(settings=settings, catalog=catalog, retriever=retriever,
                           grounded=grounded, pipeline=pipeline, client=client, calls=calls,
                           local_retriever=local_retriever)


async def test_factory_connects_existing_dependencies_without_startup_api_request(runtime_factory):
    fake = runtime_factory
    runtime = await ai.create_ai_runtime(fake.catalog)
    assert isinstance(runtime, ai.TelegramAI)
    try:
        assert runtime.pipeline is fake.pipeline
        assert runtime.client is fake.client
        assert runtime.timeout_seconds == 22
        assert fake.calls == [
            ("settings",),
            ("worker", fake.local_retriever, (fake.catalog,)),
            ("local", fake.catalog),
            ("client", fake.settings, True),
            ("grounded", fake.client, fake.catalog, 0.8, None),
            ("pipeline", fake.retriever, fake.grounded),
        ]
        assert fake.client.complete_calls == 0
    finally:
        await runtime.aclose()
    assert fake.client.close_calls == 1


@pytest.mark.parametrize("stage", ["settings", "retriever"])
async def test_factory_failure_before_client_keeps_faq_available_and_hides_details(
    monkeypatch, runtime_factory, caplog, stage,
):
    fake = runtime_factory

    def fail(*args):
        if stage == "settings":
            raise LLMConfigurationError("private-configuration")
        raise RetrievalError("private-model-or-index-path")

    if stage == "settings":
        monkeypatch.setattr(llm, "load_llm_settings", fail)
    else:
        monkeypatch.setattr(ai, "_local_retriever", fail)
    assert await ai.create_ai_runtime(fake.catalog) is None
    assert not any(call[0] == "client" for call in fake.calls)
    assert fake.client.complete_calls == 0
    assert fake.client.close_calls == 0
    assert "FAQ" in caplog.text
    assert "private-" not in caplog.text


@pytest.mark.parametrize("stage", ["grounded", "pipeline"])
async def test_factory_failure_after_client_creation_closes_it_without_leaking_details(
    monkeypatch, runtime_factory, caplog, stage,
):
    fake = runtime_factory

    def fail(*args, **kwargs):
        raise RuntimeError("private-initialization-details")

    monkeypatch.setattr(llm, "GroundedLLMService" if stage == "grounded" else "RagAnswerService", fail)
    assert await ai.create_ai_runtime(fake.catalog) is None
    assert any(call[0] == "client" for call in fake.calls)
    assert fake.client.complete_calls == 0
    assert fake.client.close_calls == 1
    assert "RuntimeError" in caplog.text
    assert "private-initialization-details" not in caplog.text
