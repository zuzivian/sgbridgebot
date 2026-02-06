#!/usr/bin/env python3

from ChatBot import ChatBot
import logging
import os
import sys

'''
sgbridgebot.py

Top-level bot script that initiates amd ChatBot() object and begins
serving requests via webhook.

WARNING: DO NOT USE THIS FOR TESTING. Instead, please use
'''

def main():
    # python-telegram-bot provides logging features for debugging purposes
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    required_env_vars = ['TELEGRAM_BOT_TOKEN', 'PORT', 'WEBHOOK_BASE_URL']
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]

    if missing_vars:
        logging.error('Missing required environment variables: %s', ', '.join(missing_vars))
        sys.exit(1)

    # provide TOKEN to initiate ChatBot
    bot = ChatBot(os.environ['TELEGRAM_BOT_TOKEN'])
    bot.start(0) # 0 for webhook


if __name__ == "__main__":
    main()
