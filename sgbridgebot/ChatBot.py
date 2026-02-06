# -*- coding: utf-8 -*-

from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError)
from telegram.ext import Updater, CommandHandler, RegexHandler
from sgbridgebot.GameManager import GameManager
from sgbridgebot.CommandUtils import CommandUtils
from sgbridgebot.ChatHandler import ChatHandler
from urllib.parse import urlparse
import os



def _resolve_webhook_base_url():
    """Return public HTTPS base URL for webhook registration."""
    # Explicit override first
    base_url = os.environ.get('WEBHOOK_BASE_URL', '').strip()
    if not base_url:
        # Koyeb exposes this automatically for public services.
        domain = os.environ.get('KOYEB_PUBLIC_DOMAIN', '').strip()
        if domain:
            base_url = 'https://' + domain

    if not base_url:
        raise ValueError('Webhook mode requires WEBHOOK_BASE_URL or KOYEB_PUBLIC_DOMAIN.')

    parsed = urlparse(base_url)
    host = (parsed.hostname or '').lower()

    if parsed.scheme != 'https':
        raise ValueError('WEBHOOK_BASE_URL must be an https URL.')
    if host in {'0.0.0.0', '127.0.0.1', 'localhost'}:
        raise ValueError('WEBHOOK_BASE_URL must be a public hostname, not {}.'.format(host))

    return base_url.rstrip('/')

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
        # Keep legacy callback signatures (`bot, update`) expected by
        # CommandUtils and Regex/Command handlers across the codebase.
        self.updater = Updater(token, use_context=False)
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
            webhook_base_url = _resolve_webhook_base_url()
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
