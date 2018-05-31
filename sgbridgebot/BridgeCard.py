


class BridgeCard(object):

    '''
    Instance of a standard poker card.

    ATTRIBS
    rank (int): [2:14] (2 through A)
    suit (int): [1:4] (Club/Diamond/Heart/Spade)

    ARGS
    get_rank: gets rank in string format
    get_suit: gets suit in string format
    '''

    def __init__(self, id):
        if not isinstance(id, int):
            raise TypeError('BridgeCard(): id must be an integer')
        if id < 1 or id > 52:
            raise Exception('BridgeCard(): id is not valid (1-52)')
        self.id = id
        self.rank = id % 13 + 1
        self.suit = id / 4

    def __repr__(self):
        return self.get_rank() + " of " + self.get_suit()

    def get_id(self):
        return id

    def get_rank(self):
        return {'2': 2,
                '3': 3,
                '4': 4,
                '5': 5,
                '6': 6,
                '7': 7,
                '8': 8,
                '9': 9,
                '10': 10,
                'Jack': 11,
                'Queen': 12,
                'King': 13,
                'Ace': 14,
                }[self.rank]

    def get_suit(self):
        return {'Clubs': 0,
                'Diamonds': 1,
                'Hearts': 2,
                'Spades': 3,
                }[self.suit]
