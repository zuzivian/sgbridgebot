import logging
import asyncio

from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.BridgeGame import BridgeGame, MAX_REDEAL_ATTEMPTS
from sgbridgebot.game_types import GameState, GameType


async def _build_started_game(mock_handler, make_user):
    game = BridgeGame(mock_handler, type=GameType.PUBLIC)
    for i in range(4):
        state = await game.add_player(make_user(i + 1, username=f"u{i+1}"), 100 + i)
        assert state is game
    return game


def test_player_join_leave_lifecycle(mock_handler, make_user):
    game = BridgeGame(mock_handler, type=GameType.PUBLIC)

    asyncio.run(game.add_player(make_user(1, username="u1"), 101))
    assert game.num_players() == 1

    duplicate = asyncio.run(game.add_player(make_user(1, username="u1"), 101))
    assert duplicate == -2

    game.remove_player(make_user(1, username="u1"), 101)
    assert game.num_players() == 0


def test_transition_from_lobby_to_started_game(mock_handler, make_user):
    game = asyncio.run(_build_started_game(mock_handler, make_user))

    assert game.state == GameState.AUCTION
    assert game.num_players() == 4
    assert game.turn == 0
    assert any(evt[0] == "starting_game" for evt in mock_handler.events)
    assert any(evt[0] == "request_bid" for evt in mock_handler.events)


def test_valid_play_rules(mock_handler, make_user):
    game = BridgeGame(mock_handler, type=GameType.PUBLIC)
    game.players = [
        type("P", (), {"id": 1, "hand": [BridgeCard(13), BridgeCard(0)], "get_all_suit": lambda self, s: [c for c in self.hand if c.suit == s]})(),
        type("P", (), {"id": 2, "hand": [], "get_all_suit": lambda self, s: []})(),
        type("P", (), {"id": 3, "hand": [], "get_all_suit": lambda self, s: []})(),
        type("P", (), {"id": 4, "hand": [], "get_all_suit": lambda self, s: []})(),
    ]
    game.turn = 0
    game.contract = 0  # trump is clubs
    game.trump_broken = 0
    game.trick = []

    assert game.valid_play(BridgeCard(13)) is True  # lead diamonds allowed
    assert game.valid_play(BridgeCard(0)) is False  # lead trump before broken

    game.trick = [BridgeCard(13)]  # leading suit diamonds
    assert game.valid_play(BridgeCard(0)) is False  # must follow suit

    game.players[0].hand = [BridgeCard(0)]
    assert game.valid_play(BridgeCard(0)) is True  # no leading suit cards left


def test_end_game_winner_determination(mock_handler, make_user):
    game = asyncio.run(_build_started_game(mock_handler, make_user))
    game.contract = 5  # level 2 -> requires 8 tricks
    game.declarer = game.players[0]
    game.partner = game.players[2]
    game.declarer.tricks_won = 5
    game.partner.tricks_won = 3

    asyncio.run(game.end_game())

    assert game.state == GameState.SCORING
    assert game.players == []
    assert mock_handler.winner_payload["result"] == 0
    assert set(mock_handler.winner_payload["winner_ids"]) == {1, 3}
    assert mock_handler.winner_payload["required_tricks"] == 8


def test_auction_four_opening_passes_redeal_and_restart(mock_handler, make_user):
    game = asyncio.run(_build_started_game(mock_handler, make_user))

    for _ in range(4):
        asyncio.run(game.process_bid(-1))

    assert game.state == GameState.AUCTION
    assert game.contract == -1
    assert game.turn == 0
    assert game.declarer == game.players[0]
    assert game.consecutive_passes == 0
    assert sum(1 for evt in mock_handler.events if evt[0] == "player_passed") == 4


def test_auction_pass_counter_resets_after_valid_bid(mock_handler, make_user):
    game = asyncio.run(_build_started_game(mock_handler, make_user))

    asyncio.run(game.process_bid(-1))
    assert game.consecutive_passes == 1

    asyncio.run(game.process_bid(0))
    assert game.contract == 0
    assert game.consecutive_passes == 0

    asyncio.run(game.process_bid(-1))
    assert game.consecutive_passes == 1


def test_auction_transition_after_bid_and_three_passes(mock_handler, make_user):
    game = asyncio.run(_build_started_game(mock_handler, make_user))

    asyncio.run(game.process_bid(0))
    assert game.state == GameState.AUCTION

    for _ in range(3):
        asyncio.run(game.process_bid(-1))

    assert game.state == GameState.PARTNER_CALL
    assert game.contract == 0
    assert game.declarer == game.players[0]
    assert any(evt[0] == "bid_winner" for evt in mock_handler.events)


