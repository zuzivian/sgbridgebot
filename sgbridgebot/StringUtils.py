# -*- coding: utf-8 -*-

import unicodedata


class StringUtils(object):

    '''
    '''

    def __init__(self):
        self.type = None
        self.suit_str = [u'\U00002663', u'\U00002666', u'\U00002764', u'\U00002660']
        self.suit_aliases = {
            'C': self.suit_str[0],
            'D': self.suit_str[1],
            'H': self.suit_str[2],
            'S': self.suit_str[3],
        }

    def player_name(self, player):
        return player.username if player.username else player.first_name

    def player_listing(self, game):
        return ", ".join([self.player_name(p) for p in game.players])

    def players_in_room(self, game):
        players_needed = 4 - game.num_players()
        readiness = (
            f'Ready to start!\n' if players_needed == 0
            else f'Waiting for {players_needed} more player(s).\n'
        )
        return '{}Number of players: {}/4\nPlayers in the room: {}'.format(
            readiness,
            game.num_players(),
            self.player_listing(game))

    def normalize_suit_token(self, token):
        normalized = unicodedata.normalize('NFKC', str(token).strip()).upper()
        if normalized in self.suit_aliases:
            return self.suit_aliases[normalized]
        if token in self.suit_str:
            return token
        return None

    def normalize_rank_token(self, token):
        normalized = unicodedata.normalize('NFKC', str(token).strip()).upper()
        if normalized in {'A', 'K', 'Q', 'J', '10'}:
            return normalized
        if len(normalized) == 1 and normalized.isdigit() and 2 <= int(normalized) <= 9:
            return normalized
        return None

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
        normalized = unicodedata.normalize('NFKC', str(text).strip())
        normalized_upper = normalized.upper()

        if normalized_upper == 'PASS':
            return -1

        if len(normalized) < 2:
            raise ValueError('Invalid bid format: expected level and suit token (e.g., 1♣ or 1NT).')

        level_token = normalized[0]
        if not level_token.isdigit() or not 1 <= int(level_token) <= 7:
            raise ValueError('Invalid bid level: expected a digit from 1 to 7.')

        suit_token = normalized[1:]
        if len(suit_token) == 1:
            normalized_suit = self.normalize_suit_token(suit_token)
            if normalized_suit is None:
                raise ValueError('Invalid bid suit: expected ♣, ♦, ♥, ♠, C, D, H, S, or NT.')
            suit = self.suit_str.index(normalized_suit)
        elif suit_token.upper() == 'NT':
            suit = 4
        else:
            raise ValueError('Invalid bid suit: expected ♣, ♦, ♥, ♠, C, D, H, S, or NT.')

        return suit + 5 * (int(level_token) - 1)

    def bid_id_to_str(self, id):
        bid = id//5 + 1
        s = (id % 5)
        suit = self.suit_str[s] if s != 4 else 'NT'
        return str(bid)+suit

    def card_str_to_id(self, text):
        normalized = unicodedata.normalize('NFKC', str(text).strip())
        if len(normalized) < 2:
            raise ValueError('Invalid card format: expected suit and rank token (e.g., ♣2 or ♠A).')

        suit_token = self.normalize_suit_token(normalized[0])
        if suit_token is None:
            raise ValueError('Invalid card suit: expected ♣, ♦, ♥, ♠, C, D, H, or S.')
        suit = self.suit_str.index(suit_token)

        rank_token = self.normalize_rank_token(normalized[1:])
        if rank_token is None:
            raise ValueError('Invalid card rank: expected 2-10, J, Q, K, or A.')
        rank_map = {'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        if rank_token in rank_map:
            rank = rank_map[rank_token]
        elif rank_token == '10':
            rank = 10
        elif len(rank_token) == 1 and rank_token.isdigit() and 2 <= int(rank_token) <= 9:
            rank = int(rank_token)
        else:
            raise ValueError('Invalid card rank: expected 2-10, J, Q, K, or A.')

        return suit * 13 + rank - 2
