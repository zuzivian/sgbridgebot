from telegram.ext import Updater, CommandHandler
from BridgeGame import BridgeGame
import logging

class GameManager(object):
        """
        Manages all instances of waiting and active BridgeGame,
        Manages player and bot events

        ATTRIBUTES
        waiting_games (listof BridgeGame)
        active_games (listof BridgeGame)

        ARGS
        create_game():
        destroy_game(uuid):
        end_game(uuid): removes game from active_games list
        join_game(player): returns BridgeGame if player able to join, else error code
        leave_game(player): returns BridgeGame if player able to leave, else error code
        update_gamelists(): when game state is changed, call to move games to appropriate lists
        """

        # Initial bot state contains empty game list
        def __init__(self):
            self.waiting_games = []
            self.active_games = []

        def create_game(self, num_bots=0):
            g = BridgeGame(num_bots)
            self.waiting_games.append(g)
            return g

        def start_game(self, game_id):
            for g in self.waiting_games:
                if game_id == g.id:
                    self.active_games.append(g)
                    self.waiting_games.remove(g)
                    return g

        def destroy_game(self, game_id):
            for g in self.waiting_games:
                if game_id == g.id:
                    self.waiting_games.remove(g)

        def end_game(self, game_id):
            for g in self.active_games:
                if game_id == g.id:
                    self.active_games.remove(g)

        def join_game(self, player, chat_id, game_id=None):
            if game_id:
                for g in self.waiting_games:
                    if game_id == g.id:
                        game = g.add_player(player, chat_id)
            else:
                # add player to oldest waiting game
                if not len(self.waiting_games):
                    self.create_game()
                game = self.waiting_games[0].add_player(player, chat_id)
            self.update_gamelists()
            return game

        def leave_game(self, player, chat_id):
            for g in self.waiting_games:
                for cid in g.player_chat_ids:
                    if chat_id == cid:
                        game = g.remove_player(player, chat_id)
                        self.update_gamelists()
                        return game
            for g in self.active_games:
                for cid in g.player_chat_ids:
                    if chat_id == cid:
                        game = g.remove_player(player, chat_id)
                        self.update_gamelists()
                        return game
            return -1

        # scan list of games that need updating
        def update_gamelists(self):
            # move full games to active list
            for g in self.waiting_games:
                if g.num_players == 4:
                    self.start_game(g.id)
                if g.num_players == 0:
                    self.destroy_game(g.id)
            # remove games that have ended or no longer have players
            for g in self.active_games:
                if g.num_players == 0 or g.state < 0:
                    self.end_game(g.id)
