import html
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.error import BadRequest, Forbidden

from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.BridgeGame import MAX_IDLE_STRIKES, WASH_MAX_POINTS
from sgbridgebot.game_types import GameType
from sgbridgebot.retry_utils import retry_on_timeout
from sgbridgebot.StringUtils import StringUtils

logger = logging.getLogger(__name__)

HTML = 'HTML'
# How many recent calls the bid prompt shows.
AUCTION_HISTORY_SHOWN = 8
RANKS_HIGH_TO_LOW = ['A', 'K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3', '2']


def esc(text):
    return html.escape(str(text), quote=False)


def callback_data(action, game, *args):
    '''
    Builds button data as action:game:seq[:args]. Telegram allows 64 bytes.
    '''
    return ':'.join([action, game.short_id, str(game.action_seq), *[str(a) for a in args]])


class ChatHandler:

    def __init__(self, bot):
        self.str_utils = StringUtils()
        self.bot = bot

    async def send_message(self, chat_id, message, parse_mode=None, reply_markup=None):
        return await retry_on_timeout(
            'send_message',
            lambda: self.bot.send_message(
                chat_id,
                message,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            ),
            chat_id=chat_id,
            retry_log_message='Timed out error in bot.send_message, retrying',
        )

    async def edit_message_text(
        self, text, chat_id, message_id, parse_mode=None, reply_markup=None
    ):
        try:
            return await retry_on_timeout(
                'edit_message_text',
                lambda: self.bot.edit_message_text(
                    text,
                    chat_id,
                    message_id=message_id,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                ),
                chat_id=chat_id,
                message_id=message_id,
                retry_log_message='Timed out error in bot.edit_message_text, retrying',
            )
        except BadRequest:
            return await self.send_message(
                chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup
            )

    async def remove_keyboard(self, chat_id, message_id):
        try:
            await retry_on_timeout(
                'edit_message_reply_markup',
                lambda: self.bot.edit_message_reply_markup(
                    chat_id=chat_id, message_id=message_id, reply_markup=None
                ),
                chat_id=chat_id,
                message_id=message_id,
            )
        except BadRequest as exc:
            # Already removed, or the message is gone. Nothing left to tidy.
            logger.debug('Could not remove keyboard: %s', exc)

    def _bot_username(self):
        try:
            return self.bot.username
        except (AttributeError, RuntimeError):
            return 'sgbridgebot'

    def mention(self, player):
        '''
        HTML mention of a player. Mentions make selective keyboards target them.
        '''
        if player.is_bot or player.id <= 0:
            return esc(player.disp_name())
        if player.username:
            return '@' + esc(player.username)
        return f'<a href="tg://user?id={player.id}">{esc(player.first_name)}</a>'

    async def _send_prompt(self, game, chat_id, text, reply_markup):
        await self.clear_prompt(game)
        msg = await self.send_message(chat_id, text, parse_mode=HTML, reply_markup=reply_markup)
        message_id = getattr(msg, 'message_id', None)
        if message_id is not None:
            game.last_prompt = (chat_id, message_id)
        return msg

    async def clear_prompt(self, game):
        '''
        Removes the buttons from the game's open prompt, if any.
        '''
        if getattr(game, 'last_prompt', None) is None:
            return
        chat_id, message_id = game.last_prompt
        game.last_prompt = None
        await self.remove_keyboard(chat_id, message_id)

    async def player_joined_game(self, player, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, self.str_utils.joined_game(player, game))

    async def player_left_game(self, player, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, self.str_utils.left_game(player, game))

    async def display_hand(self, player, chat_id=None):
        if chat_id is not None:
            await self.send_message(chat_id, self.str_utils.cards_in_hand(player))
        elif player.chat_id is not None:
            await self.send_message(player.chat_id, self.str_utils.cards_in_hand(player))

    async def display_hand_privately(self, player):
        '''
        Sends a group-game player their hand in a private chat, if they started one.
        '''
        if player.dm_blocked:
            return
        try:
            await self.send_message(player.id, self.str_utils.cards_in_hand(player))
        except (Forbidden, BadRequest) as exc:
            logger.info('Cannot reach player %s privately (%s)', player.id, exc)
            player.dm_blocked = True

    async def starting_game(self, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, 'Room is full! Starting game...')

    async def ask_private_chat(self, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(
                chat_id,
                (
                    "I've dealt your cards already!\n"
                    f'Open a private chat with @{self._bot_username()} and press Start. '
                    "I'll send your cards there when it's your turn, "
                    'and /hand there shows them any time.\n'
                    'Hands are private to prevent accidental table leaks.'
                ),
            )

    async def display_game_players(self, chat_id, game):
        players = ', '.join([p.disp_name() for p in game.players])
        await self.send_message(chat_id, 'For game with players ' + players + ':')

    '''
    BIDDING
    '''

    def auction_text(self, game, limit=None):
        '''
        The auction so far, e.g. "alice: 1♠ · bob: pass".
        '''
        calls = game.auction_log if limit is None else game.auction_log[-limit:]
        text = ' · '.join(
            f'{name}: {"pass" if bid == -1 else self.str_utils.bid_id_to_str(bid)}'
            for name, bid in calls
        )
        if limit is not None and len(game.auction_log) > limit:
            text = '… ' + text
        return text

    def bid_markup(self, game, player=None):
        first_row = [InlineKeyboardButton('PASS', callback_data=callback_data('b', game, -1))]
        if player is not None and game.can_call_wash(player):
            first_row.append(
                InlineKeyboardButton('🔄 Wash', callback_data=callback_data('w', game))
            )
        rows = [first_row]
        for level in range(7):
            row = []
            for suit in range(5):
                bid = level * 5 + suit
                if bid > game.contract:
                    row.append(InlineKeyboardButton(
                        self.str_utils.bid_id_to_str(bid),
                        callback_data=callback_data('b', game, bid),
                    ))
            if row:
                rows.append(row)
        return InlineKeyboardMarkup(rows)

    async def request_bid(self, player, game):
        contract = (
            self.str_utils.bid_id_to_str(game.contract) if game.contract >= 0 else 'none yet'
        )
        text = f'{self.mention(player)}, your bid.\n🎯 Highest bid: {esc(contract)}\n'
        if game.auction_log:
            text += f'📜 Auction: {esc(self.auction_text(game, AUCTION_HISTORY_SHOWN))}\n'
        if game.can_call_wash(player):
            points = player.hand_score(player.hand)
            text += (
                f'🔄 Your hand is worth {points} point(s), so you may call a wash '
                'to have the cards redealt.\n'
            )
        text += 'Tap a bid, or type one (1NT, 1C, PASS).'
        await self._send_prompt(game, player.chat_id, text, self.bid_markup(game, player))

    async def wash_called(self, player, points, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(
                chat_id,
                f'🔄 {player.disp_name()} called a wash with {points} point(s) '
                f'(allowed at {WASH_MAX_POINTS} or fewer). Redealing...',
            )

    async def player_passed(self, player, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, player.disp_name() + ' passed.')

    async def player_bid(self, bid, player, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(
                chat_id, player.disp_name() + ' bid ' + self.str_utils.bid_id_to_str(bid)
            )

    async def bid_winner(self, player, bid, game):
        bid_str = self.str_utils.bid_id_to_str(bid)
        message = (
            player.disp_name() + ' wins with bid ' + bid_str
            + f' and needs {game.tricks_required()} tricks with their partner.\n'
            + '📜 Auction: ' + self.auction_text(game) + '\n\nChoosing partner...'
        )
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, message, reply_markup=ReplyKeyboardRemove())

    '''
    PARTNER CALL
    '''

    def partner_suit_markup(self, game):
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(symbol, callback_data=callback_data('ps', game, suit))
            for suit, symbol in enumerate(self.str_utils.suit_str)
        ]])

    def partner_rank_markup(self, game, suit):
        buttons = [
            InlineKeyboardButton(
                self.str_utils.suit_str[suit] + rank,
                callback_data=callback_data(
                    'pc', game, self.str_utils.card_str_to_id(self.str_utils.suit_str[suit] + rank)
                ),
            )
            for rank in RANKS_HIGH_TO_LOW
        ]
        rows = [buttons[0:5], buttons[5:9], buttons[9:13]]
        back = InlineKeyboardButton('« Back to suits', callback_data=callback_data('pb', game))
        rows.append([back])
        return InlineKeyboardMarkup(rows)

    def partner_suit_prompt_text(self, player, game):
        bid_str = self.str_utils.bid_id_to_str(game.contract)
        return (
            f'{self.mention(player)}, you won the auction with {esc(bid_str)}.\n'
            'Call your partner card: whoever holds it is your partner.\n'
            'Choose a suit first (or type ♣/♦/♥/♠ or C/D/H/S).'
        )

    def partner_rank_prompt_text(self, player, suit):
        symbol = self.str_utils.suit_str[suit]
        return f'{self.mention(player)}, now choose a rank for {symbol}.'

    async def request_partner_choice(self, player, game):
        await self._send_prompt(
            game,
            player.chat_id,
            self.partner_suit_prompt_text(player, game),
            self.partner_suit_markup(game),
        )

    async def request_partner_rank(self, player, game, suit):
        await self._send_prompt(
            game,
            player.chat_id,
            self.partner_rank_prompt_text(player, suit),
            self.partner_rank_markup(game, suit),
        )

    async def partner_chosen(self, player, card_id, game):
        card = BridgeCard(card_id)
        for chat_id in game.get_chat_ids():
            await self.send_message(
                chat_id,
                player.disp_name() + ' calls ' + repr(card) + ' as the partner card.',
            )

    async def partner_revealed(self, player, game):
        if player is game.declarer:
            message = (
                f'🤝 {player.disp_name()} called their own card {game.partner_card!r}: '
                'they are playing alone, one against three!'
            )
        else:
            message = (
                f'🤝 Partner revealed! {player.disp_name()} holds {game.partner_card!r} '
                f'and plays with {game.declarer.disp_name()}.'
            )
        message += '\n' + self.tricks_tally(game)
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, message)

    '''
    CARD PLAY
    '''

    def tricks_tally(self, game):
        '''
        Trick count against each side's target. Who is on which side is only
        shown once the partner card has been played.
        '''
        required = game.tricks_required()
        to_defeat = 14 - required
        if game.partner_revealed:
            declarers = ' + '.join(
                p.disp_name() for p in game.players if game.is_declarer_side(p)
            )
            defenders = ' + '.join(
                p.disp_name() for p in game.players if not game.is_declarer_side(p)
            )
            return (
                f'📊 {declarers}: {game.declarer_side_tricks()}/{required} tricks · '
                f'{defenders}: {game.defender_side_tricks()}/{to_defeat} to defeat'
            )
        per_player = ', '.join(f'{p.disp_name()}: {p.tricks_won}' for p in game.players)
        return (
            f'📊 Tricks: {per_player}\n'
            f'{game.declarer.disp_name()} and partner need {required}; '
            f'the others need {to_defeat} to defeat the contract.'
        )

    def _table_status(self, game):
        lines = [
            '🎯 Contract: ' + esc(self.str_utils.bid_id_to_str(game.contract))
            + ' by ' + esc(game.declarer.disp_name()),
            '🤝 Partner card: ' + esc(repr(game.partner_card))
            + (' (revealed)' if game.partner_revealed else ''),
            esc(self.tricks_tally(game)),
        ]
        if game.trick:
            played = ', '.join(
                f'{c!r} {esc(game.players[(game.trick_start + i) % 4].disp_name())}'
                for i, c in enumerate(game.trick)
            )
            lines.append('🃏 Trick so far: ' + played)
        else:
            lines.append('🃏 You lead this trick.')
        return '\n'.join(lines)

    def card_markup(self, game, player):
        buttons_by_suit: dict[int, list[InlineKeyboardButton]] = {}
        for card in game.legal_card_objects(player):
            buttons_by_suit.setdefault(card.suit, []).append(
                InlineKeyboardButton(repr(card), callback_data=callback_data('c', game, card.id))
            )
        rows = []
        for suit in sorted(buttons_by_suit):
            buttons = buttons_by_suit[suit]
            for start in range(0, len(buttons), 7):
                rows.append(buttons[start:start + 7])
        return InlineKeyboardMarkup(rows)

    def card_prompt_text(self, player, game):
        return (
            f'{self.mention(player)}, your turn to play.\n'
            + self._table_status(game)
            + '\n\n'
            + esc(self.str_utils.cards_in_hand(player)).rstrip()
            + '\n\nTap a card (only legal cards are shown).'
        )

    async def request_card(self, player, game):
        if game.type == GameType.GROUP and not getattr(player, 'dm_blocked', False):
            # Group chats can see inline buttons, so the hand goes to a private chat.
            try:
                await self._send_prompt(
                    game, player.id, self.card_prompt_text(player, game),
                    self.card_markup(game, player),
                )
                return
            except (Forbidden, BadRequest) as exc:
                logger.info('Cannot reach player %s privately (%s); using group keyboard',
                            player.id, exc)
                player.dm_blocked = True
        if game.type == GameType.GROUP:
            await self._request_card_in_group(player, game)
            return
        await self._send_prompt(
            game, player.chat_id, self.card_prompt_text(player, game),
            self.card_markup(game, player),
        )

    async def _request_card_in_group(self, player, game):
        '''
        Fallback for players who never opened a private chat with the bot: a
        selective reply keyboard that only the mentioned player can see.
        '''
        gameinfo = 'Contract: ' + self.str_utils.bid_id_to_str(game.contract)
        gameinfo += ' | Declarer: ' + game.declarer.disp_name()
        gameinfo += ' | Partner: ' + repr(game.partner_card)
        keyboard = [[gameinfo]]
        cards_by_suit = [player.get_all_suit(suit) for suit in range(4)]
        num_rows = max(3, len(max(cards_by_suit, key=len)))
        for i in range(num_rows):
            keyboard.append([])
            for suit in range(4):
                if len(cards_by_suit[suit]) > i:
                    keyboard[-1].append(repr(cards_by_suit[suit][i]))
                else:
                    keyboard[-1].append(' ')
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, selective=True)
        status_message = (
            self.mention(player) + ', you are up now.\n'
            + self._table_status(game)
            + '\nPlease choose a card to play. Start a private chat with '
            + f'@{self._bot_username()} to see your hand there instead.'
        )
        await self.clear_prompt(game)
        await self.send_message(
            player.chat_id, status_message, parse_mode=HTML, reply_markup=reply_markup,
        )

    async def card_played(self, player, card, game):
        message = f'🃏 Trick {game.tricks_played + 1}\n\n'
        for i in range(len(game.trick)):
            played_card = game.trick[i]
            player_num = (game.trick_start + i) % 4
            message += (
                repr(played_card)
                + ' : played by '
                + game.players[player_num].disp_name()
                + '\n'
            )
        if len(game.trick) < 4:
            waiting_for = game.players[(game.trick_start + len(game.trick)) % 4]
            message += '\n⏳ Waiting for ' + waiting_for.disp_name()
        for chat_id in game.get_chat_ids():
            message_id = game.trick_message.get(chat_id)
            if message_id is None:
                msg = await self.send_message(chat_id, message)
                game.trick_message[chat_id] = msg.message_id
            else:
                await self.edit_message_text(message, chat_id, message_id)

    async def announce_trick(self, player, card, game):
        message = (
            '🏆 ' + player.disp_name() + ' won the trick with ' + repr(card) + '.\n\n'
            + self.tricks_tally(game)
        )
        if game.tricks_played < 12:
            message += '\n\n▶️ ' + player.disp_name() + ' leads next.'
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, message)

    '''
    GAME LIFECYCLE
    '''

    async def player_timed_out(self, player, game, handed_over):
        if handed_over:
            message = (
                f'⏰ {player.disp_name()} missed {MAX_IDLE_STRIKES} turns in a row, '
                'so a bot takes over their seat.'
            )
        else:
            message = f'⏰ {player.disp_name()} ran out of time, so a move was made for them.'
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, message)

    async def notify_restart(self, chat_ids):
        for chat_id in chat_ids:
            try:
                await self.send_message(
                    chat_id,
                    '⚠️ sgBridgeBot is restarting, so this game has ended. '
                    'Type /join to start a new one.',
                )
            except Exception:
                logger.exception('Could not send restart notice to chat %s', chat_id)

    def match_score_text(self, game):
        if not game.match_scores:
            return ''
        ranked = sorted(game.match_scores.items(), key=lambda item: -item[1])
        scores = ' · '.join(f'{game.match_names[uid]} {won}' for uid, won in ranked)
        plural = 's' if game.hands_played != 1 else ''
        return f'📈 Hands won at this table ({game.hands_played} hand{plural}): {scores}'

    def deal_again_markup(self, game):
        return InlineKeyboardMarkup([[
            InlineKeyboardButton('🔁 Deal again', callback_data=callback_data('r', game))
        ]])

    async def game_winners(self, team, winners, bid, req, game):
        declarers = [game.declarer.disp_name()]
        if game.partner is not game.declarer:
            declarers.append(game.partner.disp_name())
        declarers_text = ' and '.join(declarers)
        winners_text = ' and '.join([p.disp_name() for p in winners])
        contract = self.str_utils.bid_id_to_str(game.contract)
        outcome = 'made' if team == 0 else 'went down in'
        message = (
            f'🏁 {declarers_text} {outcome} {contract}: {bid} of the {req} required tricks.\n'
            f'🤝 Partner card: {game.partner_card!r}\n'
            f'📜 Auction: {self.auction_text(game)}\n\n'
            f'Congrats to {winners_text}!\n'
        )
        score_text = self.match_score_text(game)
        if score_text:
            message += '\n' + score_text + '\n'
        message += (
            '\nTap 🔁 Deal again to play another hand at this table, '
            'or /join for a new one.'
        )
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, message, reply_markup=self.deal_again_markup(game))
