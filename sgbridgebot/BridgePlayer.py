from telegram import User
import random


class BridgePlayer(User):

    '''
    Extends telegram.user and represents a single player of the game.

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
    make_auto_bid()


    '''

    def __init__(self, user=None, chat_id=None):
        self.is_bot = not isinstance(user, User)
        self.chat_id = chat_id
        self.hand = []
        self.direction = 0
        self.id = 0
        self.tricks_won = 0
        if self.is_bot:
            self.player_to_bot()
        else:
            self.player_to_user(user)

    def __eq__(self, other):
        return self.id == other.id

    def player_to_bot(self):
        self.is_bot = 1
        self.chat_id = None
        self.first_name = 'BotPlayer' + str(random.randint(100,999))
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
            return 1
        else:
            return -1

    def disp_name(self):
        return self.username if self.username else self.first_name

    def get_cards(self):
        return self.hand

    def hand_score(self, hand):
        score = 0
        for c in hand:
            if c.rank > 10:
                score += c.rank - 10
        for s in range(4):
            cards_suit = self.get_all_suit(s)
            if len(cards_suit) > 4:
                score += len(cards_suit) - 4
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
        suit = 0
        score = 0
        for s in range(4):
            suit_score = self.hand_score(self.get_all_suit(s))
            if  suit_score > score:
                score = suit_score
                suit = s
        return suit

    def make_auto_bid(self, contract):
        if contract > 33 or random.randint(0, (contract+2)^2) > self.hand_score(self.hand)/3:
            return -1
        else:
            # can't go above 7NT
            suit = self.get_best_suit()
            bid = -1
            if (contract%5 < suit):
                bid = contract - contract%5 + suit
            elif (contract%5 > suit):
                bid = contract - contract%5 + suit + 5
            return min(34, bid)

    def make_auto_partner(self):
        #TODO: implement partner choosing algorithm for bot
        suit = self.get_best_suit()
        cards = self.get_all_suit(suit)
        for rank in reversed(range(2,15)):
            if rank not in [c.rank for c in cards]:
                break
        return rank-2 + suit*13

    def play_auto_card(self, trick, game):
        # TODO: make bots partner aware?
        # TODO: implement better last in trick strategy

        # some vars
        trump_suit = game.get_trump_suit()

        if len(self.hand) == 0:
            return None

        # pick random card if leading
        # possibly top trump card if already broken
        if len(trick) == 0:
            for suit in range(4):
                # can't play trump if not broken
                if suit == trump_suit and not game.trump_broken:
                    continue
                top_card = self.get_top_card_in_suit(suit)
                # play top card if that's cool
                if self.is_highest_remaining_in_suit(top_card, game):
                    self.hand.remove(top_card)
                    return top_card
            # else pick random low card that's not trump
            low_cards = []
            for suit in range(4):
                if suit != trump_suit:
                    low_card = self.get_lowest_card_in_suit(suit)
                    if low_card is not None:
                        low_cards.append(low_card)
            low_cards.sort(key=lambda c: c.id)
            if len(low_cards) > 0:
                self.hand.remove(low_cards[0])
                return low_cards[0]
            # it's probably trump left
            return self.hand.pop(0)

        # get leading/suit card info
        leading_suit = trick[0].suit
        top_suit_card = self.get_top_card_in_suit(leading_suit)
        suit_cards = self.get_all_suit(leading_suit)

        # out of cards in suit
        if len(suit_cards) == 0:

            # check if can trump, if so please trump
            highest_trick_trump = 0
            for c in game.trick:
                if c.rank > highest_trick_trump:
                    highest_trick_trump = c.rank
            trump_cards = self.get_all_suit(trump_suit)
            for card in trump_cards:
                if card.rank > highest_trick_trump:
                    self.hand.remove(card)
                    return card

            #couldn't find suitable trump card, play random low card
            low_cards = []
            for suit in range(4):
                if suit != trump_suit:
                    low_card = self.get_lowest_card_in_suit(suit)
                    if low_card is not None:
                        low_cards.append(low_card)
            low_cards.sort(key=lambda c: c.id)
            if len(low_cards) > 0:
                self.hand.remove(low_cards[0])
                return low_cards[0]
            #if not just take random low card
            return self.hand.pop(0)

        # since you are not leading, play what you can
        trump_in_trick = False
        for c in trick:
            if c.suit == trump_suit:
                trump_in_trick = True
                break
        if self.is_highest_remaining_in_suit(top_suit_card, game) and not trump_in_trick:
            self.hand.remove(top_suit_card)
            return top_suit_card
        # play good card if possible
        elif len(trick) == 4:
            can_win = 1
            for card in suit_cards:
                if card.suit == trump_suit:
                    can_win = 0
                if card.suit == leading_suit and card.rank > suit_cards[-1].rank:
                    can_win = 0
            if can_win:
                self.hand.remove(suit_cards[-1])
                return suit_cards[-1]

        # give up, just play lowest card in suit
        self.hand.remove(suit_cards[0])
        return suit_cards[0]


    def is_highest_remaining_in_suit(self, card, game):
        if card is None:
            return False
        suit = card.suit
        cards_played = self.get_cards_played_in_suit(suit, game)
        for rank in reversed(range(2,15)):
            if rank in [c.rank for c in cards_played]:
                continue
            return card.rank == rank
        return false

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
        return
