import asyncio
from types import SimpleNamespace
from unittest import mock

import pytest

from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.BridgeGame import BridgeGame
from sgbridgebot.CommandUtils import CommandUtils
from sgbridgebot.game_types import GameState, GameType

class _StubPlayer:
    def __init__(self, player_id):
        self.id = player_id


class _StubGame:
    def __init__(self, players):
        self.players = players


class _StubManager:
    def __init__(self, active_games=None, waiting_games=None):
        self.active_games = active_games or []
        self.waiting_games = waiting_games or []


class _StubChat:
    def __init__(self):
        self.calls = []

    async def ask_private_chat(self, game):
        self.calls.append(("ask_private_chat", game))

    async def display_game_players(self, chat_id, game):
        self.calls.append(("display_game_players", chat_id, game))

    async def display_hand(self, player, chat_id):
        self.calls.append(("display_hand", player.id, chat_id))


class _StubMessage:
    def __init__(self, user):
        self.from_user = user
        self.replies = []

    async def reply_text(self, message):
        self.replies.append(message)
        return message


class _StubUpdate:
    def __init__(self, user, chat_id=999, chat_type="private"):
        self.message = _StubMessage(user)
        self.effective_chat = SimpleNamespace(id=chat_id, type=chat_type)


def test_hand_replies_when_user_not_in_active_or_waiting_game():
    user = SimpleNamespace(id=10)
    update = _StubUpdate(user)
    manager = _StubManager(active_games=[_StubGame([_StubPlayer(99)])], waiting_games=[])
    chat = _StubChat()
    utils = CommandUtils(manager=manager, chat_handler=chat)

    asyncio.run(utils.hand(update, context=None))

    assert update.message.replies == ["You are not in an active game. Use /join first."]
    assert chat.calls == []


def test_hand_replies_when_user_is_only_in_waiting_game():
    user = SimpleNamespace(id=10)
    update = _StubUpdate(user)
    manager = _StubManager(active_games=[], waiting_games=[_StubGame([_StubPlayer(10)])])
    chat = _StubChat()
    utils = CommandUtils(manager=manager, chat_handler=chat)

    asyncio.run(utils.hand(update, context=None))

    assert update.message.replies == [
        "You are in a game lobby. Wait for the game to start, then use /hand in a private chat."
    ]
    assert chat.calls == []


class DummyChatHandler:
    def __init__(self):
        self.calls = []

    async def player_joined_game(self, user, game):
        self.calls.append(("player_joined_game", user.id, game.id))

    async def player_left_game(self, user, game):
        self.calls.append(("player_left_game", user.id, game.id))

    async def ask_private_chat(self, game):
        self.calls.append(("ask_private_chat", game.id))

    async def display_game_players(self, chat_id, game):
        self.calls.append(("display_game_players", chat_id, game.id))

    async def display_hand(self, player, chat_id):
        self.calls.append(("display_hand", player.id, chat_id))

    async def partner_chosen(self, player, card_id, game):
        self.calls.append(("partner_chosen", player.id, card_id, game.id))

    async def request_partner_rank(self, player, suit_symbol):
        self.calls.append(("request_partner_rank", player.id, suit_symbol))

    async def card_played(self, player, card, game):
        self.calls.append(("card_played", player.id, card.id, game.id))

    async def request_card(self, player, game):
        self.calls.append(("request_card", player.id, game.id))


class DummyManager:
    def __init__(self):
        self.active_games = []
        self.join_result = None
        self.leave_result = None
        self.find_result = None
        self.update_calls = 0

    async def join_game(self, user, chat):
        return self.join_result

    def leave_game(self, user, chat_id):
        return self.leave_result

    def find_game(self, user, chat_id):
        return self.find_result

    def update_gamelists(self):
        self.update_calls += 1


class DummyMessage:
    def __init__(self, user, text="", message_id=123):
        self.from_user = user
        self.text = text
        self.message_id = message_id


