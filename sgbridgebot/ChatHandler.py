# -*- coding: utf-8 -*-

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.error import BadRequest
from sgbridgebot.StringUtils import StringUtils
from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.retry_utils import retry_on_timeout

class ChatHandler(object):

    '''
    Handles requests to use the ChatBot, with help of StringUtils

    ATRRIBUTES
    str_utils (StringUtils)
    bot (ChatBot)

    ARGS
    player_joined_game(player, game)
    player_left_game(player, game)
    display_hand(player)
    '''

    def __init__(self, bot):
        self.str_utils = StringUtils()
        self.bot = bot

    '''
    PERSISTENCE WRAPPER FOR BOT
    '''
    # TODO: move wrapper to own object?

    async def send_message(self, chat_id, message, parse_mode=None, reply_markup=None):
        return await retry_on_timeout(
            "send_message",
            lambda: self.bot.send_message(chat_id, message, parse_mode=parse_mode, reply_markup=reply_markup),
            chat_id=chat_id,
            retry_log_message="Timed out error in bot.send_message, retrying",
        )

    async def edit_message_text(self, text, chat_id, message_id, parse_mode=None, reply_markup=None):
        try:
            return await retry_on_timeout(
                "edit_message_text",
                lambda: self.bot.edit_message_text(
                    text,
                    chat_id,
                    message_id=message_id,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                ),
                chat_id=chat_id,
                message_id=message_id,
                retry_log_message="Timed out error in bot.edit_message_text, retrying",
            )
        except BadRequest:
            return await self.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)

    '''
    GENERAL
    '''

    async def player_joined_game(self, player, game):
        # send broadcast update to all members of the room
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, self.str_utils.joined_game(player, game))

    async def player_left_game(self, player, game):
        # send broadcast update to all members of the room
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, self.str_utils.left_game(player, game))

    async def display_hand(self, player, chat_id=None):
        if chat_id is not None:
            await self.send_message(chat_id, self.str_utils.cards_in_hand(player))
        elif player.chat_id is not None:
            await self.send_message(player.chat_id, self.str_utils.cards_in_hand(player))

    async def starting_game(self, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, "Room is full! Starting game...")

    async def ask_private_chat(self, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, "I've dealt your cards already!\nPM me @sgbridgebot and type /hand to see it.")

    async def display_game_players(self, chat_id, game):
        await self.send_message(chat_id, "For game with players " + ", ".join([p.disp_name() for p in game.players]) + ":")


    '''
    BIDDING
    '''

    async def request_bid(self, player):
        keyboard = [['PASS']]
        suits = [u'\U00002663', u'\U00002666', u'\U00002764', u'\U00002660', 'NT']
        for x in range(7):
            keyboard.append([])
            for y in range(5):
                keyboard[x+1].append(str(x+1)+suits[y])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await self.send_message(player.chat_id, player.disp_name() + ', please select a bid:', reply_markup=reply_markup)
        return

    async def player_passed(self, player, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, player.disp_name() + ' passed.')

    async def player_bid(self, bid, player, game):
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, player.disp_name() + ' bid ' + self.str_utils.bid_id_to_str(bid))

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


    '''
    CHOOSING PARTNER
    '''

    async def request_partner_choice(self, player):
        keyboard = []
        for x in range(13):
            keyboard.append([])
            for y in range(4):
                keyboard[x].append(repr(BridgeCard((12-x)+y*13)))
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, selective=True)
        if player.username is not None:
            disp_name = '@'+player.username
        else:
            disp_name = '['+player.first_name+'](mention:'+str(player.id)+')'
        await self.send_message(player.chat_id, disp_name + ', please select a partner card:', parse_mode='Markdown', reply_markup=reply_markup)
        return

    async def partner_chosen(self, player, card_id, game):
            card = BridgeCard(card_id)
            for chat_id in game.get_chat_ids():
                await self.send_message(chat_id, player.disp_name() + ' calls ' + repr(card) + ' as the partner card.')


    '''
    GAME PLAY
    '''

    async def request_card(self, player, game):
        gameinfo = 'Contract: ' + self.str_utils.bid_id_to_str(game.contract)
        gameinfo += ' | Declarer: ' + game.declarer.disp_name()
        gameinfo += ' | Partner: ' + repr(game.partner_card)
        keyboard = [[gameinfo]]
        cards_by_suit = [player.get_all_suit(suit) for suit in range(4)]
        num_rows = max(3, len(max(cards_by_suit, key=len)))
        for i in range(num_rows):
            keyboard.append([])
            for s in range(4):
                if len(cards_by_suit[s]) > i:
                    keyboard[-1].append(repr(cards_by_suit[s][i]))
                else:
                    keyboard[-1].append(' ')
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, selective=True)
        if player.username is not None:
            disp_name = '@'+player.username
        else:
            disp_name = '['+player.first_name+'](mention:'+str(player.id)+')'
        await self.send_message(player.chat_id, disp_name + ', please choose a card to play.', parse_mode='Markdown', reply_markup=reply_markup)


    async def card_played(self, player, card, game):
        message = 'Current trick:\n\n'
        for i in range(len(game.trick)):
            card = game.trick[i]
            player_num = (game.trick_start+i) % 4
            message += repr(card) + ' : played by ' + game.players[player_num].disp_name() + '\n'
        if game.trick_message == []:
            for chat_id in game.get_chat_ids():
                msg = await self.send_message(chat_id, message)
                game.trick_message.append(msg.message_id)
        else:
            for i in range(len(game.get_chat_ids())):
                chat_id = game.get_chat_ids()[i]
                await self.edit_message_text(message, chat_id, game.trick_message[i])


    async def announce_trick(self, player, card, game):
        message = player.disp_name() + ' won the trick with ' + repr(card) + '.\n\nTricks won:\n'
        message += ',  '.join([p.disp_name()+': '+str(p.tricks_won) for p in game.players])
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, message)


    async def game_winners(self, team, winners, bid, req, game):
        declarers = [game.declarer.disp_name()]
        if game.partner != game.declarer:
            declarers.append(game.partner.disp_name())
        declarers_text = " and ".join(declarers)
        winners_text = " and ".join([p.disp_name() for p in winners])
        message = '{} gained {} of the {} required tricks to win.\n\n'.format(declarers_text, bid, req)
        message += 'Congrats to {}!\n\n'.format(winners_text)
        message += 'Game ended, all players have been kicked from the room.'
        for chat_id in game.get_chat_ids():
            await self.send_message(chat_id, message)
