import random

from telegram import User

# Points (high cards plus length) a bot needs to open the bidding, and per extra level.
BID_OPENING_POINTS = 10
BID_POINTS_PER_LEVEL = 2
# High-card points a balanced hand needs before a bot prefers no trump.
NT_MIN_HCP = 15


class BridgePlayer:

    '''
    Represents a single player of the game.

    ATTRIBUTES
    is_bot (bool)
    chat_id (int)
    hand (listof BridgeCard)
    direction (int): 1:S 2:W 3:N 4:E
    first_name (str)
    username (str or None)
    id (int)

    ARGS
    player_to_bot(): converts a player into a bot
    player_to_user(user): converts player until a user
    give_direction(dir): give player a direction (NSEW)
    disp_name(): returns the display name of the player
    get_cards(): get player's hand
    hand_score(): returns score of player's hand
    get_all_suit(suit): returns a list of BridgeCard that match the given suit
    get_top_card_in_suit(suit): returns the highest valued BridgeCard that matches the suit
    make_auto_bid(contract): cheapest bid the hand is worth, or -1 to pass
    make_auto_partner(trump_suit): card id to call as partner
    play_auto_card(trick, game): picks, removes and returns a legal card


    '''

    def __init__(self, user=None, chat_id=None):
        self.is_bot = not isinstance(user, User)
        self.chat_id = chat_id
        self.hand = []
        self.direction = 0
        self.id = 0
        self.tricks_won = 0
        # Set once a private message to this player has failed.
        self.dm_blocked = False
        if self.is_bot:
            self.player_to_bot()
        else:
            self.player_to_user(user)

    def __eq__(self, other):
        return self.id == other.id

    def player_to_bot(self):
        if self.is_bot:
            self.first_name = 'Player' + str(random.randint(100,999))
        else:
            # Keep the seat recognisable when a bot takes over from a human.
            self.first_name = self.disp_name() + ' (bot)'
        self.is_bot = True
        self.chat_id = None
        self.username = None
        self.id = -self.direction


    def player_to_user(self, user):
        self.id = user.id
        self.username = user.username
        self.first_name = user.first_name

    def give_direction(self, dir):
        if self.direction == 0:
            self.direction = dir
            if self.is_bot:
                self.id = -self.direction
                self.first_name = {1:'South',2:'West',3:'North',4:'East'}[self.direction]
            return 1
        else:
            return -1

    def disp_name(self):
        return self.username if self.username else self.first_name

    def get_cards(self):
        return self.hand

    def hand_score(self, hand):
        '''
        Points for a set of cards: A=4, K=3, Q=2, J=1, plus one for each card
        beyond four in a suit. Only the cards passed in are counted.
        '''
        score = 0
        for c in hand:
            if c.rank > 10:
                score += c.rank - 10
        for s in range(4):
            suit_length = len([c for c in hand if c.suit == s])
            if suit_length > 4:
                score += suit_length - 4
        return score

    def get_all_suit(self, suit):
        matches = []
        for c in self.hand:
            if c.suit == suit:
                matches.append(c)
        matches.sort(key=lambda c: c.id)
        return matches

    def get_top_card_in_suit(self, suit):
        cards = self.get_all_suit(suit)
        if len(cards) > 0:
            return cards[-1]
        else:
            return None

    def get_lowest_card_in_suit(self, suit):
        cards = self.get_all_suit(suit)
        if len(cards) > 0:
            return cards[0]
        else:
            return None

    def get_best_suit(self):
        # Length matters most for a trump suit, then the honours in it.
        # Ties go to the higher-ranking suit, which is cheaper to outbid with.
        return max(
            range(4),
            key=lambda s: (len(self.get_all_suit(s)) + self.suit_score(s), s),
        )

    def suit_score(self, suit):
        return self.hand_score(self.get_all_suit(suit))

    def high_card_points(self):
        return sum(c.rank - 10 for c in self.hand if c.rank > 10)

    def is_balanced(self):
        lengths = sorted(len(self.get_all_suit(s)) for s in range(4))
        # 4-3-3-3, 4-4-3-2 or 5-3-3-2 shapes.
        return lengths[0] >= 2 and lengths[3] <= 5 and lengths[1] >= 3

    def max_bid_level(self):
        '''
        The highest level (1-7) this hand is worth bidding to, or 0 to pass.
        Opening needs 10 points; each further level needs 2 more.
        '''
        points = self.hand_score(self.hand)
        if points < BID_OPENING_POINTS:
            return 0
        return min(7, 1 + (points - BID_OPENING_POINTS) // BID_POINTS_PER_LEVEL)

    def preferred_denomination(self):
        '''
        0-3 for a suit, 4 for no trump.
        '''
        if self.is_balanced() and self.high_card_points() >= NT_MIN_HCP:
            return 4
        return self.get_best_suit()

    def make_auto_bid(self, contract):
        '''
        Returns the cheapest bid above the contract in this hand's preferred
        denomination, or -1 to pass when that would go past what the hand is worth.
        '''
        max_level = self.max_bid_level()
        if max_level == 0:
            return -1
        bid = self.preferred_denomination()
        while bid <= contract:
            bid += 5
        if bid > 34 or bid // 5 + 1 > max_level:
            return -1
        return bid

    def make_auto_partner(self, trump_suit=None):
        '''
        Calls the highest trump this player does not hold. In no trump, calls
        a missing ace, starting with the longest suit, then kings and so on.
        '''
        held = {c.id for c in self.hand}
        if trump_suit is None:
            trump_suit = self.get_best_suit()
        if 0 <= trump_suit <= 3:
            suits = [trump_suit]
        else:
            suits = sorted(range(4), key=lambda s: -len(self.get_all_suit(s)))
        for rank in range(14, 1, -1):
            for suit in suits:
                card_id = suit * 13 + rank - 2
                if card_id not in held:
                    return card_id
        # Holding every candidate: calling one of our own cards means playing alone.
        return suits[0] * 13 + 12

    def _teammate_relation(self, game, other):
        '''
        True if this player knows `other` is on its side, False if it knows
        they are not, None if it cannot tell yet.
        '''
        relation = getattr(game, 'known_teammate', None)
        if relation is None or other is None:
            return None
        return relation(self, other)

    def _trick_winner_owner(self, trick, game, trump_suit):
        players = getattr(game, 'players', None)
        trick_start = getattr(game, 'trick_start', None)
        if not players or trick_start is None or len(players) != 4:
            return None
        winner = self.get_current_trick_winner_card(trick, trump_suit)
        return players[(trick_start + trick.index(winner)) % 4]

    def _no_higher_outstanding(self, card, trick, game):
        '''
        True when every higher card of this suit is already played or in our hand.
        '''
        seen = {c.id for c in self.hand} | {c.id for c in trick}
        for played in game.trick_history:
            seen.update(c.id for c in played)
        return all(card.suit * 13 + rank - 2 in seen for rank in range(card.rank + 1, 15))

    def _lowest_discard(self, trump_suit):
        '''
        The lowest non-trump card, from the shortest suit on a tie, to keep
        high cards and long suits. Falls back to the lowest trump.
        '''
        others = [c for c in self.hand if c.suit != trump_suit]
        if others:
            return min(others, key=lambda c: (c.rank, len(self.get_all_suit(c.suit))))
        return min(self.hand, key=lambda c: c.rank)

    def _take(self, card):
        self.hand.remove(card)
        return card

    def play_auto_card(self, trick, game):
        trump_suit = game.get_trump_suit()

        if len(self.hand) == 0:
            return None

        # Leading: cash a sure winner, otherwise lead low from the longest side suit.
        if len(trick) == 0:
            for suit in range(4):
                # can't play trump if not broken
                if suit == trump_suit and not game.trump_broken:
                    continue
                top_card = self.get_top_card_in_suit(suit)
                if self.is_highest_remaining_in_suit(top_card, game):
                    return self._take(top_card)
            side_suits = [s for s in range(4) if s != trump_suit and self.get_all_suit(s)]
            if side_suits:
                longest = max(side_suits, key=lambda s: (len(self.get_all_suit(s)), -s))
                return self._take(self.get_all_suit(longest)[0])
            # Only trumps left, which may be led even before trump is broken.
            return self._take(min(self.hand, key=lambda c: c.rank))

        leading_suit = trick[0].suit
        top_suit_card = self.get_top_card_in_suit(leading_suit)
        suit_cards = self.get_all_suit(leading_suit)
        current_winner = self.get_current_trick_winner_card(trick, trump_suit)
        teammate_winning = self._teammate_relation(
            game, self._trick_winner_owner(trick, game, trump_suit)
        ) is True
        teammate_safe = teammate_winning and (
            len(trick) == 3
            or current_winner.suit == trump_suit
            or self._no_higher_outstanding(current_winner, trick, game)
        )

        # out of cards in suit
        if len(suit_cards) == 0:
            if teammate_safe:
                return self._take(self._lowest_discard(trump_suit))
            # Ruff with the cheapest trump that beats any trump already played.
            highest_trick_trump = 0
            for c in trick:
                if c.rank > highest_trick_trump and c.suit == trump_suit:
                    highest_trick_trump = c.rank
            for card in self.get_all_suit(trump_suit):
                if card.rank > highest_trick_trump:
                    return self._take(card)
            return self._take(self._lowest_discard(trump_suit))

        if teammate_safe:
            return self._take(suit_cards[0])

        # Among legal follow-suit cards, find the cards that currently win this trick.
        winning_cards = [
            card for card in suit_cards
            if self.card_wins_over(card, current_winner, leading_suit, trump_suit)
        ]

        # Last seat wins as cheaply as it can.
        if len(trick) == 3 and len(winning_cards) > 0:
            return self._take(winning_cards[0])

        # In 2nd/3rd seat, cash a likely winner only when it can beat the current trick winner
        # and appears to be the top remaining card in the suit.
        if len(winning_cards) > 0 and self.is_highest_remaining_in_suit(top_suit_card, game):
            return self._take(top_suit_card)

        # give up, just play lowest card in suit
        return self._take(suit_cards[0])

    def get_current_trick_winner_card(self, trick, trump_suit):
        if len(trick) == 0:
            return None
        leading_suit = trick[0].suit
        winner = trick[0]
        for card in trick[1:]:
            if self.card_wins_over(card, winner, leading_suit, trump_suit):
                winner = card
        return winner

    def card_wins_over(self, challenger, current_winner, leading_suit, trump_suit):
        if current_winner is None:
            return True
        challenger_is_trump = challenger.suit == trump_suit
        winner_is_trump = current_winner.suit == trump_suit

        if challenger_is_trump and not winner_is_trump:
            return True
        if challenger_is_trump and winner_is_trump:
            return challenger.rank > current_winner.rank
        if winner_is_trump:
            return False
        if challenger.suit == leading_suit and current_winner.suit == leading_suit:
            return challenger.rank > current_winner.rank
        return False


    def is_highest_remaining_in_suit(self, card, game):
        if card is None:
            return False
        suit = card.suit
        cards_played = self.get_cards_played_in_suit(suit, game)
        for rank in reversed(range(2,15)):
            if rank in [c.rank for c in cards_played]:
                continue
            return card.rank == rank
        return False

    def get_cards_played_in_suit(self, suit, game):
        cards = []
        for trick in game.trick_history:
            for card in trick:
                if card.suit == suit:
                    cards.append(card)
        return cards

    def remove_card(self, card):
        for c in self.hand:
            if c.id == card.id:
                self.hand.remove(c)
                return c
        return None
