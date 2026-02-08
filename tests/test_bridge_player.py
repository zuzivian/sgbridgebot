from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.BridgePlayer import BridgePlayer


class DummyGame:
    def __init__(self, trick_history=None):
        self.trick_history = trick_history or []


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


def test_remove_card_returns_none_and_keeps_hand_when_card_missing():
    player = BridgePlayer()
    player.hand = [BridgeCard(0), BridgeCard(10)]

    removed = player.remove_card(BridgeCard(20))

    assert removed is None
    assert [card.id for card in player.hand] == [0, 10]

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
