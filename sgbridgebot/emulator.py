#!/usr/bin/env python3
'''
emulator.py

Plays sgBridgeBot end to end without Telegram.

FakeTelegram stands in for the Telegram Bot API server. It plugs into
python-telegram-bot as its HTTP layer, so the real Application, handlers,
filters and keyboards run unchanged. It keeps every message the bot sends,
and it rejects the requests Telegram would reject (bad HTML, oversized button
data, messaging a user who never started the bot, editing a message into
itself).

Emulator plays the human side: users type commands and text, and tap inline
buttons. Scenario functions drive whole games and check that they finish.

    python -m sgbridgebot.emulator                 # run every scenario
    python -m sgbridgebot.emulator --games 25      # plus 25 random full games
    python -m sgbridgebot.emulator --transcript    # print the chat log too
    python -m sgbridgebot.emulator --interactive   # play by hand in a REPL
'''

import argparse
import asyncio
import html
import itertools
import json
import logging
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telegram import Update
from telegram.request import BaseRequest

from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.ChatBot import ChatBot
from sgbridgebot.game_types import GameState, GameType

BOT_ID = 4242
BOT_USERNAME = 'sgbridgebot'
TOKEN = f'{BOT_ID}:EMULATOR-TOKEN'

ALLOWED_HTML_TAGS = {
    'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'a', 'code', 'pre',
    'span', 'tg-spoiler', 'blockquote', 'tg-emoji',
}
TAG_RE = re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9-]*)([^<>]*)>')
ENTITY_RE = re.compile(r'&(lt|gt|amp|quot|#\d+|#x[0-9a-fA-F]+);')


class ApiError(Exception):
    def __init__(self, code, description):
        super().__init__(description)
        self.code = code
        self.description = description


def check_html(text):
    '''
    Rejects HTML that Telegram's parser would reject.
    '''
    stack: list[str] = []
    for match in TAG_RE.finditer(text):
        closing, tag = match.group(1), match.group(2).lower()
        if tag not in ALLOWED_HTML_TAGS:
            raise ApiError(400, f"Bad Request: can't parse entities: unsupported tag <{tag}>")
        if closing:
            if not stack or stack.pop() != tag:
                raise ApiError(400, f"Bad Request: can't parse entities: unexpected </{tag}>")
        else:
            stack.append(tag)
    if stack:
        raise ApiError(400, f"Bad Request: can't parse entities: unclosed <{stack[-1]}>")
    bare = TAG_RE.sub('', text)
    if '<' in bare or '>' in bare:
        raise ApiError(400, "Bad Request: can't parse entities: unescaped < or >")
    if '&' in ENTITY_RE.sub('', bare):
        raise ApiError(400, "Bad Request: can't parse entities: unescaped &")


def plain_text(text, parse_mode):
    if parse_mode == 'HTML':
        return html.unescape(TAG_RE.sub('', text))
    return text


@dataclass
class Sent:
    chat_id: int
    message_id: int
    raw_text: str
    text: str
    reply_markup: dict | None = None

    @property
    def inline_buttons(self):
        if not self.reply_markup or 'inline_keyboard' not in self.reply_markup:
            return []
        return [b for row in self.reply_markup['inline_keyboard'] for b in row]

    @property
    def reply_buttons(self):
        if not self.reply_markup or 'keyboard' not in self.reply_markup:
            return []
        return [
            b['text'] if isinstance(b, dict) else b
            for row in self.reply_markup['keyboard'] for b in row
        ]

    def addresses(self, user):
        '''
        True if this message mentions the user, so a selective keyboard shows to them.
        '''
        if self.chat_id == user.id:
            return True
        if f'tg://user?id={user.id}' in self.raw_text:
            return True
        return bool(user.username) and f'@{user.username}' in self.text


@dataclass
class FakeUser:
    id: int
    first_name: str
    username: str | None = None

    def to_dict(self):
        data = {'id': self.id, 'is_bot': False, 'first_name': self.first_name}
        if self.username:
            data['username'] = self.username
        return data

    @property
    def name(self):
        return self.username or self.first_name


@dataclass
class TapResult:
    answered: bool
    text: str | None = None
    show_alert: bool = False


