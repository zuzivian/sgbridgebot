from telegram.ext import Updater, CommandHandler
from BridgeGame import BridgeGame
from GameManager import GameManager
import logging


class CommandUtils(object):

    '''
    Contains methods for handling the various telegram commands

    ATTRIBUTES
    manager: GameManager object

    ARGS
    hello(telegram.Bot, telegram.Update)
    join(telegram.Bot, telegram.Update)
    leave(telegram.Bot, telegram.Update)
    '''

    def __init__(self, manager, chat_handler):
        self.manager = manager
        self.chat = chat_handler


    # /hello command util
    def hello(self, bot, update):
        update.message.reply_text(
            'Hello {}.'.format(update.message.from_user.first_name))


    # /join command util
    def join(self, bot, update):
        # attempt to add player to game
        user = update.message.from_user
        game = self.manager.join_game(user, update.message.chat_id)

        if game == -1:
            update.message.reply_text('Could not join: all games are currently full.')
            return

        elif game == -2:
            update.message.reply_text('You are already in the game.')
            return

        elif not isinstance(game, BridgeGame):
            raise TypeError('GameManager.join_game() did not return a valid BridgeGame object')

        update.message.reply_text('You joined the game.')
        # send broadcast update to all members of the room
        self.chat.player_joined_game(user, game)



    # /leave command util
    def leave(self, bot, update):
        # attempt to remove player from game
        user = update.message.from_user
        game = self.manager.leave_game(user, update.message.chat_id)

        if game == -1:
            update.message.reply_text('You are already not in the game.')
            return

        elif not isinstance(game, BridgeGame):
            raise TypeError('GameManager.join_game() did not return a valid BridgeGame object')

        update.message.reply_text('You left the game.')
        # send broadcast update to all members of the room
        self.chat.player_left_game(player, game)
