import logging
import asyncio

from types import SimpleNamespace

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, User
from telegram.error import Forbidden, TimedOut

from sgbridgebot.bridge_card import BridgeCard
from sgbridgebot.bridge_game import BridgeGame
from sgbridgebot.bridge_player import BridgePlayer
from sgbridgebot.chat_handler import ChatHandler
from sgbridgebot.game_types import GameState, GameType


class _DummyPlayer:
    def __init__(self, name="u1"):
        self._name = name

    def disp_name(self):
        return self._name


class _DummyGame:
    def __init__(self, chat_ids):
        self._chat_ids = chat_ids
        self.auction_log = [("u2", -1), ("u1", 0)]

    def tricks_required(self):
        return 7

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
    assert all("Auction: u2: pass · u1: 1♣" in call["message"] for call in calls)


def _started_game(make_user, game_type=GameType.MATCHMAKING):
    handler = ChatHandler(bot=None)
    calls = []

    async def fake_send_message(chat_id, message, parse_mode=None, reply_markup=None):
        calls.append({
            "chat_id": chat_id,
            "message": message,
            "parse_mode": parse_mode,
            "reply_markup": reply_markup,
        })
        return SimpleNamespace(message_id=len(calls))

    async def fake_remove_keyboard(chat_id, message_id):
        calls.append({"removed": (chat_id, message_id)})

    handler.send_message = fake_send_message
    handler.remove_keyboard = fake_remove_keyboard
    game = BridgeGame(handler, game_type)
    for i, name in enumerate(["_name](", None, "u3", "u4"]):
        user = User(id=i + 1, is_bot=False, first_name="A_[B<&" if name is None else "P", username=name)
        game.players.append(BridgePlayer(user, 1001 if game_type == GameType.GROUP else 1001 + i))
    for i, player in enumerate(game.players):
        player.give_direction(i + 1)
    game.deal_hands()
    game.state = GameState.PLAY
    game.contract = 0
    game.declarer = game.players[0]
    game.partner_card = BridgeCard(51)
    game.trick_start = 0
    return handler, game, calls


def _buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_request_card_sends_inline_keyboard_of_legal_cards(make_user):
    handler, game, calls = _started_game(make_user)
    player = game.players[0]

    asyncio.run(handler.request_card(player, game))

    assert len(calls) == 1
    assert calls[0]["chat_id"] == 1001
    assert calls[0]["parse_mode"] == "HTML"
    assert "your turn to play" in calls[0]["message"]
    labels = [b.text for b in _buttons(calls[0]["reply_markup"])]
    assert labels == game.legal_cards(player)
    assert game.last_prompt == (1001, 1)


def test_prompt_mentions_escape_html_and_use_tg_user_links(make_user):
    handler, game, calls = _started_game(make_user)
    game.state = GameState.PARTNER_CALL

    asyncio.run(handler.request_partner_choice(game.players[0], game))
    asyncio.run(handler.request_partner_choice(game.players[1], game))

    sends = [call for call in calls if "message" in call]
    assert calls[1] == {"removed": (1001, 1)}
    assert sends[0]["message"].startswith("@_name](,")
    assert sends[1]["message"].startswith('<a href="tg://user?id=2">A_[B&lt;&amp;</a>')
    assert "Choose a suit first" in sends[1]["message"]
    suit_data = [b.callback_data for b in _buttons(sends[1]["reply_markup"])]
    assert suit_data == [f"ps:{game.short_id}:{game.action_seq}:{s}" for s in range(4)]


def test_bid_keyboard_only_offers_bids_above_the_contract(make_user):
    handler, game, calls = _started_game(make_user)
    game.state = GameState.AUCTION
    game.contract = 32  # 7♥

    asyncio.run(handler.request_bid(game.players[0], game))

    labels = [b.text for b in _buttons(calls[0]["reply_markup"])]
    assert labels == ["PASS", "7♠", "7NT"]
    assert all(len(b.callback_data.encode()) <= 64 for b in _buttons(calls[0]["reply_markup"]))


def test_group_card_prompt_falls_back_to_group_keyboard_when_dm_is_blocked(make_user):
    handler, game, calls = _started_game(make_user, GameType.GROUP)
    player = game.players[1]

    async def refuse_private(chat_id, message, parse_mode=None, reply_markup=None):
        if chat_id == player.id:
            raise Forbidden("bot can't initiate conversation with a user")
        calls.append({"chat_id": chat_id, "message": message, "reply_markup": reply_markup})
        return SimpleNamespace(message_id=len(calls))

    handler.send_message = refuse_private
    asyncio.run(handler.request_card(player, game))

    assert player.dm_blocked is True
    assert calls[0]["chat_id"] == 1001
    assert isinstance(calls[0]["reply_markup"], ReplyKeyboardMarkup)
    assert calls[0]["reply_markup"].selective is True


def test_card_played_edits_each_chat_by_chat_id_after_a_seat_changes_hands(make_user):
    handler, game, calls = _started_game(make_user)
    edits = []

    async def fake_edit(text, chat_id, message_id, parse_mode=None, reply_markup=None):
        edits.append((chat_id, message_id))

    handler.edit_message_text = fake_edit
    game.trick = [BridgeCard(0)]
    asyncio.run(handler.card_played(game.players[0], game.trick[0], game))
    sent = {call["chat_id"]: i + 1 for i, call in enumerate(calls)}

    # The second player leaves; their private chat drops out of the game.
    game.players[1].player_to_bot()
    game.trick.append(BridgeCard(1))
    asyncio.run(handler.card_played(game.players[1], game.trick[1], game))

    assert edits == [(chat_id, sent[chat_id]) for chat_id in game.get_chat_ids()]


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


def test_partner_reveal_announces_sides_and_tally(make_user):
    handler, game, calls = _started_game(make_user)
    game.partner = game.players[2]
    game.partner_revealed = True
    game.players[0].tricks_won = 3
    game.players[2].tricks_won = 2
    game.players[1].tricks_won = 1

    asyncio.run(handler.partner_revealed(game.players[2], game))

    text = calls[0]["message"]
    assert "Partner revealed! u3 holds ♠A and plays with _name](." in text
    assert "_name]( + u3: 5/7 tricks" in text
    assert ": 1/7 to defeat" in text


def test_tally_hides_sides_until_partner_is_revealed(make_user):
    handler, game, _ = _started_game(make_user)
    game.partner = game.players[2]

    tally = handler.tricks_tally(game)

    assert "u3" in tally and "+" not in tally
    assert "need 7; the others need 7 to defeat" in tally


def test_declarer_calling_own_card_is_announced_as_playing_alone(make_user):
    handler, game, calls = _started_game(make_user)
    game.partner = game.declarer
    game.partner_revealed = True

    asyncio.run(handler.partner_revealed(game.declarer, game))

    assert "playing alone" in calls[0]["message"]
