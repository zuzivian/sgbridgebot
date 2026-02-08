#!/usr/bin/env python3

import logging
import os
import sys

from sgbridgebot.ChatBot import ChatBot

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

    if not os.environ.get('TELEGRAM_BOT_TOKEN'):
        logging.error('Missing required environment variable: TELEGRAM_BOT_TOKEN')
        sys.exit(1)

    # provide TOKEN to initiate ChatBot
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    bot = ChatBot(token)

    # Default to webhook for public web-service deployments.
    # For VM/always-on workers, set BOT_MODE=polling.
    default_mode = 'webhook'
    mode = os.environ.get('BOT_MODE', default_mode).strip().lower()

    if mode == 'webhook':
        if not (os.environ.get('WEBHOOK_BASE_URL') or os.environ.get('KOYEB_PUBLIC_DOMAIN')):
            logging.error('Missing WEBHOOK_BASE_URL or KOYEB_PUBLIC_DOMAIN for webhook mode')
            sys.exit(1)
        try:
            bot.start(0)
        except ValueError as exc:
            logging.error('Webhook startup failed: %s', exc)
            sys.exit(1)
    elif mode == 'polling':
        bot.start(1)
    else:
        raise ValueError(f"Invalid BOT_MODE '{mode}'. Expected 'webhook' or 'polling'.")



if __name__ == "__main__":
    main()
