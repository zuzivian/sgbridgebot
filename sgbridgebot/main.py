#!/usr/bin/env python3

from ChatBot import ChatBot
import logging
import os

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

    # provide TOKEN to initiate ChatBot
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '608173029:AAFXYqVYU6pDZlRAEdNV7PzuOqkAKilDDCg')
    bot = ChatBot(token)

    # Default to webhook for public web-service deployments.
    # For VM/always-on workers, set BOT_MODE=polling.
    default_mode = 'webhook'
    mode = os.environ.get('BOT_MODE', default_mode).strip().lower()

    if mode == 'webhook':
        bot.start(0)
    elif mode == 'polling':
        bot.start(1)
    else:
        raise ValueError("Invalid BOT_MODE '{}'. Expected 'webhook' or 'polling'.".format(mode))



if __name__ == "__main__":
    main()
