from BridgeCard import BridgeCard


class BridgeHand(object):

    '''
    A player's hand.

    ATTRIBUTES
    cards (listof BridgeCard): holds a list of BridgeCard objects. Is the player's actual hand
    pos (int): player's position (NESW/1234)

    ARGS
    get_cards(): returns all the player's Cards
    get_all_suit(suit): returns a list of cards of the desired suit, or empty list
    get_top_suit(suit): returns only the top card of the specified suit, or None

    '''

    def __init__(self, cards, pos):
        if not isinstance(cards, list):
            raise TypeError('BridgeHand(): cards is not a list')
        if not isinstance(pos, int) or pos < 1 or pos > 4:
            raise TypeError('BridgeHand(): pos is not a valid number 1-4')
        self.cards = cards
        self.pos = pos

    def get_cards(self):
        return cards

    def get_pos(self):
        return pos

    def get_all_suit(self, suit):
        matches = []
        for c in self.cards:
            if c.suit == suit:
                matches.append(c)
        return matches

    def get_top_suit(self, suit):
        top = None
        for c in self.cards:
            if c.suit == suit and (top_card is None or c.rank > top.rank):
                top = c
        return top