class DummyUpdate:
    def __init__(self, user, chat_id=101, chat_type="private", text=""):
        self.message = DummyMessage(user, text=text)
        self.effective_chat = SimpleNamespace(id=chat_id, type=chat_type)


def _make_user(user_id=1):
    return SimpleNamespace(id=user_id)


def _make_game(chat_handler):
    return BridgeGame(handler=chat_handler, type=GameType.PUBLIC)


def test_join_handles_full_game_with_user_facing_message():
    manager = DummyManager()
    manager.join_result = -1
    chat = DummyChatHandler()
    utils = CommandUtils(manager, chat)
    utils.reply_text = mock.AsyncMock()

    asyncio.run(utils.join(DummyUpdate(_make_user()), None))

    utils.reply_text.assert_awaited_once()
    assert "currently full" in utils.reply_text.await_args.args[1]


def test_join_handles_duplicate_player_message():
    manager = DummyManager()
    manager.join_result = -2
    chat = DummyChatHandler()
    utils = CommandUtils(manager, chat)
    utils.reply_text = mock.AsyncMock()

    asyncio.run(utils.join(DummyUpdate(_make_user()), None))

    assert "already in the game" in utils.reply_text.await_args.args[1]


def test_join_raises_when_manager_returns_invalid_type():
    manager = DummyManager()
    manager.join_result = object()
    utils = CommandUtils(manager, DummyChatHandler())

    with pytest.raises(TypeError, match="valid BridgeGame"):
        asyncio.run(utils.join(DummyUpdate(_make_user()), None))


def test_join_notifies_chat_handler_on_successful_join():
    chat = DummyChatHandler()
    manager = DummyManager()
    manager.join_result = _make_game(chat)
    user = _make_user(77)
    utils = CommandUtils(manager, chat)

    asyncio.run(utils.join(DummyUpdate(user), None))

    assert ("player_joined_game", 77, manager.join_result.id) in chat.calls


def test_leave_handles_not_in_game_message():
    manager = DummyManager()
    manager.leave_result = -1
    utils = CommandUtils(manager, DummyChatHandler())
    utils.reply_text = mock.AsyncMock()

    asyncio.run(utils.leave(DummyUpdate(_make_user()), None))

    assert "already not in the game" in utils.reply_text.await_args.args[1]


def test_leave_raises_when_manager_returns_invalid_type():
    manager = DummyManager()
    manager.leave_result = object()
    utils = CommandUtils(manager, DummyChatHandler())

    with pytest.raises(TypeError, match="valid BridgeGame"):
        asyncio.run(utils.leave(DummyUpdate(_make_user()), None))


def test_leave_sends_confirmation_and_notifies_chat_handler():
    chat = DummyChatHandler()
    manager = DummyManager()
    manager.leave_result = _make_game(chat)
    user = _make_user(42)
    utils = CommandUtils(manager, chat)
    utils.reply_text = mock.AsyncMock()

    asyncio.run(utils.leave(DummyUpdate(user), None))

    assert "left the game" in utils.reply_text.await_args.args[1]
    assert ("player_left_game", 42, manager.leave_result.id) in chat.calls


def test_hand_in_group_chat_requests_private_chat():
    chat = DummyChatHandler()
    manager = DummyManager()
    utils = CommandUtils(manager, chat)

    player = SimpleNamespace(id=9, hand=[])
    game = SimpleNamespace(id="g1", players=[player])
    manager.active_games = [game]

    asyncio.run(utils.hand(DummyUpdate(_make_user(9), chat_type="group"), None))

    assert chat.calls == [("ask_private_chat", "g1")]


def test_hand_in_private_chat_displays_players_and_hand():
    chat = DummyChatHandler()
    manager = DummyManager()
    utils = CommandUtils(manager, chat)

    player = SimpleNamespace(id=11, hand=[])
    game = SimpleNamespace(id="g2", players=[player])
    manager.active_games = [game]

    asyncio.run(utils.hand(DummyUpdate(_make_user(11), chat_id=202, chat_type="private"), None))

    assert ("display_game_players", 202, "g2") in chat.calls
    assert ("display_hand", 11, 202) in chat.calls


