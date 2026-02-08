from dataclasses import dataclass

import pytest
from telegram import User


@dataclass
class FakeChat:
    id: int
    type: str


class MockChatHandler:
    def __init__(self):
        self.events = []
        self.winner_payload = None

    async def player_joined_game(self, player, game):
        self.events.append(("player_joined_game", player.id, game.id))

    async def starting_game(self, game):
        self.events.append(("starting_game", game.id))

    async def ask_private_chat(self, game):
        self.events.append(("ask_private_chat", game.id))

    async def display_hand(self, player):
        self.events.append(("display_hand", player.id))

    async def request_bid(self, player):
        self.events.append(("request_bid", player.id))

    async def game_winners(self, result, winners, declarer_tricks, required_tricks, game):
        self.winner_payload = {
            "result": result,
            "winner_ids": [p.id for p in winners],
            "declarer_tricks": declarer_tricks,
            "required_tricks": required_tricks,
            "game_id": game.id,
        }

    async def card_played(self, player, card, game):
        self.events.append(("card_played", player.id, card.id, game.id))

    async def request_card(self, player, game):
        self.events.append(("request_card", player.id, game.id))

    async def announce_trick(self, player, card, game):
        self.events.append(("announce_trick", player.id, card.id, game.id))

    async def player_passed(self, player, game):
        self.events.append(("player_passed", player.id, game.id))

    async def player_bid(self, bid, player, game):
        self.events.append(("player_bid", bid, player.id, game.id))

    async def invalid_bid(self, player):
        self.events.append(("invalid_bid", player.id))

    async def bid_winner(self, player, contract, game):
        self.events.append(("bid_winner", player.id, contract, game.id))

    async def request_partner_choice(self, player):
        self.events.append(("request_partner_choice", player.id))


@pytest.fixture
def mock_handler():
    return MockChatHandler()


@pytest.fixture
def make_user():
    def _make_user(user_id: int, username: str | None = None, first_name: str = "Player"):
        return User(id=user_id, is_bot=False, first_name=first_name, username=username)

    return _make_user
