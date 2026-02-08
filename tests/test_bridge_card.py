import pytest

from sgbridgebot.BridgeCard import BridgeCard


def test_bridge_card_maps_rank_and_suit_and_repr():
    card = BridgeCard(0)
    assert card.rank == 2
    assert card.suit == 0
    assert card.get_rank() == "2"
    assert card.get_suit() == "♣"
    assert repr(card) == "♣2"


def test_bridge_card_handles_upper_boundary():
    card = BridgeCard(51)
    assert card.rank == 14
    assert card.suit == 3
    assert repr(card) == "♠A"


@pytest.mark.parametrize("bad_id", [None, "1", 3.14])
def test_bridge_card_rejects_non_integer_ids(bad_id):
    with pytest.raises(TypeError):
        BridgeCard(bad_id)


@pytest.mark.parametrize("bad_id", [-1, 52])
def test_bridge_card_rejects_out_of_range_ids(bad_id):
    with pytest.raises(Exception):
        BridgeCard(bad_id)
