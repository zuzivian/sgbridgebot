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
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
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
