# -*- coding: utf-8 -*-

from telegram import InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.error import TimedOut
from StringUtils import StringUtils
from BridgeCard import BridgeCard
import time

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
    PERSISTENCE WRAPPER
    '''

    def send_message(self, chat_id, message, parse_mode=None, reply_markup=None):
        while True:
            try:
                self.bot.send_message(chat_id, message, parse_mode=parse_mode, reply_markup=reply_markup)
            except TimedOut:
                print("Timed out error in bot.send_message, retrying")
                time.sleep(0.5)
                continue
            break

    '''
    GENERAL
    '''

    def player_joined_game(self, player, game):
        # send broadcast update to all members of the room
        for chat_id in game.get_chat_ids():
            self.send_message(chat_id, self.str_utils.joined_game(player, game))

    def player_left_game(self, player, game):
        # send broadcast update to all members of the room
        for chat_id in game.get_chat_ids():
            self.send_message(chat_id, self.str_utils.left_game(player, game))

    def display_hand(self, player, chat_id=None):
        if chat_id is not None:
            self.send_message(chat_id, self.str_utils.cards_in_hand(player))
        elif player.chat_id is not None:
            self.send_message(player.chat_id, self.str_utils.cards_in_hand(player))

    def starting_game(self, game):
        for chat_id in game.get_chat_ids():
            self.send_message(chat_id, "Room is full! Starting game...")

    def ask_private_chat(self, game):
        for chat_id in game.get_chat_ids():
            self.send_message(chat_id, "I've dealt your cards already!\nPM me @sgbridgebot and type /hand to see it.")

    def display_game_players(self, chat_id, game):
        self.send_message(chat_id, "For game with players " + ", ".join([p.disp_name() for p in game.players]) + ":")


    '''
    BIDDING
    '''

    def request_bid(self, player):
        keyboard = [[InlineKeyboardButton('PASS')]]
        suits = [u'\U00002663', u'\U00002666', u'\U00002764', u'\U00002660', 'NT']
        for x in range(7):
            keyboard.append([])
            for y in range(5):
                keyboard[x+1].append(InlineKeyboardButton(str(x+1)+suits[y]))
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        self.send_message(player.chat_id, player.disp_name() + ', please select a bid:', reply_markup=reply_markup)
        return

    def player_passed(self, player, game):
        for chat_id in game.get_chat_ids():
            self.send_message(chat_id, player.disp_name() + ' passed.')

    def player_bid(self, bid, player, game):
        for chat_id in game.get_chat_ids():
            self.send_message(chat_id, player.disp_name() + ' bid ' + self.str_utils.bid_id_to_str(bid) + ' .')

    def invalid_bid(self, player):
        self.send_message(player.chat_id, 'Invalid bid!')
        self.request_bid(player)

    def bid_winner(self, player, bid, game):
        bid_str = self.str_utils.bid_id_to_str(bid)
        for chat_id in game.get_chat_ids():
            self.send_message(chat_id, player.disp_name() + ' wins with bid ' + bid_str + '. Choosing partner...')


    '''
    CHOOSING PARTNER
    '''

    def request_partner_choice(self, player):
        keyboard = []
        for x in range(13):
            keyboard.append([])
            for y in range(4):
                keyboard[x].append( InlineKeyboardButton(repr(BridgeCard((12-x)+y*13))) )
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, selective=True)
        self.send_message(player.chat_id, '@'+player.disp_name() + ', please select a partner card:', reply_markup=reply_markup)
        return

    def partner_chosen(self, player, card_id, game):
            card = BridgeCard(card_id)
            for chat_id in game.get_chat_ids():
                self.send_message(chat_id, player.disp_name() + ' calls ' + repr(card) + ' as the partner card.')


    '''
    GAME PLAY
    '''

    def request_card(self, player, game):
        gameinfo = 'Contract: ' + self.str_utils.bid_id_to_str(game.contract)
        gameinfo += ' | Declarer: ' + game.declarer.disp_name()
        gameinfo += ' | Partner: ' + repr(game.partner_card)
        keyboard = [[InlineKeyboardButton(gameinfo)]]
        counter = 0
        l = [player.get_all_suit(suit) for suit in range(4)]
        num_rows = max( 3, len(max(l, key=len)) )
        for i in range(num_rows):
            keyboard.append([])
            for s in range(4):
                if len(l[s]) > i:
                    keyboard[-1].append( InlineKeyboardButton(repr(l[s][i])) )
                else:
                    keyboard[-1].append( InlineKeyboardButton(' ') )
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, selective=True)
        if player.username is not None:
            disp_name = '@'+player.username
        else:
            disp_name = '['+player.first_name+'](mention:'+str(player.id)+')'
        self.send_message(player.chat_id, player.disp_name() + ', please choose a card to play.', parse_mode='Markdown', reply_markup=reply_markup)


    def card_played(self, player, card, game):
        message = player.disp_name() + ' played ' + repr(card) + '.\n\nCurrent trick: '
        message += ' '.join([repr(c) for c in game.trick])
        for chat_id in game.get_chat_ids():
            self.send_message(chat_id, message)

    def announce_trick(self, player, card, game):
        message = player.disp_name() + ' won the trick with ' + repr(card) + '.\n\nTricks won:\n'
        message += ',  '.join([p.disp_name()+': '+str(p.tricks_won) for p in game.players])
        for chat_id in game.get_chat_ids():
            self.send_message(chat_id, message)


    def game_winners(self, team, p1, p2, bid, req, game):
        bidder = game.bidder.disp_name()
        partner = game.partner.disp_name()
        message = '{} and {} gained {} of the {} required tricks to win.\n\n'.format(bidder, partner, bid, req)
        message += 'Congrats to {} and {}!\n\n'.format(p1.disp_name(), p2.disp_name())
        message += 'Game ended, all players have been kicked from the room.'
        for chat_id in game.get_chat_ids():
            self.send_message(chat_id, message)