def test_bidding_rejects_when_not_players_turn_or_wrong_state():
    manager = DummyManager()
    chat = DummyChatHandler()
    utils = CommandUtils(manager, chat)
    utils.reply_text = mock.AsyncMock()
    utils.chat.str_utils = SimpleNamespace(bid_str_to_id=lambda _text: 10)

    game = _make_game(chat)
    game.state = GameState.PLAY
    game.curr_player = lambda: SimpleNamespace(id=999)
    game.process_bid = mock.AsyncMock()
    manager.find_result = game

    asyncio.run(utils.bidding(DummyUpdate(_make_user(1), text="1NT"), None))

    utils.reply_text.assert_awaited_once()
    game.process_bid.assert_not_awaited()


def test_bidding_replies_when_user_not_in_active_game():
    manager = DummyManager()
    chat = DummyChatHandler()
    utils = CommandUtils(manager, chat)
    utils.reply_text = mock.AsyncMock()
    utils.chat.str_utils = SimpleNamespace(bid_str_to_id=lambda _text: 10)
    manager.find_result = None

    asyncio.run(utils.bidding(DummyUpdate(_make_user(1), text="1NT"), None))

    utils.reply_text.assert_awaited_once_with(
        mock.ANY,
        "You are not in an active game. Use /join first.",
    )


def test_bidding_processes_bid_when_valid_turn_and_auction_state():
    manager = DummyManager()
    chat = DummyChatHandler()
    utils = CommandUtils(manager, chat)
    utils.chat.str_utils = SimpleNamespace(bid_str_to_id=lambda _text: 17)

    game = _make_game(chat)
    game.state = GameState.AUCTION
    game.curr_player = lambda: SimpleNamespace(id=7)
    game.process_bid = mock.AsyncMock()
    manager.find_result = game

    asyncio.run(utils.bidding(DummyUpdate(_make_user(7), text="3NT"), None))

    game.process_bid.assert_awaited_once_with(17)


def test_card_partner_call_sets_partner_and_moves_turn():
    manager = DummyManager()
    chat = DummyChatHandler()
    utils = CommandUtils(manager, chat)
    utils.chat.str_utils = SimpleNamespace(card_str_to_id=lambda _text: 12)

    current_player = SimpleNamespace(id=5)
    partner = SimpleNamespace(id=66)

    game = _make_game(chat)
    game.state = GameState.PARTNER_CALL
    game.curr_player = lambda: current_player
    game.player_holding_card = lambda _card_id: partner
    game.next_turn = mock.AsyncMock()
    manager.find_result = game

    asyncio.run(utils.card(DummyUpdate(_make_user(5), text="♣A"), None))

    assert game.partner is partner
    assert isinstance(game.partner_card, BridgeCard)
    assert game.partner_card.id == 12
    assert ("partner_chosen", 5, 12, game.id) in chat.calls
    game.next_turn.assert_awaited_once()


def test_card_replies_when_user_not_in_active_game():
    manager = DummyManager()
    chat = DummyChatHandler()
    utils = CommandUtils(manager, chat)
    utils.reply_text = mock.AsyncMock()
    utils.chat.str_utils = SimpleNamespace(card_str_to_id=lambda _text: 12)
    manager.find_result = None

    asyncio.run(utils.card(DummyUpdate(_make_user(5), text="♣A"), None))

    utils.reply_text.assert_awaited_once_with(
        mock.ANY,
        "You are not in an active game. Use /join first.",
    )


def test_card_play_rejects_invalid_card_and_requests_new_card():
    manager = DummyManager()
    chat = DummyChatHandler()
    utils = CommandUtils(manager, chat)
    utils.reply_text = mock.AsyncMock()
    utils.chat.str_utils = SimpleNamespace(card_str_to_id=lambda _text: 3)

    current_player = SimpleNamespace(id=8, hand=[])
    game = _make_game(chat)
    game.state = GameState.PLAY
    game.curr_player = lambda: current_player
    game.valid_play = lambda _card: False
    manager.find_result = game

    asyncio.run(utils.card(DummyUpdate(_make_user(8), text="♣5"), None))

    assert "Invalid card" in utils.reply_text.await_args.args[1]
    assert ("request_card", 8, game.id) in chat.calls