@dataclass
class Transcript:
    lines: list = field(default_factory=list)
    echo: bool = False

    def add(self, line):
        self.lines.append(line)
        if self.echo:
            print(line)


class FakeTelegram(BaseRequest):
    '''
    In-memory Telegram Bot API server for python-telegram-bot to talk to.
    '''

    def __init__(self, transcript):
        self.transcript = transcript
        self.chats = {}  # chat_id -> {'type': ..., 'title': ...}
        self.started_users = set()
        self.messages = {}  # (chat_id, message_id) -> Sent
        self.message_ids = itertools.count(1)
        self.callback_answers = {}
        self.api_errors = []
        self.calls = []

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def chat_name(self, chat_id):
        chat = self.chats.get(chat_id, {})
        if chat.get('type') == 'private':
            return f"DM {chat.get('title')}"
        return f"group {chat.get('title', chat_id)}"

    async def do_request(self, url, method, request_data=None, read_timeout=None,
                         write_timeout=None, connect_timeout=None, pool_timeout=None):
        api_method = url.rsplit('/', 1)[-1]
        params = request_data.parameters if request_data is not None else {}
        self.calls.append((api_method, params))
        try:
            handler = getattr(self, 'api_' + api_method, None)
            if handler is None:
                raise ApiError(404, f'Not Found: method {api_method} is not emulated')
            result = handler(params)
        except ApiError as exc:
            self.api_errors.append((api_method, exc.code, exc.description))
            body = {'ok': False, 'error_code': exc.code, 'description': exc.description}
            return exc.code, json.dumps(body).encode()
        return 200, json.dumps({'ok': True, 'result': result}).encode()

    # -- Bot API methods ---------------------------------------------------

    def api_getMe(self, params):
        return {
            'id': BOT_ID, 'is_bot': True, 'first_name': 'sgBridgeBot',
            'username': BOT_USERNAME, 'can_join_groups': True,
            'can_read_all_group_messages': True, 'supports_inline_queries': False,
        }

    def api_setMyCommands(self, params):
        return True

    def api_deleteWebhook(self, params):
        return True

    def _check_markup(self, markup):
        if not markup or 'inline_keyboard' not in markup:
            return
        buttons = [b for row in markup['inline_keyboard'] for b in row]
        if len(buttons) > 100:
            raise ApiError(400, 'Bad Request: too many inline keyboard buttons')
        for button in buttons:
            data = button.get('callback_data', '')
            if len(data.encode()) > 64:
                raise ApiError(400, 'Bad Request: BUTTON_DATA_INVALID')

    def _check_text(self, text, parse_mode):
        if not text or not str(text).strip():
            raise ApiError(400, 'Bad Request: message text is empty')
        if len(plain_text(text, parse_mode)) > 4096:
            raise ApiError(400, 'Bad Request: message is too long')
        if parse_mode == 'HTML':
            check_html(text)
        elif parse_mode is not None:
            raise ApiError(400, f'Bad Request: emulator does not check parse_mode {parse_mode}')

    def _message_json(self, sent):
        chat = self.chats[sent.chat_id]
        data = {
            'message_id': sent.message_id,
            'date': int(time.time()),
            'chat': {'id': sent.chat_id, 'type': chat['type'], 'title': chat.get('title')},
            'from': self.api_getMe({}),
            'text': sent.text,
        }
        if sent.inline_buttons:
            data['reply_markup'] = sent.reply_markup
        return data

    def api_sendMessage(self, params):
        chat_id = int(params['chat_id'])
        if chat_id not in self.chats:
            raise ApiError(400, 'Bad Request: chat not found')
        if self.chats[chat_id]['type'] == 'private' and chat_id not in self.started_users:
            raise ApiError(403, "Forbidden: bot can't initiate conversation with a user")
        text, parse_mode = params.get('text', ''), params.get('parse_mode')
        self._check_text(text, parse_mode)
        markup = params.get('reply_markup')
        self._check_markup(markup)
        sent = Sent(chat_id, next(self.message_ids), text, plain_text(text, parse_mode), markup)
        self.messages[(chat_id, sent.message_id)] = sent
        self.transcript.add(f'[{self.chat_name(chat_id)}] bot: {self._describe(sent)}')
        return self._message_json(sent)

    def _find_message(self, params):
        key = (int(params['chat_id']), int(params['message_id']))
        if key not in self.messages:
            raise ApiError(400, 'Bad Request: message to edit not found')
        return self.messages[key]

    def api_editMessageText(self, params):
        sent = self._find_message(params)
        text, parse_mode = params.get('text', ''), params.get('parse_mode')
        self._check_text(text, parse_mode)
        markup = params.get('reply_markup')
        self._check_markup(markup)
        if text == sent.raw_text and markup == sent.reply_markup:
            raise ApiError(400, 'Bad Request: message is not modified')
        sent.raw_text, sent.text, sent.reply_markup = text, plain_text(text, parse_mode), markup
        self.transcript.add(
            f'[{self.chat_name(sent.chat_id)}] bot edits #{sent.message_id}: {self._describe(sent)}'
        )
        return self._message_json(sent)

    def api_editMessageReplyMarkup(self, params):
        sent = self._find_message(params)
        markup = params.get('reply_markup')
        self._check_markup(markup)
        if markup == sent.reply_markup or (not markup and not sent.inline_buttons):
            raise ApiError(400, 'Bad Request: message is not modified')
        sent.reply_markup = markup
        return self._message_json(sent)

    def api_answerCallbackQuery(self, params):
        text = params.get('text')
        if text is not None and len(text) > 200:
            raise ApiError(400, 'Bad Request: MESSAGE_TOO_LONG')
        query_id = params['callback_query_id']
        if query_id in self.callback_answers:
            raise ApiError(400, 'Bad Request: query is too old or already answered')
        self.callback_answers[query_id] = TapResult(True, text, bool(params.get('show_alert')))
        return True

    @staticmethod
    def _describe(sent):
        text = sent.text.replace('\n', ' / ')
        if sent.inline_buttons:
            text += '  [' + ' '.join(b['text'] for b in sent.inline_buttons) + ']'
        elif sent.reply_buttons:
            text += '  {reply keyboard: ' + ' '.join(sent.reply_buttons) + '}'
        return text


