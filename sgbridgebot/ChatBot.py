import logging
import os
from urllib.parse import urlparse

from telegram.error import TimedOut
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from sgbridgebot.ChatHandler import ChatHandler
from sgbridgebot.CommandUtils import CommandUtils
from sgbridgebot.GameManager import GameManager

logger = logging.getLogger(__name__)


def _mask_token(token):
    """Return a redacted token representation safe for logs."""
    if not token:
        return '<empty>'
    if len(token) <= 8:
        return f'<redacted:{len(token)} chars>'
    return f'{token[:4]}...{token[-4:]}'



def _resolve_webhook_base_url():
    """Return public HTTPS base URL for webhook registration."""
    base_url = os.environ.get('WEBHOOK_BASE_URL', '').strip()
    logger.info('Resolving webhook base URL (WEBHOOK_BASE_URL set=%s, KOYEB_PUBLIC_DOMAIN set=%s)',
                bool(base_url), bool(os.environ.get('KOYEB_PUBLIC_DOMAIN', '').strip()))
    if not base_url:
        domain = os.environ.get('KOYEB_PUBLIC_DOMAIN', '').strip()
        if domain:
            base_url = domain
            logger.info('Using KOYEB_PUBLIC_DOMAIN to build webhook base URL: %s', domain)

    if not base_url:
        raise ValueError('Webhook mode requires WEBHOOK_BASE_URL or KOYEB_PUBLIC_DOMAIN.')

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
        raise ValueError(f'WEBHOOK_BASE_URL must be a public hostname, not {host}.')

    normalized = base_url.rstrip('/')
    logger.info('Resolved webhook base URL: %s', normalized)
    return normalized


def _resolve_webhook_listen_port():
    """Return webhook listen port from PORT with strict validation."""
    raw_port = os.environ.get('PORT', '').strip()
    if not raw_port:
        logger.info('PORT is unset. Falling back to default webhook listen port 8000.')
        return 8000

    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(f'PORT must be a valid integer, got {raw_port!r}') from exc

    if not (1 <= port <= 65535):
        raise ValueError(f'PORT must be between 1 and 65535, got {port}.')

    if port < 1024 and hasattr(os, 'geteuid') and os.geteuid() != 0:
        raise ValueError(
            f'PORT={port} is privileged but this process runs as non-root (uid={os.geteuid()}). '
            'Use a non-privileged port (>=1024). On managed platforms like Koyeb/Render, '
            'do not hardcode PORT (especially 80); let the platform inject it.'
        )

    return port


class ChatBot:

    def __init__(self, token):
        self.application = ApplicationBuilder().token(token).build()
        self.token = token
        self.chat_handler = ChatHandler(self.application.bot)
        self.manager = GameManager(self.chat_handler)
        self.cmd_utils = CommandUtils(self.manager, self.chat_handler)

    async def error_callback(self, update, context):
        if isinstance(context.error, TimedOut):
            logger.warning('Timed out error: %s', context.error)
        else:
            logger.exception('Unhandled Telegram error', exc_info=context.error)

    def start(self, poll):
        self.init_command_handlers()
        self.init_regex_handlers()
        self.application.add_error_handler(self.error_callback)

        if poll == 1:
            self.application.run_polling()
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

            try:
                self.application.run_webhook(
                    listen='0.0.0.0',
                    port=port,
                    url_path=token,
                    webhook_url=webhook_url,
                )
            except RuntimeError as exc:
                # python-telegram-bot requires optional webhook extras (e.g. tornado)
                # to run in webhook mode.
                raise ValueError(
                    'Webhook startup failed. Ensure webhook dependencies are installed '
                    '(pip install "python-telegram-bot[webhooks]>=21,<22"). '
                    f'Original error: {exc}'
                ) from exc

    def init_regex_handlers(self):
        suits = ['\U00002663', '\U00002666', '\U00002764', '\U00002660']
        bids = r'^(PASS|(1|2|3|4|5|6|7)(' + '|'.join([*suits, 'NT']) + r'))$'
        cards = r'^(' + '|'.join(suits) + r')(2|3|4|5|6|7|8|9|10|J|Q|K|A)$'
        self.application.add_handler(MessageHandler(filters.Regex(bids), self.cmd_utils.bidding))
        self.application.add_handler(MessageHandler(filters.Regex(cards), self.cmd_utils.card))

    def init_command_handlers(self):
        self.application.add_handler(CommandHandler('forcestart', self.cmd_utils.forcestart))
        self.application.add_handler(CommandHandler('join', self.cmd_utils.join))
        self.application.add_handler(CommandHandler('leave', self.cmd_utils.leave))
        self.application.add_handler(CommandHandler('hand', self.cmd_utils.hand))
