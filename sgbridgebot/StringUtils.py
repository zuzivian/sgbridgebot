# -*- coding: utf-8 -*-


class StringUtils(object):

    '''
    '''

    def __init__(self):
        self.type = None
        self.suit_str = [u'\U00002663', u'\U00002666', u'\U00002764', u'\U00002660']

    def player_name(self, player):
        return player.username if player.username else player.first_name

    def player_listing(self, game):
        return ", ".join([self.player_name(p) for p in game.players])

    def players_in_room(self, game):
        return 'Number of players: {}/4\nPlayers in the room: {}'.format(
            game.num_players(),
            self.player_listing(game))

    def joined_game(self, player, game):
        join_remark = '{} joined the game.'.format(self.player_name(player))
        room_players = self.players_in_room(game)
        return join_remark + '\n\n' + room_players

    def left_game(self, player, game):
        leave_remark = '{} left the game.'.format(self.player_name(player))
        room_players = self.players_in_room(game)
        return leave_remark + '\n\n' + room_players

    def cards_in_hand(self, player):
        message = "You have the following cards in your hand:\n"
        for suit in range(4):
            cards = player.get_all_suit(suit)
            message += self.suit_str[suit] + ": "
            message += ",  ".join([c.get_rank() for c in cards])
            message += "\n"
        return message

    def bid_str_to_id(self, text):
        text.encode('UTF8')
        if text == 'PASS':
            return -1
        for suit in range(5):
            if suit < 4 and text[1] in self.suit_str[suit]:
                break
        return suit + 5*(int(text[0])-1)

    def bid_id_to_str(self, id):
        bid = (id/5) + 1
        s = (id % 5)
        suit = self.suit_str[s] if s != 4 else 'NT'
        return unicode(bid)+suit

    def card_str_to_id(self, text):
        text.encode('UTF8')
        for suit in range(4):
            if text[0] in self.suit_str[suit]:
                break
        if text[1] == 'J':
            rank = 11
        elif text[1] == 'Q':
            rank = 12
        elif text[1] == 'K':
            rank = 13
        elif text[1] == 'A':
            rank = 14
        else:
            rank = int(text[1])
        return suit*13 + rank-2
