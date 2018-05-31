

class StringUtils(object):

    '''
    '''

    def __init__(self):
        self.type = None

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
        room_players = selfplayers_in_room(game)
        return leave_remark + '\n\n' + room_players
