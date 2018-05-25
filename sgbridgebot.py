from telegram.ext import Updater, CommandHandler
import logging

# GLOBAL VARS
player_list = []

# set logging level to DEBUG
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# /hello command handler
def hello(bot, update):
    update.message.reply_text(
        'Hello {}'.format(update.message.from_user.first_name))

# /join command handler.
def join(bot, update):
    if update.message.from_user.id in player_list:
        reply_text = '{} is already in the game.\n Number of players: {}/4'
    elif len(player_list) < 4:
        player_list.append(update.message.from_user.id)
        reply_text = '{} joined the game.\n Number of players: {}/4'
    else:
        reply_text = 'Game full, sorry {}.\n Number of players: {}/4'
    update.message.reply_text(
        reply_text.format(update.message.from_user.first_name, len(player_list)))

# /leave command handler
def leave(bot, update):
    if update.message.from_user.id in player_list:
        player_list.remove(update.message.from_user.id)
        reply_text = '{} left the game.\n Number of players: {}/4'
    else:
        reply_text = '{} is not in the game.\n Number of players: {}/4'
    update.message.reply_text(
        reply_text.format(update.message.from_user.first_name, len(player_list)))


# session API token
updater = Updater('608173029:AAFXYqVYU6pDZlRAEdNV7PzuOqkAKilDDCg')

#add command handlers to dispatcher
updater.dispatcher.add_handler(CommandHandler('hello', hello))
updater.dispatcher.add_handler(CommandHandler('join', join))
updater.dispatcher.add_handler(CommandHandler('leave', leave))



updater.start_polling()
updater.idle()
