from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.BridgePlayer import BridgePlayer


class DummyGame:
    def __init__(self, trick_history=None, trump_suit=3, trump_broken=True):
        self.trick_history = trick_history or []
        self.trump_suit = trump_suit
        self.trump_broken = trump_broken
        self.trick = []

    def get_trump_suit(self):
        return self.trump_suit


def test_bridge_player_defaults_to_bot_with_boolean_flag():
    player = BridgePlayer()

    assert isinstance(player.is_bot, bool)
    assert player.is_bot is True


def test_player_to_bot_sets_boolean_flag(monkeypatch):
    player = BridgePlayer()
    player.is_bot = False

    monkeypatch.setattr("sgbridgebot.BridgePlayer.random.randint", lambda a, b: 123)
    player.player_to_bot()

    assert isinstance(player.is_bot, bool)
    assert player.is_bot is True


def test_bridge_player_user_has_boolean_non_bot_flag(make_user):
    player = BridgePlayer(user=make_user(42, username="alice", first_name="Alice"))

    assert isinstance(player.is_bot, bool)
    assert player.is_bot is False


def test_is_highest_remaining_in_suit_returns_boolean_without_exception():
    player = BridgePlayer()
    card = BridgeCard(0)  # 2 of clubs

    # all clubs already played, so there is no remaining rank to beat against
    all_clubs = [BridgeCard(rank - 2) for rank in range(2, 15)]
    game = DummyGame(trick_history=[all_clubs])

    result = player.is_highest_remaining_in_suit(card, game)

    assert isinstance(result, bool)
    assert result is False


def test_make_auto_bid_uses_exponent_for_random_threshold(monkeypatch):
    player = BridgePlayer()
    called = {}

    def fake_randint(a, b):
        called["args"] = (a, b)
        return 0

    monkeypatch.setattr("sgbridgebot.BridgePlayer.random.randint", fake_randint)

    bid = player.make_auto_bid(3)

    assert called["args"] == (0, 64)
    assert bid == 5


def test_make_auto_bid_deterministic_with_patched_random(monkeypatch):
    player = BridgePlayer()

    monkeypatch.setattr("sgbridgebot.BridgePlayer.random.randint", lambda a, b: 999)
    assert player.make_auto_bid(1) == -1

    monkeypatch.setattr("sgbridgebot.BridgePlayer.random.randint", lambda a, b: 0)
    assert player.make_auto_bid(1) == 5


def test_remove_card_existing_card_returns_removed_card_and_updates_hand():
    player = BridgePlayer()
    card_to_remove = BridgeCard(0)
    second_card = BridgeCard(1)
    player.hand = [card_to_remove, second_card]

    removed = player.remove_card(card_to_remove)

    assert removed == card_to_remove
    assert [card.id for card in player.hand] == [second_card.id]


def test_remove_card_missing_card_returns_none_without_crashing():
    player = BridgePlayer()
    existing_card = BridgeCard(0)
    missing_card = BridgeCard(12)
    player.hand = [existing_card]

    removed = player.remove_card(missing_card)

    assert removed is None
    assert [card.id for card in player.hand] == [existing_card.id]


def test_remove_card_missing_card_keeps_hand_intact_with_multiple_cards():
    player = BridgePlayer()
    player.hand = [BridgeCard(0), BridgeCard(10), BridgeCard(25)]

    removed = player.remove_card(BridgeCard(51))

    assert removed is None
    assert [card.id for card in player.hand] == [0, 10, 25]


def test_play_auto_card_second_seat_beats_current_winner_when_possible():
    player = BridgePlayer()
    game = DummyGame(
        trump_suit=3,
        trick_history=[[BridgeCard(36), BridgeCard(37), BridgeCard(38)]],  # hearts Q, K, A
    )
    player.hand = [BridgeCard(26), BridgeCard(35)]  # hearts 2, hearts J
    trick = [BridgeCard(34)]  # hearts 10

    played = player.play_auto_card(trick, game)

    assert played.id == 35


def test_play_auto_card_third_seat_uses_current_winner_context_when_trumped():
    player = BridgePlayer()
    game = DummyGame(trump_suit=3)
    player.hand = [BridgeCard(26), BridgeCard(38)]  # hearts 2, hearts A
    trick = [BridgeCard(34), BridgeCard(39)]  # hearts 10, spade 2 (trump)

    played = player.play_auto_card(trick, game)

    assert played.id == 26


def test_play_auto_card_last_seat_branch_plays_winning_card_before_fourth_play():
    player = BridgePlayer()
    game = DummyGame(trump_suit=3)
    player.hand = [BridgeCard(26), BridgeCard(37)]  # hearts 2, hearts K
    trick = [BridgeCard(34), BridgeCard(35), BridgeCard(36)]  # hearts 10, J, Q

    played = player.play_auto_card(trick, game)

    assert played.id == 37
