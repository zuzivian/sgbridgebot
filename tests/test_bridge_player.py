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
