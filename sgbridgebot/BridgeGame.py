from telegram.ext import Updater, CommandHandler
from telegram import User, Chat
import uuid


class BridgeGame(object):
    """
    Creates an instance of a BridgeGame
    which includes all information about the game

    ATTRIBUTES
    players (listof Telegram.User)
    state (int)

    ARGS
    add_player(Telegram.User):
    remove_player(Telegram.User):
    """


    # Initial game state is an empty game in the PREGAME state
    def __init__(self, num_bots=0):
        self.id = uuid.uuid1()
        self.state = 0
        self.players = []
        self.player_chat_ids = []
        self.num_bots = num_bots
        self.num_players = self.num_bots + len(self.players)

    # adds a player to the game if it is not full
    def add_player(self, player, chat_id):
        if not isinstance(player, User) or not isinstance(chat_id, int):
            raise TypeError
        elif self.num_players == 4 or self.state != 0:
            return -1
        elif player in self.players:
            return -2
        else:
            self.players.append(player)
            self.player_chat_ids.append(chat_id)
            self.num_players += 1
            if self.num_players == 4:
                self.start_game()
            return self

    # removes a player from the game
    def remove_player(self, player, chat_id):
        if not isinstance(player, User) or not isinstance(chat_id, int):
            raise TypeError
        elif player not in self.players:
            return -1
        else:
            self.players.remove(player)
            self.player_chat_ids.remove(chat_id)
            self.num_players -= 1
            return self

    def start_game(self):
        #starts the game
        self.state = 1
        return

    # player utility. should move to Player object in future
    def player_name(self, player):
        return player.username if player.username else player.first_name

    def player_listing(self):
        return ", ".join([self.player_name(p) for p in self.players])
