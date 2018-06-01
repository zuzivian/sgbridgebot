from telegram import User
import random


class BridgePlayer(User):

    '''
    '''

    def __init__(self, user=None, chat_id=None):
        self.is_bot = not isinstance(user, User)
        self.chat_id = chat_id
        self.hand = []
        self.direction = 0
        if self.is_bot:
            self.player_to_bot()
        else:
            self.player_to_user(user)

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
        if self.direction == -1:
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

    def hand_score(self):
        score = 0
        for c in self.hand:
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
        return matches

    def get_top_suit(self, suit):
        top = None
        for c in self.hand:
            if c.suit == suit and (top_card is None or c.rank > top.rank):
                top = c
        return top

    def make_auto_bid(self, contract):
        # TODO: implement bidding algorithm for bot
        return -1
