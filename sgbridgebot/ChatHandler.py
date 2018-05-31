from StringUtils import StringUtils

class ChatHandler(object):

    '''
    '''

    def __init__(self, bot):
        self.str_utils = StringUtils()
        self.bot = bot

    def player_joined_game(self, player, game):
        # send broadcast update to all members of the room
        for chat_id in game.player_chat_ids:
            self.bot.send_message(chat_id, self.str_utils.joined_game(player, game))

    def player_left_game(self, player, game):
        # send broadcast update to all members of the room
        for chat_id in game.player_chat_ids:
            self.bot.send_message(chat_id, self.str_utils.left_game(player, game))
