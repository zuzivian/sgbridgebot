from telegram.ext import Updater, CommandHandler
from BridgeGame import BridgeGame
from GameManager import GameManager
import logging


# GLOBAL VARS
manager = GameManager()

# set logging level to DEBUG
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

###
# Command Utils
###

# /hello command util
def hello(bot, update):
    update.message.reply_text(
        'Hello {}.'.format(update.message.from_user.first_name))

# /join command util
def join(bot, update):
    # attempt to add player to game
    game = manager.join_game(update.message.from_user, update.message.chat_id)

    if game == -1:
        update.message.reply_text('Could not join: all games are currently full.')

    elif game == -2:
        update.message.reply_text('You are already in the game.')

    elif isinstance(game, BridgeGame):
        update.message.reply_text('You joined the game.')
        # send broadcast to all other members of the room
        for chat_id in game.player_chat_ids:
            bot.send_message(chat_id,
                '{} joined the game.\n\nNumber of players: {}/4\nPlayers in the room: {}'.format(
                    game.player_name(update.message.from_user), game.num_players, game.player_listing()))

# /leave command util
def leave(bot, update):
    # attempt to remove player from game
    game = manager.leave_game(update.message.from_user, update.message.chat_id)

    if game == -1:
        update.message.reply_text('You are already not in the game.')

    elif isinstance(game, BridgeGame):
        update.message.reply_text('You left the game.')

        # send broadcast to all other members of the room
        for chat_id in game.player_chat_ids:
            bot.send_message(chat_id,
                '{} left the game.\n\nNumber of players: {}/4\nPlayers in the room: {}'.format(
                    game.player_name(update.message.from_user), game.num_players, game.player_listing()))


# instantiate Updater with API token
updater = Updater('608173029:AAFXYqVYU6pDZlRAEdNV7PzuOqkAKilDDCg')

# add command handlers to dispatcher
updater.dispatcher.add_handler(CommandHandler('hello', hello))
updater.dispatcher.add_handler(CommandHandler('join', join))
updater.dispatcher.add_handler(CommandHandler('leave', leave))

# begin polling Telegram for updates
updater.start_polling()

# set idle to run in background
# updater.idle()
