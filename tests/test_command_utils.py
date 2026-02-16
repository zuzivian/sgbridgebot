import asyncio
from types import SimpleNamespace

from sgbridgebot.CommandUtils import CommandUtils


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