class Emulator:
    '''
    The human side of the conversation, plus a handle on the bot under test.
    '''

    def __init__(self, turn_timeout=None, bot_pause=0.0, echo=False):
        self.transcript = Transcript(echo=echo)
        self.server = FakeTelegram(self.transcript)
        # A turn_timeout of 0 switches the idle timer off.
        self.bot = ChatBot(TOKEN, request=self.server, turn_timeout=turn_timeout or 0,
                           bot_pause=bot_pause)
        self.app = self.bot.application
        self.update_ids = itertools.count(1)
        self.callback_ids = itertools.count(1)
        self.user_message_ids = itertools.count(100000)
        self.users = {}
        self.pending = set()
        self.errors = []
        self.bot.application.add_error_handler(self._record_error)

    async def _record_error(self, update, context):
        self.errors.append(context.error)

    async def __aenter__(self):
        self.bot.register_handlers()
        await self.app.initialize()
        await self.bot.post_init(self.app)
        return self

    async def __aexit__(self, *exc):
        await self.settle()
        for game in self.bot.manager.waiting_games + self.bot.manager.active_games:
            game._cancel_idle_timer()
        await self.app.shutdown()

    # -- people and chats ---------------------------------------------------

    def add_user(self, user_id, first_name, username=None, start_dm=True):
        user = FakeUser(user_id, first_name, username)
        self.users[user_id] = user
        self.server.chats[user_id] = {'type': 'private', 'title': user.name}
        if start_dm:
            self.server.started_users.add(user_id)
        return user

    def add_group(self, chat_id, title):
        self.server.chats[chat_id] = {'type': 'group', 'title': title}
        return chat_id

    # -- sending updates ----------------------------------------------------

    def _chat_json(self, chat_id):
        chat = self.server.chats[chat_id]
        data = {'id': chat_id, 'type': chat['type']}
        if chat['type'] == 'private':
            data['first_name'] = chat['title']
        else:
            data['title'] = chat['title']
        return data

    async def say(self, user, chat_id, text, wait=True):
        '''
        The user types text (or a /command) into a chat.
        '''
        if self.server.chats[chat_id]['type'] == 'private':
            self.server.started_users.add(user.id)
        message = {
            'message_id': next(self.user_message_ids),
            'date': int(time.time()),
            'chat': self._chat_json(chat_id),
            'from': user.to_dict(),
            'text': text,
        }
        if text.startswith('/'):
            command = text.split()[0]
            message['entities'] = [{'type': 'bot_command', 'offset': 0, 'length': len(command)}]
        self.transcript.add(f'[{self.server.chat_name(chat_id)}] {user.name}: {text}')
        update = Update.de_json({'update_id': next(self.update_ids), 'message': message},
                                self.app.bot)
        await self._dispatch(update, wait)

    async def tap(self, user, sent, button_text, wait=True):
        '''
        The user taps the inline button with this label on a bot message.
        '''
        for button in sent.inline_buttons:
            if button['text'] == button_text:
                return await self.tap_data(user, sent, button['callback_data'], button_text, wait)
        raise LookupError(f'No button {button_text!r} on message #{sent.message_id}')

    async def tap_data(self, user, sent, data, label=None, wait=True):
        query_id = str(next(self.callback_ids))
        self.transcript.add(
            f'[{self.server.chat_name(sent.chat_id)}] {user.name} taps [{label or data}]'
        )
        update = Update.de_json({
            'update_id': next(self.update_ids),
            'callback_query': {
                'id': query_id,
                'from': user.to_dict(),
                'chat_instance': str(sent.chat_id),
                'data': data,
                'message': self.server._message_json(sent),
            },
        }, self.app.bot)
        task = await self._dispatch(update, wait)
        if not wait:
            return task
        answer = self.server.callback_answers.get(query_id, TapResult(False))
        if answer.text:
            self.transcript.add(f'    (popup to {user.name}: {answer.text})')
        return answer

    async def _dispatch(self, update, wait):
        task = asyncio.create_task(self.app.process_update(update))
        self.pending.add(task)
        task.add_done_callback(self.pending.discard)
        if wait:
            await task
        return task

    async def settle(self):
        while self.pending:
            await asyncio.gather(*list(self.pending), return_exceptions=True)

    # -- reading what the bot showed ---------------------------------------

    def visible_chats(self, user):
        chats = [user.id]
        for game in self.bot.manager.waiting_games + self.bot.manager.active_games:
            for p in game.players:
                if p.id == user.id and p.chat_id not in chats:
                    chats.append(p.chat_id)
        return chats

    def open_prompt(self, user):
        '''
        The newest message with live inline buttons that is meant for this user.
        '''
        chats = self.visible_chats(user)
        candidates = [
            s for s in self.server.messages.values()
            if s.chat_id in chats and s.inline_buttons and s.addresses(user)
        ]
        return max(candidates, key=lambda s: s.message_id) if candidates else None

    def reply_keyboard(self, user):
        '''
        The newest selective reply keyboard meant for this user (group fallback).
        '''
        chats = self.visible_chats(user)
        candidates = [
            s for s in self.server.messages.values()
            if s.chat_id in chats and s.reply_buttons and s.addresses(user)
        ]
        return max(candidates, key=lambda s: s.message_id) if candidates else None

    def messages_in(self, chat_id):
        return sorted(
            (s for s in self.server.messages.values() if s.chat_id == chat_id),
            key=lambda s: s.message_id,
        )

    def game_of(self, user):
        for game in self.bot.manager.waiting_games + self.bot.manager.active_games:
            if any(p.id == user.id for p in game.players):
                return game
        return None


