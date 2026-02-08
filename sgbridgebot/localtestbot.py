#!/usr/bin/env python3

from pathlib import Path
import sys

# Ensure package imports still work when this file is executed directly via
# `python sgbridgebot/localtestbot.py` where sys.path[0] is this package dir.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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

    if not os.environ.get('TELEGRAM_BOT_TOKEN'):
        logging.error('Missing required environment variable: TELEGRAM_BOT_TOKEN')
        sys.exit(1)

    # provide TOKEN to initiate ChatBot
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    bot = ChatBot(token)
    bot.start(1)


if __name__ == "__main__":
    main()
