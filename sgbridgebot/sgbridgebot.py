# from telegram.ext import Updater, CommandHandler
# from BridgeGame import BridgeGame
# from GameManager import GameManager
from ChatBot import ChatBot
import logging

'''
    sgbridgebot.py

    Top-level bot script that initiates and starts a ChatBot() object.

    ChatBot() handles all aspects of operating the telegram bot, including
    interfacing with the python-telegram-bot API.

    ChatBot().start runs a continual polling loop to check for updates from the
    Telegram servers. ChatBot() will respond appropriately to user actions.
'''


def main():

    # python-telegram-bot provides logging features for debugging purposes
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG)

    # provide TOKEN to initiate ChatBot
    bot = ChatBot('608173029:AAFXYqVYU6pDZlRAEdNV7PzuOqkAKilDDCg')

    # provide 1 for idle on a production server
    bot.start(0)


if __name__ == "__main__":
    main()