class PlaytestFailure(AssertionError):
    pass


def expect(condition, message):
    if not condition:
        raise PlaytestFailure(message)


async def play_until_done(emu, humans, rng, chaos=False, max_steps=2000, idle=()):
    '''
    Humans answer whatever prompt the bot shows them until no game is left.
    Players in `idle` never act. Returns the number of actions taken.
    '''
    steps = 0
    stuck_rounds = 0
    while emu.bot.manager.active_games or emu.bot.manager.waiting_games:
        await emu.settle()
        acted = False
        for user in humans:
            if user.id in [u.id for u in idle] or emu.game_of(user) is None:
                continue
            prompt = emu.open_prompt(user)
            if prompt is not None:
                if chaos and rng.random() < 0.15:
                    await chaos_action(emu, user, humans, rng)
                buttons = list(prompt.inline_buttons)
                rng.shuffle(buttons)
                for button in buttons:
                    answer = await emu.tap_data(user, prompt, button['callback_data'],
                                                button['text'])
                    expect(answer.answered, f'Tap on {button["text"]} was never answered')
                    if not answer.show_alert:
                        break
                acted = True
                steps += 1
                continue
            keyboard = emu.reply_keyboard(user)
            game = emu.game_of(user)
            if keyboard is not None and game is not None and game.state == GameState.PLAY \
                    and game.curr_player().id == user.id:
                options = [b for b in keyboard.reply_buttons[1:] if b.strip()]
                await emu.say(user, keyboard.chat_id, rng.choice(options))
                acted = True
                steps += 1
        if not acted:
            stuck_rounds += 1
            if idle and stuck_rounds < 400:
                await asyncio.sleep(0.01)
                continue
            dump = describe_games(emu)
            raise PlaytestFailure(f'No player had anything to do, but games remain:\n{dump}')
        stuck_rounds = 0
        expect(steps < max_steps, f'Game did not finish within {max_steps} actions')
    return steps


