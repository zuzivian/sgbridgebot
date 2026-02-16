from sgbridgebot.StringUtils import StringUtils


class FakePlayer:
    def __init__(self, username, first_name):
        self.username = username
        self.first_name = first_name


class FakeGame:
    def __init__(self, players):
        self.players = players

    def num_players(self):
        return len(self.players)


def test_player_name_prefers_username_then_first_name():
    su = StringUtils()
    assert su.player_name(FakePlayer("alice", "Alice")) == "alice"
    assert su.player_name(FakePlayer(None, "Bob")) == "Bob"


def test_room_messages_include_player_count_and_names():
    su = StringUtils()
    game = FakeGame([FakePlayer("alice", "Alice"), FakePlayer(None, "Bob")])

    assert su.player_listing(game) == "alice, Bob"
    msg = su.players_in_room(game)
    assert "Number of players: 2/4" in msg
    assert "alice, Bob" in msg


def test_bid_and_card_conversion_round_trip():
    su = StringUtils()

    assert su.bid_str_to_id("PASS") == -1
    assert su.bid_str_to_id("1♣") == 0
    assert su.bid_id_to_str(0) == "1♣"
    assert su.bid_id_to_str(4) == "1NT"

    assert su.card_str_to_id("♣2") == 0
    assert su.card_str_to_id("♠A") == 51
    assert su.card_str_to_id(f"{su.suit_str[2]}10") == 34


def test_bid_str_to_id_rejects_malformed_inputs():
    su = StringUtils()

    for value in ["", "   ", "1", "0♣", "8NT", "1X", "1N"]:
        try:
            su.bid_str_to_id(value)
            assert False, f"Expected ValueError for bid {value!r}"
        except ValueError:
            pass


def test_card_str_to_id_rejects_malformed_inputs():
    su = StringUtils()

    for value in ["", "   ", "♣", "X10", "♣1", "♣11", "♣Z"]:
        try:
            su.card_str_to_id(value)
            assert False, f"Expected ValueError for card {value!r}"
        except ValueError:
            pass
