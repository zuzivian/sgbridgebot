from ChatBot import ChatBot
import logging

'''
sgbridgebot.py

Top-level bot script that initiates amd ChatBot() object and begins
serving requests.

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
    bot = ChatBot('608173029:AAFXYqVYU6pDZlRAEdNV7PzuOqkAKilDDCg')
    bot.start()


if __name__ == "__main__":
    main()
