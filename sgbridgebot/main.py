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
    bot = ChatBot('608173029:AAFXYqVYU6pDZlRAEdNV7PzuOqkAKilDDCg')
    bot.start(1)


if __name__ == "__main__":
    main()
