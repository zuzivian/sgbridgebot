# -*- coding: utf-8 -*-

from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError)
from telegram.ext import Updater, CommandHandler, RegexHandler
from sgbridgebot.GameManager import GameManager
from sgbridgebot.CommandUtils import CommandUtils
from sgbridgebot.ChatHandler import ChatHandler
from urllib.parse import urlparse
import os
import logging



logger = logging.getLogger(__name__)


def _mask_token(token):
    """Return a redacted token representation safe for logs."""
    if not token:
        return '<empty>'
    if len(token) <= 8:
        return '<redacted:{} chars>'.format(len(token))
    return '{}...{}'.format(token[:4], token[-4:])



def _resolve_webhook_base_url():
    """Return public HTTPS base URL for webhook registration."""
    # Explicit override first
    base_url = os.environ.get('WEBHOOK_BASE_URL', '').strip()
    logger.info('Resolving webhook base URL (WEBHOOK_BASE_URL set=%s, KOYEB_PUBLIC_DOMAIN set=%s)',
                bool(base_url), bool(os.environ.get('KOYEB_PUBLIC_DOMAIN', '').strip()))
    if not base_url:
        # Koyeb exposes this automatically for public services.
        domain = os.environ.get('KOYEB_PUBLIC_DOMAIN', '').strip()
        if domain:
            base_url = domain
            logger.info('Using KOYEB_PUBLIC_DOMAIN to build webhook base URL: %s', domain)

    if not base_url:
        raise ValueError('Webhook mode requires WEBHOOK_BASE_URL or KOYEB_PUBLIC_DOMAIN.')

    # Support both full URLs and bare domains from platform env vars.
    if '://' not in base_url:
        base_url = 'https://' + base_url

    parsed = urlparse(base_url)
    host = (parsed.hostname or '').lower()
    logger.info('Parsed webhook base URL -> scheme=%s host=%s path=%s',
                parsed.scheme, host or '<empty>', parsed.path or '<empty>')

    if parsed.scheme != 'https':
        raise ValueError('WEBHOOK_BASE_URL must be an https URL.')
    if not host:
        raise ValueError('WEBHOOK_BASE_URL must include a valid public hostname.')
    if host in {'0.0.0.0', '127.0.0.1', 'localhost'}:
        raise ValueError('WEBHOOK_BASE_URL must be a public hostname, not {}.'.format(host))

    normalized = base_url.rstrip('/')
    logger.info('Resolved webhook base URL: %s', normalized)
    return normalized


def _resolve_webhook_listen_port():
    """Return a webhook listen port that is valid for this runtime user."""
    raw_port = os.environ.get('PORT', '').strip()
    if not raw_port:
        logger.info('PORT is unset. Falling back to default webhook listen port 8000.')
        return 8000

    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError('PORT must be a valid integer, got {!r}'.format(raw_port)) from exc

    if not (1 <= port <= 65535):
        raise ValueError('PORT must be between 1 and 65535, got {}.'.format(port))

    # Non-root processes cannot bind privileged ports (<1024) on many hosts.
    if port < 1024 and hasattr(os, 'geteuid') and os.geteuid() != 0:
        fallback_port = int(os.environ.get('UNPRIVILEGED_PORT_FALLBACK', '8000'))
        logger.warning(
            'Configured PORT=%s is privileged but process is non-root (uid=%s). '
            'Falling back to %s. Override with UNPRIVILEGED_PORT_FALLBACK if needed.',
            port, os.geteuid(), fallback_port,
        )
        return fallback_port

    return port

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
            port = _resolve_webhook_listen_port()
            webhook_base_url = _resolve_webhook_base_url()
            webhook_url = webhook_base_url + '/' + token

            logger.info('Starting webhook listener on 0.0.0.0:%s', port)
            logger.info('Registering Telegram webhook URL: %s/<token:%s>',
                        webhook_base_url, _mask_token(token))
            logger.info('Webhook URL diagnostics: length=%s token_length=%s',
                        len(webhook_url), len(token))

            self.updater.start_webhook(listen="0.0.0.0",
                                  port=port,
                                  url_path=token,
                                  webhook_url=webhook_url)
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
