"""Real aiogram routing with a recording, network-free Telegram session."""

from datetime import datetime, timezone
from itertools import count

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage, SetMyCommands
from aiogram.types import Chat, Message, MessageEntity, Update, User

from app.bot.factory import create_dispatcher

TEST_TOKEN = "123456789:" + "a" * 35  # Synthetic; never used for real requests.


class RecordingSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.failures_remaining = 0
        self.closed = False

    async def close(self):
        self.closed = True

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise TelegramNetworkError(method=method, message="private-error-content")
        if isinstance(method, SendMessage):
            return Message(
                message_id=len(self.calls), date=datetime.now(timezone.utc),
                chat=Chat(id=method.chat_id, type="private"), text=method.text,
            )
        if isinstance(method, SetMyCommands):
            return True
        raise AssertionError(f"Unexpected Telegram method in test: {type(method).__name__}")

    async def stream_content(self, url, **kwargs):
        raise AssertionError("Network access is forbidden in tests")
        yield b""  # Required async-generator signature.


class BotHarness:
    def __init__(self):
        self.session = RecordingSession()
        self.bot = Bot(token=TEST_TOKEN, session=self.session)
        self.dispatcher = create_dispatcher()
        self.catalog = self.dispatcher["faq_catalog"]
        self.ids = count(1)

    async def send(self, text=None, user_id=101, locale="uz", chat_type="private", **content):
        index = next(self.ids)
        entities = []
        if text and text.startswith("/"):
            entities = [MessageEntity(type="bot_command", offset=0, length=len(text.split()[0]))]
        update = Update(update_id=index, message=Message(
            message_id=index, date=datetime.now(timezone.utc),
            chat=Chat(id=user_id, type=chat_type),
            from_user=User(id=user_id, is_bot=False, first_name="Demo", language_code=locale),
            text=text, entities=entities, **content,
        ))
        await self.dispatcher.feed_update(self.bot, update)

    @property
    def last(self):
        return self.session.calls[-1]


@pytest.fixture
async def harness():
    value = BotHarness()
    yield value
    await value.dispatcher.storage.close()
    await value.dispatcher.fsm.events_isolation.close()
    await value.session.close()