def test_card_play_handles_remove_card_failure_gracefully():
    manager = DummyManager()
    chat = DummyChatHandler()
    utils = CommandUtils(manager, chat)
    utils.reply_text = mock.AsyncMock()
    utils.chat.str_utils = SimpleNamespace(card_str_to_id=lambda _text: 4)

    class CurrentPlayer:
        id = 2
        hand = [BridgeCard(4)]

        def remove_card(self, _card):
            return None

    current_player = CurrentPlayer()

    game = _make_game(chat)
    game.state = GameState.PLAY
    game.curr_player = lambda: current_player
    game.valid_play = lambda _card: True
    game.next_turn = mock.AsyncMock()
    manager.find_result = game

    asyncio.run(utils.card(DummyUpdate(_make_user(2), text="♣6"), None))

    assert "Could not play card" in utils.reply_text.await_args.args[1]
    assert ("request_card", 2, game.id) in chat.calls
    game.next_turn.assert_not_awaited()


def test_card_play_adds_card_marks_trump_broken_and_advances_turn():
    manager = DummyManager()
    chat = DummyChatHandler()
    utils = CommandUtils(manager, chat)
    utils.chat.str_utils = SimpleNamespace(card_str_to_id=lambda _text: 26)

    played_card = BridgeCard(26)

    class CurrentPlayer:
        id = 55
        hand = [played_card]

        def remove_card(self, _card):
            self.hand = []
            return played_card

    current_player = CurrentPlayer()

    game = _make_game(chat)
    game.state = GameState.PLAY
    game.contract = 0
    game.trick = []
    game.trump_broken = 0
    game.curr_player = lambda: current_player
    game.valid_play = lambda _card: True
    game.get_trump_suit = lambda: played_card.suit
    game.next_turn = mock.AsyncMock()
    manager.find_result = game

    asyncio.run(utils.card(DummyUpdate(_make_user(55), text="♦2"), None))

    assert game.trick == [played_card]
    assert game.trump_broken == 1
    assert ("card_played", 55, played_card.id, game.id) in chat.calls
    game.next_turn.assert_awaited_once()


def test_start_and_help_commands_return_guidance_text():
    manager = DummyManager()
    chat = DummyChatHandler()
    utils = CommandUtils(manager, chat)
    utils.reply_text = mock.AsyncMock()

    asyncio.run(utils.start(DummyUpdate(_make_user()), None))
    asyncio.run(utils.help(DummyUpdate(_make_user()), None))

    assert "Quick start" in utils.reply_text.await_args_list[0].args[1]
    assert "Commands" in utils.reply_text.await_args_list[1].args[1]


def test_card_partner_call_supports_two_step_suit_then_rank_selection():
    manager = DummyManager()
    chat = DummyChatHandler()
    chat.str_utils = __import__("sgbridgebot.StringUtils", fromlist=["StringUtils"]).StringUtils()
    utils = CommandUtils(manager, chat)

    current_player = SimpleNamespace(id=5, chat_id=999)
    partner = SimpleNamespace(id=66)

    game = _make_game(chat)
    game.state = GameState.PARTNER_CALL
    game.curr_player = lambda: current_player
    game.player_holding_card = lambda _card_id: partner
    game.next_turn = mock.AsyncMock()
    manager.find_result = game

    asyncio.run(utils.card(DummyUpdate(_make_user(5), text="H"), None))
    assert ("request_partner_rank", 5, chat.str_utils.suit_str[2]) in chat.calls

    asyncio.run(utils.card(DummyUpdate(_make_user(5), text="A"), None))
    assert game.partner is partner
    assert game.partner_card.id == 38
    game.next_turn.assert_awaited_once()
