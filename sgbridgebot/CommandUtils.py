from telegram.ext import Updater, CommandHandler
from BridgeGame import BridgeGame
from GameManager import GameManager
import logging


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


    def forcestart(self, bot, update):
        user = update.message.from_user
        # admin_list = update.message.chat.get_administrators()
        # admins = [cm.user for cm in admin_list]
        # if (user not in admins):
        #     update.message.reply_text('You must be an admin of a group chat to do this!')
        #     return
        game = self.manager.find_game(user, update.message.chat_id)
        if (not game):
            update.message.reply_text('Please join the game first before starting one!')
            return
        if (game.state != 0):
            update.message.reply_text('Game already started!')
            return
        # populate game with bots
        while (game.add_bot() != -1):
            pass
        if (game.state == 0):
            game.start_game()

    # /hello command util
    def hello(self, bot, update):
        update.message.reply_text(
            'Hello {}.'.format(update.message.from_user.first_name))


    # /join command util
    def join(self, bot, update):
        # attempt to add player to game
        user = update.message.from_user
        game = self.manager.join_game(user, update.message.chat)

        if game == -1:
            update.message.reply_text('Could not join: all games are currently full.')
            return

        elif game == -2:
            update.message.reply_text('You are already in the game.')
            return

        elif not isinstance(game, BridgeGame):
            raise TypeError('GameManager.join_game() did not return a valid BridgeGame object')

        update.message.reply_text('You joined the game.')
        # send broadcast update to all members of the room
        self.chat.player_joined_game(user, game)


    # /leave command util
    def leave(self, bot, update):
        # attempt to remove player from game
        user = update.message.from_user
        game = self.manager.leave_game(user, update.message.chat_id)

        if game == -1:
            update.message.reply_text('You are already not in the game.')
            return

        elif not isinstance(game, BridgeGame):
            raise TypeError('GameManager.join_game() did not return a valid BridgeGame object')

        update.message.reply_text('You left the game.')
        # send broadcast update to all members of the room
        self.chat.player_left_game(user, game)


    def bidding(self, bot, update):
        # handles all text messgaes that have the format NUMBER|SUIT
        user = update.message.from_user
        game = self.manager.find_game(user, update.message.chat_id)
        bid_id = self.chat.str_utils.bid_str_to_id(update.message.text)
        if isinstance(game, BridgeGame):
            if game.state != 1 or user.id != game.curr_player().id:
                update.message.reply_text('You cannot bid at this time!')
                return
            game.process_bid(bid_id)
            return

    def card(self, bot, update):
        user = update.message.from_user
        game = self.manager.find_game(user, update.message.chat_id)
        card_str = update.message.text
        if isinstance(game, BridgeGame):
            if game.state == 2 and user.id == game.curr_player().id:
                update.message.reply_text('Partner chosen.')
                card_id = self.chat.str_utils.card_str_to_id(card_str)
                game.partner = game.player_holding_card(card_id)
                self.chat.partner_chosen(game.curr_player(), card_id, game)
            elif game.state == 3 and user.id == game.curr_player().id:
                update.message.reply_text('You played a card.')
        return
