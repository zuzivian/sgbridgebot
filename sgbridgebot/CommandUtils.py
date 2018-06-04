from telegram.ext import Updater, CommandHandler
from telegram.error import TimedOut
from BridgeGame import BridgeGame
from GameManager import GameManager
from BridgeCard import BridgeCard
import logging, time


class CommandUtils(object):

    '''
    Contains methods for handling the various telegram commands

    ATTRIBUTES
    manager: GameManager object

    ARGS
    forcestart(telegram.Bot, telegram.Update)
    hello(telegram.Bot, telegram.Update)
    join(telegram.Bot, telegram.Update)
    leave(telegram.Bot, telegram.Update)
    '''

    def __init__(self, manager, chat_handler):
        self.manager = manager
        self.chat = chat_handler

    def reply_text(self, update, message):
        while True:
            try:
                update.message.reply_text(message)
            except TimedOut:
                print("Timed out error in message.reply_text to {}, retrying: {}".format(str(chat_id), message))
                time.sleep(0.5)
                continue
            break


    def forcestart(self, bot, update):
        user = update.message.from_user
        # admin_list = update.message.chat.get_administrators()
        # admins = [cm.user for cm in admin_list]
        # if (user not in admins):
        #     self.reply_text(update, 'You must be an admin of a group chat to do this!')
        #     return
        game = self.manager.find_game(user, update.message.chat_id)
        if (not game):
            self.reply_text(update, 'Please join the game first before starting one!')
            return
        if (game.state != 0):
            self.reply_text(update, 'Game already started!')
            return
        # populate game with bots
        while (game.add_bot() != -1):
            time.sleep(0.5)
            pass
        if (game.state == 0):
            game.start_game()
        self.manager.update_gamelists()


    # /join command util
    def join(self, bot, update):
        # attempt to add player to game
        user = update.message.from_user
        game = self.manager.join_game(user, update.message.chat)

        if game == -1:
            self.reply_text(update, 'Could not join: games are currently full.')
            return

        elif game == -2:
            self.reply_text(update, 'You are already in the game.')
            return

        elif not isinstance(game, BridgeGame):
            raise TypeError('GameManager.join_game() did not return a valid BridgeGame object')

        # send broadcast update to all members of the room
        self.chat.player_joined_game(user, game)


    # /leave command util
    def leave(self, bot, update):
        # attempt to remove player from game
        user = update.message.from_user
        game = self.manager.leave_game(user, update.message.chat_id)

        if game == -1:
            self.reply_text(update, 'You are already not in the game.')
            return

        elif not isinstance(game, BridgeGame):
            raise TypeError('GameManager.join_game() did not return a valid BridgeGame object')

        self.reply_text(update, 'You left the game.')
        # send broadcast update to all members of the room
        self.chat.player_left_game(user, game)

    def hand(self, bot, update):
        user = update.message.from_user
        chat_id = update.message.chat_id
        for g in self.manager.active_games:
            for p in g.players:
                if p.id == user.id:
                    if update.message.chat.type != 'private':
                        self.chat.ask_private_chat(g)
                        return
                    self.chat.display_game_players(chat_id, g)
                    self.chat.display_hand(p, chat_id)

    '''
    RegexHandlers
    '''

    def bidding(self, bot, update):
        # handles all text messgaes that have the format NUMBER|SUIT
        user = update.message.from_user
        game = self.manager.find_game(user, update.message.chat_id)
        bid_id = self.chat.str_utils.bid_str_to_id(update.message.text)
        if isinstance(game, BridgeGame):
            if game.state != 1 or user.id != game.curr_player().id:
                self.reply_text(update, 'You cannot bid at this time!')
                return
            game.process_bid(bid_id)
            return

    def card(self, bot, update):
        user = update.message.from_user
        game = self.manager.find_game(user, update.message.chat_id)
        card_str = update.message.text
        card_id = self.chat.str_utils.card_str_to_id(card_str)
        if isinstance(game, BridgeGame):
            if game.state == 2 and user.id == game.curr_player().id:
                # Chose a partner, update game state
                game.partner = game.player_holding_card(card_id)
                self.chat.partner_chosen(game.curr_player(), card_id, game)
                # update state
                game.next_turn()
            elif game.state == 3 and user.id == game.curr_player().id:
                # Played a card, update game state
                card = BridgeCard(card_id)
                if card.id in [c.id for c in game.curr_player().hand] and game.valid_play(card):
                    game.curr_player().remove_card(card)
                    game.trick.append(card)
                    if card.suit == game.get_trump_suit():
                        game.trump_broken = 1
                    self.chat.card_played(game.curr_player(), card, game)
                    game.next_turn()
                else:
                    self.reply_text(update, 'Invalid card!')
                    self.chat.request_card(game.curr_player(), game)
            else:
                self.reply_text(update, 'Not you turn to play a card! Current turn: {}'. format(game.curr_player().disp_name()))
        return
