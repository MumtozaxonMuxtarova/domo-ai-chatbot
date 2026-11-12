from unittest.mock import AsyncMock
import os
from pathlib import Path
import subprocess
import sys

import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.methods import GetMe, SetMyCommands

from app import main
from app.bot.factory import create_bot
from app.config import ConfigurationError, Settings
from app.faq import KnowledgeBaseError
from conftest import TEST_TOKEN


@pytest.fixture(autouse=True)
def offline_ai_startup(monkeypatch):
    # Existing lifecycle tests must not load real credentials/models or use APIs.
    monkeypatch.setattr(main, "create_ai_runtime", AsyncMock(return_value=None))


@pytest.fixture
def settings():
    return Settings(bot_token=TEST_TOKEN, request_timeout=17)


@pytest.fixture
def cli_settings(monkeypatch, settings):
    monkeypatch.setattr(main, "load_settings", lambda: settings)
    monkeypatch.setattr(main, "configure_logging", lambda *args: None)
    return settings


def test_missing_config_returns_clear_error_without_traceback(monkeypatch, capsys):
    def fail():
        raise ConfigurationError("BOT_TOKEN kiritilmagan")
    monkeypatch.setattr(main, "load_settings", fail)
    assert main.main([]) == 2
    output = capsys.readouterr()
    assert "BOT_TOKEN" in output.err
    assert "Traceback" not in output.err


def test_config_check_is_offline(monkeypatch, capsys, cli_settings):
    def fail(_settings):
        raise AssertionError("Bot must not be constructed for a configuration check")
    monkeypatch.setattr(main, "run_bot", fail)
    assert main.main(["--check-config"]) == 0
    assert "Telegram orqali tekshirilmagan" in capsys.readouterr().out


@pytest.mark.parametrize("error", [
    TelegramUnauthorizedError(method=GetMe(), message="private-token"),
    TelegramNetworkError(method=GetMe(), message="private-network-data"),
    RuntimeError("private-unexpected-data"),
    KnowledgeBaseError("Bilim bazasi fayli yo'q: faq.json"),
])
def test_startup_errors_are_safe(monkeypatch, cli_settings, error, caplog):
    monkeypatch.setattr(main, "run_bot", AsyncMock(side_effect=error))
    assert main.main([]) == 1
    assert "private-" not in caplog.text


async def test_invalid_knowledge_base_fails_before_bot_creation(monkeypatch, settings):
    def fail():
        raise KnowledgeBaseError("Bilim bazasi fayli yo'q: faq.json")
    monkeypatch.setattr(main, "create_dispatcher", fail)
    def must_not_create(_settings):
        raise AssertionError("No Telegram bot should be created with invalid knowledge content")
    monkeypatch.setattr(main, "create_bot", must_not_create)
    with pytest.raises(KnowledgeBaseError):
        await main.run_bot(settings)


async def test_bot_factory_uses_configured_timeout(settings):
    bot = create_bot(settings)
    assert bot.session.timeout == 17
    await bot.session.close()


async def test_startup_sets_commands_polls_and_closes_resources(monkeypatch, harness, settings):
    monkeypatch.setattr(main, "create_bot", lambda _: harness.bot)
    monkeypatch.setattr(main, "create_dispatcher", lambda: harness.dispatcher)
    poll = AsyncMock()
    monkeypatch.setattr(harness.dispatcher, "start_polling", poll)
    await main.run_bot(settings)
    assert isinstance(harness.session.calls[0], SetMyCommands)
    assert {command.command for command in harness.session.calls[0].commands} == {"start", "help", "language"}
    assert harness.session.calls[0].scope.type == "all_private_chats"
    poll.assert_awaited_once_with(
        harness.bot, allowed_updates=["message"], close_bot_session=False
    )
    assert harness.session.closed


async def test_startup_failure_still_closes_session(monkeypatch, harness, settings):
    monkeypatch.setattr(main, "create_bot", lambda _: harness.bot)
    monkeypatch.setattr(main, "create_dispatcher", lambda: harness.dispatcher)
    harness.session.failures_remaining = 1
    with pytest.raises(TelegramNetworkError):
        await main.run_bot(settings)
    assert harness.session.closed


@pytest.mark.parametrize("fail_commands", [False, True])
async def test_ai_runtime_is_injected_and_closed_on_normal_or_failed_startup(monkeypatch, harness, settings, fail_commands):
    runtime = AsyncMock()
    monkeypatch.setattr(main, "create_ai_runtime", AsyncMock(return_value=runtime))
    monkeypatch.setattr(main, "create_bot", lambda _: harness.bot)
    monkeypatch.setattr(main, "create_dispatcher", lambda: harness.dispatcher)
    poll = AsyncMock()
    monkeypatch.setattr(harness.dispatcher, "start_polling", poll)
    if fail_commands:
        harness.session.failures_remaining = 1
        with pytest.raises(TelegramNetworkError):
            await main.run_bot(settings)
    else:
        await main.run_bot(settings)
        poll.assert_awaited_once()
    assert harness.dispatcher["rag_service"] is runtime
    runtime.aclose.assert_awaited_once()
    assert harness.session.closed


def test_faq_bot_imports_and_starts_without_optional_ai_packages():
    script = """
import asyncio
import importlib.abc
import sys

class NoAI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'httpx', 'chromadb', 'sentence_transformers'}:
            raise ModuleNotFoundError('optional dependency intentionally unavailable')
        return None

sys.meta_path.insert(0, NoAI())
from app.bot.factory import create_dispatcher
from app.bot.ai import create_ai_runtime
from app import main

async def check():
    dispatcher = create_dispatcher()
    assert await create_ai_runtime(dispatcher['faq_catalog']) is None
    assert dispatcher['faq_catalog'].faq_items['debt_check'].status == 'approved'
    await dispatcher.storage.close()
    await dispatcher.fsm.events_isolation.close()
    print('faq_ready_without_ai')

asyncio.run(check())
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script], cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "faq_ready_without_ai" in result.stdout
