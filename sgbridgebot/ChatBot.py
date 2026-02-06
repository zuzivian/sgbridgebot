# -*- coding: utf-8 -*-

from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError)
from telegram.ext import Updater, CommandHandler, RegexHandler
from GameManager import GameManager
from CommandUtils import CommandUtils
from ChatHandler import ChatHandler
import os

class ChatBot(object):

    '''
    Object that contains all elements of the chatbot. Interfaces between the
    python-telegram-bot API and the GameManager object with the help of several
    utilities.

    ATTRIBUTES
    manager(GameManager)
    updater(telegram.Updater)
    cmd_utils(CommandUtils)

    ARGS
    start(int): idle 0/1
    init_command_handlers()

    '''


    def __init__(self, token):
        self.updater = Updater(token)
        self.token = token
        self.chat_handler = ChatHandler(self.updater.bot)
        self.manager = GameManager(self.chat_handler)
        self.cmd_utils = CommandUtils(self.manager, self.chat_handler)



    def error_callback(self, bot, update, error):
        try:
            raise error
        except TimedOut:
            print("Timed out error")

    def start(self, poll):
        self.init_command_handlers()
        self.init_regex_handlers()

        if poll == 1:
            self.updater.start_polling()
            self.updater.idle()
        else:
            token = self.token
            port = int(os.environ.get('PORT', '8443'))
            webhook_base_url = os.environ['WEBHOOK_BASE_URL'].rstrip('/')
            webhook_url = webhook_base_url + '/' + token

            self.updater.start_webhook(listen="0.0.0.0",
                                  port=port,
                                  url_path=token)
            self.updater.bot.set_webhook(webhook_url)
            self.updater.idle()

    def init_regex_handlers(self):
        self.updater.dispatcher.add_handler(RegexHandler('^(PASS|(1|2|3|4|5|6|7)('+"|".join([u'\U00002663',u'\U00002666',u'\U00002764',u'\U00002660','NT'])+'))$', self.cmd_utils.bidding))
        self.updater.dispatcher.add_handler(RegexHandler('^('+"|".join([u'\U00002663',u'\U00002666',u'\U00002764',u'\U00002660'])+')(2|3|4|5|6|7|8|9|10|J|Q|K|A)$', self.cmd_utils.card))


    def init_command_handlers(self):
        self.updater.dispatcher.add_handler(CommandHandler('forcestart', self.cmd_utils.forcestart))
        self.updater.dispatcher.add_handler(CommandHandler('join', self.cmd_utils.join))
        self.updater.dispatcher.add_handler(CommandHandler('leave', self.cmd_utils.leave))
        self.updater.dispatcher.add_handler(CommandHandler('hand', self.cmd_utils.hand))
        # self.updater.dispatcher.add_error_handler(self.error_callback)
