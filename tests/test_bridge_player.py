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


def _cards(*ids):
    return [BridgeCard(i) for i in ids]


# Card ids: clubs 0-12, diamonds 13-25, hearts 26-38, spades 39-51 (2 up to A).
SEVEN_SMALL_SPADES_AND_HEART_ACE = _cards(39, 40, 41, 42, 43, 44, 45, 38, 0, 1, 2, 13, 14)


def test_hand_score_counts_length_only_for_cards_passed_in():
    player = BridgePlayer()
    player.hand = SEVEN_SMALL_SPADES_AND_HEART_ACE

    # 4 for the heart ace, 3 for the three spades beyond four.
    assert player.hand_score(player.hand) == 7
    assert player.suit_score(3) == 3
    assert player.suit_score(2) == 4
    assert player.suit_score(0) == 0


def test_best_suit_prefers_a_long_suit_over_a_lone_ace():
    player = BridgePlayer()
    player.hand = SEVEN_SMALL_SPADES_AND_HEART_ACE

    assert player.get_best_suit() == 3


def test_make_auto_bid_passes_a_weak_hand():
    player = BridgePlayer()
    player.hand = SEVEN_SMALL_SPADES_AND_HEART_ACE  # 7 points

    assert player.make_auto_bid(-1) == -1


def test_make_auto_bid_opens_cheapest_bid_in_best_suit():
    player = BridgePlayer()
    # Spades A K Q 5 4 3 2, hearts K, clubs 2 3 4, diamonds 2 3: 15 points.
    player.hand = _cards(51, 50, 49, 42, 41, 40, 39, 37, 0, 1, 2, 13, 14)

    assert player.make_auto_bid(-1) == 3  # 1♠
    assert player.make_auto_bid(3) == 8  # 2♠ over someone else's 1♠
    assert player.make_auto_bid(4) == 8  # 2♠ over 1NT


def test_make_auto_bid_stops_at_what_the_hand_is_worth():
    player = BridgePlayer()
    player.hand = _cards(51, 50, 49, 42, 41, 40, 39, 37, 0, 1, 2, 13, 14)  # 15 points

    assert player.max_bid_level() == 3
    assert player.make_auto_bid(9) == 13  # 3♠ over 2NT
    assert player.make_auto_bid(13) == -1  # 4♠ is one level too high


def test_make_auto_bid_chooses_no_trump_with_a_strong_balanced_hand():
    player = BridgePlayer()
    # A K x x / A x x / K Q x / x x x: 16 high-card points, 4-3-3-3.
    player.hand = _cards(51, 50, 39, 40, 38, 26, 27, 24, 23, 13, 0, 1, 2)

    assert player.preferred_denomination() == 4
    assert player.make_auto_bid(-1) == 4  # 1NT


def test_make_auto_partner_calls_highest_missing_trump():
    player = BridgePlayer()
    player.hand = _cards(51, 50, 42, 41, 38, 0, 1, 2, 13, 14, 15, 16, 17)  # ♠A ♠K ...

    assert player.make_auto_partner(3) == 49  # ♠Q
    assert player.make_auto_partner(2) == 37  # ♥K, since we hold the ♥A


def test_make_auto_partner_in_no_trump_calls_a_missing_ace():
    player = BridgePlayer()
    # Holds ♠A and ♥A, five diamonds: the ♦A comes first as the longest suit.
    player.hand = _cards(51, 38, 13, 14, 15, 16, 17, 0, 1, 2, 39, 40, 26)

    assert player.make_auto_partner(4) == 25


def test_play_auto_card_discards_lowest_rank_not_lowest_id():
    player = BridgePlayer()
    player.hand = _cards(12, 13)  # ♣A, ♦2
    trick = _cards(26, 38)  # ♥2, ♥A: we are void in hearts and it's no trump

    played = player.play_auto_card(trick, DummyGame(trump_suit=4))

    assert played.id == 13  # ♦2, keeping the ♣A


def test_play_auto_card_leads_low_from_longest_side_suit():
    player = BridgePlayer()
    game = DummyGame(trump_suit=3, trump_broken=False)
    player.hand = _cards(11, 14, 15, 16, 17, 40)  # ♣K, ♦3 4 5 6, ♠3

    played = player.play_auto_card([], game)

    assert played.id == 14


class SeatedGame(DummyGame):
    '''A dummy game that knows seats and who is on which side.'''

    def __init__(self, players, trick_start, teammates, **kwargs):
        super().__init__(**kwargs)
        self.players = players
        self.trick_start = trick_start
        self.teammates = teammates

    def known_teammate(self, viewer, other):
        return other in self.teammates


def test_play_auto_card_does_not_ruff_a_trick_its_teammate_is_winning():
    seats = [BridgePlayer() for _ in range(4)]
    bot = seats[3]
    bot.hand = _cards(0, 40)  # ♣2, ♠3 (trump)
    game = SeatedGame(seats, trick_start=0, teammates=[seats[1]], trump_suit=3)
    trick = _cards(26, 38, 30)  # ♥2, ♥A (teammate), ♥6

    played = bot.play_auto_card(trick, game)

    assert played.id == 0


def test_play_auto_card_still_ruffs_when_an_opponent_is_winning():
    seats = [BridgePlayer() for _ in range(4)]
    bot = seats[3]
    bot.hand = _cards(0, 40)
    game = SeatedGame(seats, trick_start=0, teammates=[], trump_suit=3)
    trick = _cards(26, 38, 30)

    played = bot.play_auto_card(trick, game)

    assert played.id == 40


def test_play_auto_card_does_not_overtake_a_teammate_in_last_seat():
    seats = [BridgePlayer() for _ in range(4)]
    bot = seats[3]
    bot.hand = _cards(27, 37)  # ♥3, ♥K
    game = SeatedGame(seats, trick_start=0, teammates=[seats[2]], trump_suit=3)
    trick = _cards(26, 30, 35)  # ♥2, ♥6, ♥J (teammate)

    played = bot.play_auto_card(trick, game)

    assert played.id == 27


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
