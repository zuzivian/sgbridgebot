import logging
import asyncio

import pytest

from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.BridgeGame import BridgeGame, MAX_IDLE_STRIKES, MAX_REDEAL_ATTEMPTS
from sgbridgebot.errors import AlreadyInGameError, InvalidPlayError
from sgbridgebot.game_types import GameState, GameType


async def _build_started_game(mock_handler, make_user):
    game = BridgeGame(mock_handler, type=GameType.MATCHMAKING)
    for i in range(4):
        state = await game.add_player(make_user(i + 1, username=f"u{i+1}"), 100 + i)
        assert state is game
    return game


def test_player_join_leave_lifecycle(mock_handler, make_user):
    game = BridgeGame(mock_handler, type=GameType.MATCHMAKING)

    asyncio.run(game.add_player(make_user(1, username="u1"), 101))
    assert game.num_players() == 1

    with pytest.raises(AlreadyInGameError):
        asyncio.run(game.add_player(make_user(1, username="u1"), 101))

    asyncio.run(game.remove_player(make_user(1, username="u1"), 101))
    assert game.num_players() == 0


def test_transition_from_lobby_to_started_game(mock_handler, make_user):
    game = asyncio.run(_build_started_game(mock_handler, make_user))

    assert game.state == GameState.AUCTION
    assert game.num_players() == 4
    assert game.turn == 0
    assert any(evt[0] == "starting_game" for evt in mock_handler.events)
    assert any(evt[0] == "request_bid" for evt in mock_handler.events)


def test_valid_play_rules(mock_handler, make_user):
    game = BridgeGame(mock_handler, type=GameType.MATCHMAKING)
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


def _rig_play_state(game, hand, trump_suit=3):
    game.state = GameState.PLAY
    game.contract = trump_suit  # level 1 in the trump suit
    game.declarer = game.players[1]
    game.partner = game.players[2]
    game.partner_card = BridgeCard(0)
    game.turn = 0
    game.trick = []
    game.trick_start = 0
    game.trump_broken = 0
    game.players[0].hand = hand


def test_all_trump_hand_may_lead_trump_before_it_is_broken(mock_handler, make_user):
    game = asyncio.run(_build_started_game(mock_handler, make_user))
    _rig_play_state(game, [BridgeCard(39 + r) for r in range(5)])  # five spades

    is_valid, reason, legal = game.valid_play_details(BridgeCard(39))

    assert is_valid is True and reason is None
    assert game.legal_cards(game.players[0]) == [repr(c) for c in game.players[0].hand]

    asyncio.run(game.play_card(game.players[0], 39))
    assert game.trump_broken == 1
    assert [c.id for c in game.trick] == [39]


def test_trump_lead_still_refused_when_hand_has_other_suits(mock_handler, make_user):
    game = asyncio.run(_build_started_game(mock_handler, make_user))
    _rig_play_state(game, [BridgeCard(39), BridgeCard(13)])

    with pytest.raises(InvalidPlayError) as exc_info:
        game.validate_card(game.players[0], 39)

    assert "not broken" in str(exc_info.value)
    assert exc_info.value.legal_cards == ["♦2"]


def test_removing_player_on_turn_lets_replacement_bot_act(mock_handler, make_user):
    async def scenario():
        game = await _build_started_game(mock_handler, make_user)
        seq = game.action_seq
        await game.remove_player(make_user(1, username="u1"), 100)
        return game, seq

    game, seq = asyncio.run(scenario())
    assert game.players[0].is_bot
    assert game.action_seq > seq
    assert not game.curr_player().is_bot
    assert sum(1 for evt in mock_handler.events if evt[0] == "request_bid") == 2


def test_last_human_leaving_abandons_game(mock_handler, make_user):
    finished = []

    async def scenario():
        game = BridgeGame(mock_handler, GameType.MATCHMAKING, on_game_complete=finished.append)
        await game.add_player(make_user(1, username="u1"), 100)
        for _ in range(3):
            await game.add_bot()
        await game.remove_player(make_user(1, username="u1"), 100)
        return game

    game = asyncio.run(scenario())
    assert game.state == GameState.SCORING
    assert finished == [game.id]


def test_idle_player_is_auto_played_then_handed_to_a_bot(mock_handler, make_user):
    async def scenario():
        game = BridgeGame(mock_handler, GameType.MATCHMAKING, turn_timeout=0.01, bot_pause=0)
        for i in range(4):
            await game.add_player(make_user(i + 1, username=f"u{i+1}"), 100 + i)
        for _ in range(200):
            if game.players[0].is_bot or not game.is_in_progress():
                break
            await asyncio.sleep(0.01)
        game._cancel_idle_timer()
        return game

    game = asyncio.run(scenario())
    timeouts = [evt for evt in mock_handler.events if evt[0] == "player_timed_out"]
    first_seat = [evt for evt in timeouts if evt[1] == 1]
    assert [evt[2] for evt in first_seat][:MAX_IDLE_STRIKES] == [False] * (MAX_IDLE_STRIKES - 1) + [True]
    assert game.players[0].is_bot


def test_stale_idle_timer_does_nothing_after_player_acts(mock_handler, make_user):
    async def scenario():
        game = BridgeGame(mock_handler, GameType.MATCHMAKING, turn_timeout=0.05, bot_pause=0)
        for i in range(4):
            await game.add_player(make_user(i + 1, username=f"u{i+1}"), 100 + i)
        stale_seq = game.action_seq
        async with game.lock:
            await game.make_bid(game.players[0], 0)
        game._cancel_idle_timer()
        # A timer armed before the bid wakes up late: it must see the turn moved on.
        await game._idle_timeout(stale_seq)
        return game

    game = asyncio.run(scenario())
    assert not [evt for evt in mock_handler.events if evt[0] == "player_timed_out"]
    assert game.contract == 0
