# -*- coding: utf-8 -*-

from telegram import InlineKeyboardButton, ReplyKeyboardMarkup
from StringUtils import StringUtils
from BridgeCard import BridgeCard

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

    def player_joined_game(self, player, game):
        # send broadcast update to all members of the room
        for chat_id in game.get_chat_ids():
            self.bot.send_message(chat_id, self.str_utils.joined_game(player, game))

    def player_left_game(self, player, game):
        # send broadcast update to all members of the room
        for chat_id in game.get_chat_ids():
            self.bot.send_message(chat_id, self.str_utils.left_game(player, game))

    def display_hand(self, player):
        if player.chat_id is not None:
            self.bot.send_message(player.chat_id, self.str_utils.cards_in_hand(player))

    def starting_game(self, game):
        for chat_id in game.get_chat_ids():
            self.bot.send_message(chat_id, "Room is full! Starting game...")

    def request_bid(self, player):
        keyboard = [[InlineKeyboardButton('PASS')]]
        suits = [u'\U00002663', u'\U00002666', u'\U00002764', u'\U00002660', 'NT']
        for x in range(7):
            keyboard.append([])
            for y in range(5):
                keyboard[x+1].append(InlineKeyboardButton(str(x+1)+suits[y]))
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        self.bot.send_message(player.chat_id, 'Please select a bid:', reply_markup=reply_markup)
        return

    def request_partner_choice(self, player):
        keyboard = []
        for x in range(13):
            keyboard.append([])
            for y in range(4):
                keyboard[x].append( InlineKeyboardButton(repr(BridgeCard((12-x)+y*13))) )
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        self.bot.send_message(player.chat_id, 'Please select a partner card:', reply_markup=reply_markup)
        return

    def player_passed(self, player, game):
        for chat_id in game.get_chat_ids():
            self.bot.send_message(chat_id, player.disp_name() + ' passed.')

    def player_bid(self, bid, player, game):
        for chat_id in game.get_chat_ids():
            self.bot.send_message(chat_id, player.disp_name() + ' bid ' + self.str_utils.bid_id_to_str(bid) + ' .')

    def invalid_bid(self, player):
        self.bot.send_message(player.chat_id, 'Invalid bid!')
        self.request_bid(player)

    def bid_winner(self, player, bid, game):
        bid_str = self.str_utils.bid_id_to_str(bid)
        for chat_id in game.get_chat_ids():
            self.bot.send_message(chat_id, player.disp_name() + ' wins with bid ' + bid_str + '. Choosing partner...')

    def partner_chosen(self, player, card_id, game):
        card = BridgeCard(card_id)
        for chat_id in game.get_chat_ids():
            self.bot.send_message(chat_id, player.disp_name() + ' calls ' + repr(card) + ' as the partner card.')
            if chat_id == game.partner.chat_id:
                self.bot.send_message(chat_id, 'You playing as the partner!')
