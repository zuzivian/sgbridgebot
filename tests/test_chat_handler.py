import logging
import asyncio

from telegram import ReplyKeyboardRemove
from telegram.error import TimedOut

from sgbridgebot.ChatHandler import ChatHandler


class _DummyPlayer:
    def __init__(self, name="u1"):
        self._name = name

    def disp_name(self):
        return self._name


class _DummyGame:
    def __init__(self, chat_ids):
        self._chat_ids = chat_ids

    def get_chat_ids(self):
        return self._chat_ids


def test_bid_winner_clears_bidding_keyboard_before_partner_selection():
    handler = ChatHandler(bot=None)
    calls = []

    async def fake_send_message(chat_id, message, parse_mode=None, reply_markup=None):
        calls.append(
            {
                "chat_id": chat_id,
                "message": message,
                "reply_markup": reply_markup,
            }
        )

    handler.send_message = fake_send_message
    player = _DummyPlayer()
    game = _DummyGame([1001, 1002])

    asyncio.run(handler.bid_winner(player, 0, game))

    assert len(calls) == 2
    assert all(isinstance(call["reply_markup"], ReplyKeyboardRemove) for call in calls)
    assert all("wins with bid" in call["message"] for call in calls)


class _DummyCard:
    def __init__(self, text):
        self._text = text

    def __repr__(self):
        return self._text


class _DummyPlayPlayer:
    def __init__(self):
        self.username = "u1"
        self.first_name = "Player"
        self.id = 1
        self.chat_id = 1001
        self._cards = {
            0: [_DummyCard("♣A"), _DummyCard("♣K")],
            1: [_DummyCard("♦Q")],
            2: [],
            3: [_DummyCard("♠2")],
        }

    def get_all_suit(self, suit):
        return list(self._cards[suit])


class _DummyDeclarer:
    def disp_name(self):
        return "decl"


class _DummyPlayGame:
    contract = 0
    declarer = _DummyDeclarer()
    partner_card = "♣A"


def test_request_card_builds_keyboard_without_name_error():
    handler = ChatHandler(bot=None)
    calls = []

    async def fake_send_message(chat_id, message, parse_mode=None, reply_markup=None):
        calls.append({
            "chat_id": chat_id,
            "message": message,
            "parse_mode": parse_mode,
            "reply_markup": reply_markup,
        })

    handler.send_message = fake_send_message

    asyncio.run(handler.request_card(_DummyPlayPlayer(), _DummyPlayGame()))

    assert len(calls) == 1
    assert calls[0]["chat_id"] == 1001
    assert "please choose a card to play" in calls[0]["message"]
    assert calls[0]["reply_markup"] is not None


class _TimeoutThenSuccessBot:
    def __init__(self):
        self.calls = 0

    async def send_message(self, chat_id, message, parse_mode=None, reply_markup=None):
        self.calls += 1
        if self.calls == 1:
            raise TimedOut("timeout")
        return {"chat_id": chat_id, "message": message}


def test_send_message_retries_and_logs_timeout_warning(caplog):
    handler = ChatHandler(bot=_TimeoutThenSuccessBot())

    with caplog.at_level(logging.WARNING):
        response = asyncio.run(handler.send_message(1001, "hello"))

    assert response["chat_id"] == 1001
    assert "Timed out error in bot.send_message, retrying" in caplog.text


class _TimeoutThenEditSuccessBot:
    def __init__(self):
        self.calls = 0

    async def edit_message_text(self, text, chat_id, message_id, parse_mode=None, reply_markup=None):
        self.calls += 1
        if self.calls == 1:
            raise TimedOut("timeout")
        return {"chat_id": chat_id, "message_id": message_id, "text": text}


def test_edit_message_text_retries_and_logs_timeout_warning(caplog):
    handler = ChatHandler(bot=_TimeoutThenEditSuccessBot())

    with caplog.at_level(logging.WARNING):
        response = asyncio.run(handler.edit_message_text("hi", 1001, 42))

    assert response["message_id"] == 42
    assert "Timed out error in bot.edit_message_text, retrying" in caplog.text