async def chaos_action(emu, user, humans, rng):
    '''
    Things real people do: tap someone else's buttons, tap old buttons, chat.
    '''
    roll = rng.random()
    others = [u for u in humans if u.id != user.id]
    if roll < 0.4 and others:
        intruder = rng.choice(others)
        prompt = emu.open_prompt(user)
        if prompt is not None and prompt.chat_id != user.id:
            answer = await emu.tap_data(intruder, prompt, prompt.inline_buttons[0]['callback_data'])
            expect(answer.answered and 'not yours' in (answer.text or ''),
                   f'Intruder tap was not refused: {answer}')
    elif roll < 0.7:
        await emu.say(user, user.id, '/hand')
    else:
        game = emu.game_of(user)
        if game is not None and game.type == GameType.GROUP:
            chat_id = next(p.chat_id for p in game.players if p.id == user.id)
            bystander = emu.users.get(9999) or emu.add_user(9999, 'Bystander')
            before = len(emu.server.messages)
            await emu.say(bystander, chat_id, rng.choice(['A', 'pass', 'S', '10', 'h2']))
            expect(len(emu.server.messages) == before, 'Bot replied to a bystander in the group')


def describe_games(emu):
    lines = []
    for game in emu.bot.manager.waiting_games + emu.bot.manager.active_games:
        lines.append(
            f'game {game.short_id} state={game.state.name} turn={game.turn} '
            f'seq={game.action_seq} players='
            + ', '.join(f'{p.disp_name()}{"(bot)" if p.is_bot else ""}' for p in game.players)
        )
    lines.extend(emu.transcript.lines[-15:])
    return '\n'.join(lines)


def check_clean(emu, allowed_errors=()):
    expect(not emu.errors, f'Handler raised: {emu.errors!r}')
    unexpected = [
        e for e in emu.server.api_errors
        if not any(allowed in e[2] for allowed in allowed_errors)
        # Removing buttons that are already gone is harmless; the bot ignores it.
        and not (e[0] == 'editMessageReplyMarkup' and 'not modified' in e[2])
    ]
    expect(not unexpected, f'Bot made requests Telegram would reject: {unexpected}')
    expect(not emu.bot.manager.active_games, 'A game was left running')


def final_result_posted(emu, chat_id):
    return any('Congrats to' in s.text for s in emu.messages_in(chat_id))


# -- scenarios ---------------------------------------------------------------

async def scenario_matchmaking_four_humans(rng, echo=False):
    async with Emulator(echo=echo) as emu:
        humans = [emu.add_user(100 + i, f'Player{i}', f'p{i}') for i in range(4)]
        for user in humans:
            await emu.say(user, user.id, '/join')
        expect(len(emu.bot.manager.active_games) == 1, 'Four DM joins did not start a game')
        await play_until_done(emu, humans, rng)
        for user in humans:
            expect(final_result_posted(emu, user.id), f'{user.name} never saw the result')
        check_clean(emu)


