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

    def __init__(self, manager):
        self.manager = manager


    # /hello command util
    def hello(self, bot, update):
        update.message.reply_text(
            'Hello {}.'.format(update.message.from_user.first_name))


    # /join command util
    def join(self, bot, update):
        # attempt to add player to game
        game = self.manager.join_game(update.message.from_user, update.message.chat_id)

        if game == -1:
            update.message.reply_text('Could not join: all games are currently full.')

        elif game == -2:
            update.message.reply_text('You are already in the game.')

        elif isinstance(game, BridgeGame):
            update.message.reply_text('You joined the game.')
            # send broadcast to all other members of the room
            for chat_id in game.player_chat_ids:
                bot.send_message(chat_id,
                    '{} joined the game.\n\nNumber of players: {}/4\n'
                    'Players in the room: {}'.format(
                        game.player_name(update.message.from_user),
                        game.num_players,
                        game.player_listing()))


    # /leave command util
    def leave(self, bot, update):
        # attempt to remove player from game
        game = self.manager.leave_game(update.message.from_user, update.message.chat_id)

        if game == -1:
            update.message.reply_text('You are already not in the game.')

        elif isinstance(game, BridgeGame):
            update.message.reply_text('You left the game.')

            # send broadcast to all other members of the room
            for chat_id in game.player_chat_ids:
                bot.send_message(chat_id,
                    '{} left the game.\n\nNumber of players: {}/4\n'
                    'Players in the room: {}'.format(
                        game.player_name(update.message.from_user),
                        game.num_players,
                        game.player_listing()))
