#!/usr/bin/env python3

from sgbridgebot.ChatBot import ChatBot
import logging
import os

'''
localtestbot.py

Top-level bot script that initiates amd ChatBot() object and begins
serving requests via long polling, for testing purposes.

ChatBot handles all aspects of operating the telegram bot, including
interfacing with the python-telegram-bot API.

ChatBot.start() runs a continual polling loop to check for updates from the
Telegram servers. ChatBot will respond appropriately to user actions.
'''


def main():
    # python-telegram-bot provides logging features for debugging purposes
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG)

    # provide TOKEN to initiate ChatBot
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '577609760:AAFkuR2w7lWWyOlERf9NMyq0GYlf8WaoAZI')
    bot = ChatBot(token)
    bot.start(1)


if __name__ == "__main__":
    main()
