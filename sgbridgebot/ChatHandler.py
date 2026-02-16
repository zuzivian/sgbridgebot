import logging

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.error import BadRequest
from telegram.helpers import escape_markdown

from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.retry_utils import retry_on_timeout
from sgbridgebot.StringUtils import StringUtils

logger = logging.getLogger(__name__)


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

    async def starting_game(self, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, 'Room is full! Starting game...')

    async def ask_private_chat(self, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(
                chat_id,
                (
                    "I've dealt your cards already!\n"
                    'Open a private chat with @sgbridgebot and type /hand '
                    'to see your cards.\n'
                    'Hands are private to prevent accidental table leaks.'
                ),
            )

    async def display_game_players(self, chat_id, game):
        players = ', '.join([p.disp_name() for p in game.players])
        await self.send_message(chat_id, 'For game with players ' + players + ':')

    def _safe_display_name_for_markdown(self, player):
        if player.username is not None:
            safe_username = escape_markdown(player.username, version=1)
            return '@' + safe_username

        safe_first_name = escape_markdown(player.first_name, version=1)
        return '[' + safe_first_name + '](mention:' + str(player.id) + ')'

    async def request_bid(self, player):
        keyboard = [['PASS']]
        suits = ['\U00002663', '\U00002666', '\U00002764', '\U00002660', 'NT']
        for x in range(7):
            keyboard.append([])
            for y in range(5):
                keyboard[x + 1].append(str(x + 1) + suits[y])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await self.send_message(
            player.chat_id,
            player.disp_name() + ', choose your bid.\nExamples: 1NT, 1♣, 1C, PASS',
            reply_markup=reply_markup,
        )

    async def player_passed(self, player, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, player.disp_name() + ' passed.')

    async def player_bid(self, bid, player, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(
                chat_id, player.disp_name() + ' bid ' + self.str_utils.bid_id_to_str(bid)
            )

    async def invalid_bid(self, player):
        await self.send_message(player.chat_id, 'Invalid bid!')
        await self.request_bid(player)

    async def bid_winner(self, player, bid, game):
        bid_str = self.str_utils.bid_id_to_str(bid)
        for chat_id in game.get_chat_ids():
            await self.send_message(
                chat_id,
                player.disp_name() + ' wins with bid ' + bid_str + '. Choosing partner...',
                reply_markup=ReplyKeyboardRemove(),
            )

    async def request_partner_choice(self, player):
        keyboard = [[suit for suit in self.str_utils.suit_str], ['C', 'D', 'H', 'S']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, selective=True)
        disp_name = self._safe_display_name_for_markdown(player)
        await self.send_message(
            player.chat_id,
            disp_name
            + ', please select a partner card: choose suit first (♣/♦/♥/♠ or C/D/H/S).',
            parse_mode='Markdown',
            reply_markup=reply_markup,
        )

    async def request_partner_rank(self, player, suit_symbol):
        keyboard = [['A', 'K', 'Q', 'J', '10'], ['9', '8', '7', '6', '5', '4', '3', '2']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, selective=True)
        await self.send_message(
            player.chat_id,
            f'Great. Now choose a rank for {suit_symbol} (A, K, Q, J, 10-2).',
            reply_markup=reply_markup,
        )

    async def partner_chosen(self, player, card_id, game):
        card = BridgeCard(card_id)
        for chat_id in game.get_chat_ids():
            await self.send_message(
                chat_id,
                player.disp_name() + ' calls ' + repr(card) + ' as the partner card.',
            )

    async def request_card(self, player, game):
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
        disp_name = self._safe_display_name_for_markdown(player)
        status_message = (
            disp_name
            + ', you are up now.\n🎯 Contract: '
            + self.str_utils.bid_id_to_str(game.contract)
            + '\n👤 Declarer: '
            + game.declarer.disp_name()
            + '\n🤝 Partner card: '
            + repr(game.partner_card)
            + '\nplease choose a card to play.'
        )
        await self.send_message(
            player.chat_id,
            status_message,
            parse_mode='Markdown',
            reply_markup=reply_markup,
        )

    async def card_played(self, player, card, game):
        message = '🃏 Current trick\n\n'
        for i in range(len(game.trick)):
            played_card = game.trick[i]
            player_num = (game.trick_start + i) % 4
            message += (
                repr(played_card)
                + ' : played by '
                + game.players[player_num].disp_name()
                + '\n'
            )
        if game.trick_message == []:
            for chat_id in game.get_chat_ids():
                msg = await self.send_message(chat_id, message)
                game.trick_message.append(msg.message_id)
        else:
            for i in range(len(game.get_chat_ids())):
                chat_id = game.get_chat_ids()[i]
                await self.edit_message_text(message, chat_id, game.trick_message[i])

    async def announce_trick(self, player, card, game):
        message = (
            '🏆 ' + player.disp_name() + ' won the trick with ' + repr(card) + '.\n\nTricks won:\n'
        )
        message += ',  '.join([p.disp_name() + ': ' + str(p.tricks_won) for p in game.players])
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, message)

    async def game_winners(self, team, winners, bid, req, game):
        declarers = [game.declarer.disp_name()]
        if game.partner != game.declarer:
            declarers.append(game.partner.disp_name())
        declarers_text = ' and '.join(declarers)
        winners_text = ' and '.join([p.disp_name() for p in winners])
        message = f'{declarers_text} gained {bid} of the {req} required tricks to win.\n\n'
        message += f'Congrats to {winners_text}!\n\n'
        message += (
            'Game ended, all players have been kicked from the room.\n'
            'Type /join to start a rematch.'
        )
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, message)
