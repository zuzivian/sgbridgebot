#!/usr/bin/env python3

from ChatBot import ChatBot
import logging


def main():
    # python-telegram-bot provides logging features for debugging purposes
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG)

    # provide TOKEN to initiate ChatBot
    bot = ChatBot('577609760:AAFkuR2w7lWWyOlERf9NMyq0GYlf8WaoAZI')
    bot.start(1)


if __name__ == "__main__":
    main()