async def scenario_group_four_humans(rng, echo=False):
    async with Emulator(echo=echo) as emu:
        group = emu.add_group(-1001, 'Table')
        humans = [emu.add_user(200 + i, f'Friend_{i}', None if i % 2 else f'f_{i}')
                  for i in range(4)]
        for user in humans:
            await emu.say(user, group, '/join')
        await play_until_done(emu, humans, rng, chaos=True)
        expect(final_result_posted(emu, group), 'Group never saw the result')
        for user in humans:
            dm_cards = [s for s in emu.messages_in(user.id) if 'your turn to play' in s.text]
            expect(dm_cards, f'{user.name} was never sent their cards privately')
        group_hands = [
            s for s in emu.messages_in(group) if 'following cards in your hand' in s.text
        ]
        expect(not group_hands, 'A hand was posted in the group chat')
        check_clean(emu)


async def scenario_group_with_bots_and_no_dm(rng, echo=False):
    '''
    Two friends fill the table with bots; one never opened a chat with the bot.
    '''
    async with Emulator(echo=echo) as emu:
        group = emu.add_group(-1002, 'Two and two bots')
        alice = emu.add_user(301, 'Alice', 'alice')
        bob = emu.add_user(302, 'Bob', None, start_dm=False)
        await emu.say(alice, group, '/join')
        await emu.say(bob, group, '/join')
        await emu.say(alice, group, '/forcestart')
        expect(len(emu.bot.manager.active_games) == 1, '/forcestart did not start the game')
        await play_until_done(emu, [alice, bob], rng)
        expect(final_result_posted(emu, group), 'Group never saw the result')
        check_clean(emu, allowed_errors=["can't initiate conversation"])


async def scenario_idle_player_is_replaced(rng, echo=False):
    async with Emulator(turn_timeout=0.05, echo=echo) as emu:
        group = emu.add_group(-1003, 'One sleeper')
        humans = [emu.add_user(400 + i, f'P{i}', f'p4{i}') for i in range(4)]
        sleeper = humans[0]
        for user in humans:
            await emu.say(user, group, '/join')
        await play_until_done(emu, humans, rng, idle=[sleeper])
        texts = [s.text for s in emu.messages_in(group)]
        expect(any('ran out of time' in t for t in texts), 'No timeout notice was posted')
        expect(any('bot takes over' in t for t in texts), 'The sleeper was never replaced')
        expect(final_result_posted(emu, group), 'Game did not finish after the timeout')
        check_clean(emu)


async def scenario_everyone_idle_ends_game(rng, echo=False):
    async with Emulator(turn_timeout=0.02, echo=echo) as emu:
        humans = [emu.add_user(450 + i, f'Z{i}', f'z{i}') for i in range(4)]
        for user in humans:
            await emu.say(user, user.id, '/join')
        deadline = time.monotonic() + 30
        while emu.bot.manager.active_games and time.monotonic() < deadline:
            await asyncio.sleep(0.02)
        expect(not emu.bot.manager.active_games, 'An all-idle table never ended')
        check_clean(emu)


async def scenario_leave_on_own_turn(rng, echo=False):
    async with Emulator(echo=echo) as emu:
        group = emu.add_group(-1004, 'Quitter')
        humans = [emu.add_user(500 + i, f'Q{i}', f'q{i}') for i in range(4)]
        for user in humans:
            await emu.say(user, group, '/join')
        game = emu.bot.manager.active_games[0]
        seat = game.turn
        quitter = next(u for u in humans if u.id == game.curr_player().id)
        seq_before = game.action_seq
        await emu.say(quitter, group, '/leave')
        expect(game.players[seat].is_bot, 'Seat was not handed to a bot')
        expect(game.action_seq > seq_before, 'The bot that took over never moved')
        stayers = [u for u in humans if u is not quitter]
        await play_until_done(emu, stayers, rng)
        expect(final_result_posted(emu, group), 'Game did not finish after a player left')
        check_clean(emu)