def test_all_pass_auction_redeals_and_requests_bid_again(mock_handler, make_user, monkeypatch):
    shuffle_calls = {"count": 0}

    def deterministic_shuffle(values):
        shift = shuffle_calls["count"] % len(values)
        values[:] = values[shift:] + values[:shift]
        shuffle_calls["count"] += 1

    monkeypatch.setattr("sgbridgebot.BridgeGame.random.shuffle", deterministic_shuffle)

    game = asyncio.run(_build_started_game(mock_handler, make_user))

    initial_hands = [[card.id for card in player.hand] for player in game.players]

    for _ in range(4):
        asyncio.run(game.process_bid(-1))

    assert game.state == GameState.AUCTION
    assert game.contract == -1
    assert game.turn == 0
    assert game.declarer == game.players[0]
    assert game.consecutive_passes == 0
    assert sum(1 for evt in mock_handler.events if evt[0] == "player_passed") == 4
    assert sum(1 for evt in mock_handler.events if evt[0] == "request_bid") >= 2

    redealt_hands = [[card.id for card in player.hand] for player in game.players]
    assert redealt_hands != initial_hands




def test_next_turn_from_auction_does_not_duplicate_first_card_prompt_for_bot_declarer(mock_handler, make_user):
    game = asyncio.run(_build_started_game(mock_handler, make_user))

    game.players[0].player_to_bot()
    game.declarer = game.players[0]
    game.contract = 0
    game.state = 1
    game.turn = 3

    asyncio.run(game.next_turn())

    request_card_events = [evt for evt in mock_handler.events if evt[0] == "request_card"]
    assert len(request_card_events) == 1

def test_partner_selection_maps_called_card_to_partner_player(mock_handler, make_user):
    game = asyncio.run(_build_started_game(mock_handler, make_user))
    game.state = GameState.PARTNER_CALL
    game.turn = 0

    called_card = game.players[2].hand[0]
    game.partner = game.player_holding_card(called_card.id)
    game.partner_card = BridgeCard(called_card.id)

    assert game.partner == game.players[2]
    assert game.partner_card.id == called_card.id


def test_partner_selection_rejects_unknown_card_ids(mock_handler, make_user):
    game = asyncio.run(_build_started_game(mock_handler, make_user))

    partner = game.player_holding_card(99)

    assert partner is None


def test_process_bid_logs_warning_for_invalid_bot_bid(mock_handler, caplog):
    game = BridgeGame(mock_handler, type=0)
    game.id = "game-123"
    bot_player = type("BotPlayer", (), {"id": 777, "is_bot": True})()
    game.players = [bot_player]
    game.turn = 0
    game.contract = 10

    with caplog.at_level(logging.WARNING):
        asyncio.run(game.process_bid(5))

    assert "Invalid bid made by bot; ignoring bid and continuing auction context" in caplog.text
    assert "game-123" in caplog.text
    assert "777" in caplog.text


def test_start_game_limits_redeals_for_perpetual_wash(mock_handler, make_user, monkeypatch, caplog):
    deal_counter = {"count": 0}

    original_deal_hands = BridgeGame.deal_hands

    def counted_deal_hands(self):
        deal_counter["count"] += 1
        original_deal_hands(self)

    monkeypatch.setattr(BridgeGame, "deal_hands", counted_deal_hands)
    monkeypatch.setattr("sgbridgebot.BridgePlayer.BridgePlayer.hand_score", lambda self, hand: 0)

    with caplog.at_level(logging.WARNING):
        game = asyncio.run(_build_started_game(mock_handler, make_user))

    assert deal_counter["count"] == MAX_REDEAL_ATTEMPTS
    assert game.state == GameState.AUCTION
    assert any(evt[0] == "request_bid" for evt in mock_handler.events)
    assert "Redeal attempt limit exceeded" in caplog.text
    assert "Accepting latest deal after redeal limit reached" in caplog.text


def test_start_game_deals_once_when_no_wash(mock_handler, make_user, monkeypatch):
    deal_counter = {"count": 0}

    original_deal_hands = BridgeGame.deal_hands

    def counted_deal_hands(self):
        deal_counter["count"] += 1
        original_deal_hands(self)

    monkeypatch.setattr(BridgeGame, "deal_hands", counted_deal_hands)
    monkeypatch.setattr("sgbridgebot.BridgePlayer.BridgePlayer.hand_score", lambda self, hand: 10)

    game = asyncio.run(_build_started_game(mock_handler, make_user))

    assert deal_counter["count"] == 1
    assert game.state == GameState.AUCTION
    assert game.turn == 0
