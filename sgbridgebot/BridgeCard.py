# -*- coding: utf-8 -*-



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
        if id < 0 or id > 51:
            raise Exception('BridgeCard(): id is not valid (0-51)')
        self.id = id
        self.rank = id % 13 + 2
        self.suit = id / 13

    def __repr__(self):
        return self.get_suit() + self.get_rank()

    def get_id(self):
        return id

    def get_rank(self):
        return {2: '2',
                3: '3',
                4: '4',
                5: '5',
                6: '6',
                7: '7',
                8: '8',
                9: '9',
                10: '10',
                11: 'J',
                12: 'Q',
                13: 'K',
                14: 'A'
                }[self.rank]

    def get_suit(self):
        return {0: u'\U00002663',
                1: u'\U00002666',
                2: u'\U00002764',
                3: u'\U00002660',
                }[self.suit]