async def scenario_all_trump_hand_can_lead(rng, echo=False):
    async with Emulator(echo=echo) as emu:
        humans = [emu.add_user(600 + i, f'T{i}', f't{i}') for i in range(4)]
        for user in humans:
            await emu.say(user, user.id, '/join')
        game = emu.bot.manager.active_games[0]
        # Rig the table: seat 0 holds all thirteen spades, spades are trump,
        # and seat 0 is on lead before trump is broken.
        spades = [c for p in game.players for c in p.hand if c.suit == 3]
        others = [c for p in game.players for c in p.hand if c.suit != 3]
        game.players[0].hand = sorted(spades, key=lambda c: c.id)
        for i in range(1, 4):
            game.players[i].hand = sorted(others[(i - 1) * 13:i * 13], key=lambda c: c.id)
        game.state = GameState.PLAY
        game.contract = 3
        game.declarer = game.players[3]
        game.partner = game.players[1]
        game.partner_card = BridgeCard(game.players[1].hand[0].id)
        game.turn = 0
        game.trick_start = 0
        game.trump_broken = 0
        async with game.lock:
            await game.get_next_card()
        prompt = emu.open_prompt(humans[0])
        expect(prompt is not None and prompt.inline_buttons,
               'All-trump hand was offered no card to lead')
        answer = await emu.tap_data(humans[0], prompt, prompt.inline_buttons[0]['callback_data'])
        expect(not answer.show_alert, f'Leading trump was refused: {answer.text}')
        expect(game.trump_broken == 1 and len(game.trick) == 1, 'The trump lead was not played')
        await play_until_done(emu, humans, rng)
        check_clean(emu)


async def scenario_bots_do_not_block_other_tables(rng, echo=False):
    '''
    While one table's bots are pausing between cards, another table still responds.
    '''
    async with Emulator(bot_pause=0.5, echo=echo) as emu:
        expect(emu.app.concurrent_updates > 1, 'Updates are processed one at a time')
        slow_group = emu.add_group(-1005, 'Slow bots')
        loner = emu.add_user(701, 'Loner', 'loner')
        await emu.say(loner, slow_group, '/join')
        await emu.say(loner, slow_group, '/forcestart')
        fast = [emu.add_user(710 + i, f'F{i}', f'fast{i}') for i in range(4)]
        for user in fast:
            await emu.say(user, user.id, '/join')
        # The loner bids; three bots then answer, 0.5s apart, inside that tap.
        prompt = emu.open_prompt(loner)
        slow = await emu.tap(loner, prompt, 'PASS', wait=False)
        await asyncio.sleep(0.05)
        started = time.monotonic()
        fast_game = next(g for g in emu.bot.manager.active_games if g.type == GameType.MATCHMAKING)
        current = next(u for u in fast if u.id == fast_game.curr_player().id)
        prompt = emu.open_prompt(current)
        answer = await emu.tap_data(current, prompt, prompt.inline_buttons[0]['callback_data'])
        waited = time.monotonic() - started
        expect(answer.answered, 'Fast table got no answer')
        expect(not slow.done(), 'Slow table finished too early to prove anything')
        expect(waited < 0.4, f'Fast table waited {waited:.2f}s behind the other table')
        # Proven; let the rest of the game run at full speed.
        for game in emu.bot.manager.active_games:
            game.bot_pause = 0
        await slow
        await play_until_done(emu, fast + [loner], rng)
        check_clean(emu)


async def scenario_restart_notice(rng, echo=False):
    async with Emulator(echo=echo) as emu:
        group = emu.add_group(-1006, 'Restarted')
        humans = [emu.add_user(800 + i, f'R{i}', f'r{i}') for i in range(2)]
        for user in humans:
            await emu.say(user, group, '/join')
        await emu.bot.post_stop(emu.app)
        expect(any('restarting' in s.text for s in emu.messages_in(group)),
               'No restart notice was sent')
        emu.bot.manager.waiting_games.clear()
        check_clean(emu)


async def scenario_random_games(rng, echo=False, games=10):
    for index in range(games):
        async with Emulator(echo=echo) as emu:
            group_mode = rng.random() < 0.6
            chat = emu.add_group(-2000 - index, f'Random {index}') if group_mode else None
            human_count = rng.randint(1, 4)
            humans = [
                emu.add_user(1000 * (index + 1) + i, f'H{index}_{i}',
                             rng.choice([None, f'h{index}_{i}']),
                             start_dm=rng.random() < 0.8)
                for i in range(human_count)
            ]
            for user in humans:
                await emu.say(user, chat if group_mode else user.id, '/join')
            if human_count < 4:
                where = chat if group_mode else humans[0].id
                await emu.say(humans[0], where, '/forcestart')
                if not group_mode:
                    # Strangers who joined other DM lobbies wait there; fill those too.
                    for user in humans[1:]:
                        game = emu.game_of(user)
                        if game is not None and game.state == GameState.SETUP:
                            await emu.say(user, user.id, '/forcestart')
            await play_until_done(emu, humans, rng, chaos=group_mode)
            check_clean(emu, allowed_errors=["can't initiate conversation"])


