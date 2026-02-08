import asyncio

import pytest
from telegram.error import TimedOut

from sgbridgebot.ChatHandler import ChatHandler
from sgbridgebot.CommandUtils import CommandUtils


class _AlwaysTimeoutBot:
    def __init__(self):
        self.send_attempts = 0
        self.edit_attempts = 0

    async def send_message(self, *args, **kwargs):
        self.send_attempts += 1
        raise TimedOut("timed out")

    async def edit_message_text(self, *args, **kwargs):
        self.edit_attempts += 1
        raise TimedOut("timed out")


class _FlakyReplyMessage:
    def __init__(self, fail_attempts, success_value):
        self.fail_attempts = fail_attempts
        self.success_value = success_value
        self.attempts = 0
        self.message_id = 55

    async def reply_text(self, _message):
        self.attempts += 1
        if self.attempts <= self.fail_attempts:
            raise TimedOut("timed out")
        return self.success_value


class _DummyUpdate:
    def __init__(self, message):
        self.message = message

        class _Chat:
            id = 99

        self.effective_chat = _Chat()


@pytest.fixture
def no_sleep_no_jitter(monkeypatch):
    async def _fake_sleep(_seconds):
        return None

    monkeypatch.setattr("sgbridgebot.retry_utils.asyncio.sleep", _fake_sleep)
    monkeypatch.setattr("sgbridgebot.retry_utils.random.uniform", lambda _a, _b: 0)


def test_send_message_retries_bounded_and_raises(no_sleep_no_jitter):
    handler = ChatHandler(bot=_AlwaysTimeoutBot())

    with pytest.raises(TimedOut):
        asyncio.run(handler.send_message(1234, "hello"))

    assert handler.bot.send_attempts == 4


def test_edit_message_text_retries_bounded_and_raises(no_sleep_no_jitter):
    handler = ChatHandler(bot=_AlwaysTimeoutBot())

    with pytest.raises(TimedOut):
        asyncio.run(handler.edit_message_text("hello", 1234, 77))

    assert handler.bot.edit_attempts == 4


def test_reply_text_succeeds_when_later_retry_succeeds(no_sleep_no_jitter):
    expected_message = object()
    update = _DummyUpdate(_FlakyReplyMessage(fail_attempts=2, success_value=expected_message))
    utils = CommandUtils(manager=None, chat_handler=None)

    result = asyncio.run(utils.reply_text(update, "hello"))

    assert result is expected_message
    assert update.message.attempts == 3