SCENARIOS = [
    scenario_matchmaking_four_humans,
    scenario_group_four_humans,
    scenario_group_with_bots_and_no_dm,
    scenario_idle_player_is_replaced,
    scenario_everyone_idle_ends_game,
    scenario_leave_on_own_turn,
    scenario_all_trump_hand_can_lead,
    scenario_bots_do_not_block_other_tables,
    scenario_restart_notice,
]


async def run_scenarios(seed=1, games=0, echo=False):
    results = []
    for scenario in SCENARIOS + ([scenario_random_games] if games else []):
        rng = random.Random(seed)
        random.seed(seed)
        name = scenario.__name__.removeprefix('scenario_')
        started = time.monotonic()
        try:
            if scenario is scenario_random_games:
                await scenario_random_games(rng, echo=echo, games=games)
            else:
                await scenario(rng, echo=echo)
            results.append((name, True, f'{time.monotonic() - started:.1f}s'))
        except Exception as exc:  # report every scenario, then fail
            results.append((name, False, f'{type(exc).__name__}: {exc}'))
    return results


# -- interactive play --------------------------------------------------------

HELP = '''Commands:
  say <user> <dm|group> <text>   type a message, e.g. say alice group /join
  tap <user> <button>            tap a button on that user's newest prompt
  show <user>                    show that user's newest prompt
  auto                           let everyone play to the end of the game
  log [n]                        show the last n transcript lines
  quit
Users: alice, bob, carol, dave. Group: Table.'''


async def interactive():
    async with Emulator(turn_timeout=None, bot_pause=0.3, echo=True) as emu:
        group = emu.add_group(-1, 'Table')
        users = {name: emu.add_user(i + 1, name.title(), name)
                 for i, name in enumerate(['alice', 'bob', 'carol', 'dave'])}
        print(HELP)
        loop = asyncio.get_running_loop()
        while True:
            line = (await loop.run_in_executor(None, input, '> ')).strip()
            if not line:
                continue
            cmd, *rest = line.split(maxsplit=1)
            arg = rest[0] if rest else ''
            try:
                if cmd == 'quit':
                    return
                elif cmd == 'say':
                    name, where, text = arg.split(maxsplit=2)
                    user = users[name]
                    await emu.say(user, user.id if where == 'dm' else group, text)
                elif cmd == 'tap':
                    name, label = arg.split(maxsplit=1)
                    prompt = emu.open_prompt(users[name])
                    if prompt is None:
                        print(f'{name} has no buttons to tap.')
                    else:
                        await emu.tap(users[name], prompt, label)
                elif cmd == 'show':
                    prompt = emu.open_prompt(users[arg])
                    print(FakeTelegram._describe(prompt) if prompt else 'No open prompt.')
                elif cmd == 'auto':
                    await play_until_done(emu, list(users.values()), random.Random())
                elif cmd == 'log':
                    for entry in emu.transcript.lines[-int(arg or 20):]:
                        print(entry)
                else:
                    print(HELP)
                await emu.settle()
            except (KeyError, ValueError, LookupError) as exc:
                print(f'Could not do that: {exc}')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Play sgBridgeBot without Telegram.')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--games', type=int, default=0,
                        help='also play this many random full games')
    parser.add_argument('--transcript', action='store_true', help='print the chat log')
    parser.add_argument('--interactive', action='store_true', help='play by hand')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    if args.interactive:
        asyncio.run(interactive())
        return 0

    results = asyncio.run(run_scenarios(args.seed, args.games, args.transcript))
    width = max(len(name) for name, _, _ in results)
    for name, ok, detail in results:
        print(f'{"PASS" if ok else "FAIL"}  {name.ljust(width)}  {detail}')
    failed = [name for name, ok, _ in results if not ok]
    print(f'\n{len(results) - len(failed)}/{len(results)} scenarios passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
