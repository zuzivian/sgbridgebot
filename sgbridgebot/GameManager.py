from sgbridgebot.BridgeGame import BridgeGame

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
        find_game(player, chat_id):
        leave_game(player): returns BridgeGame if player able to leave, else error code
        update_gamelists(): when game state is changed, call to move games to appropriate lists
        """

        # Initial bot state contains empty game list
        def __init__(self, handler):
            self.waiting_games = []
            self.active_games = []
            self.chat_handler = handler

        def create_game(self, type, num_bots=0):
            g = BridgeGame(self.chat_handler, type, num_bots)
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

        async def join_game(self, player, chat):
            game_state = None
            # don't allow joining if already in a game
            game = self.find_game(player, chat.id)
            if isinstance(game, BridgeGame):
                return -2
            # allow friends in group chat to join group game
            if chat.type != 'private':
                found = 0
                for g in self.waiting_games:
                    if chat.id in [p.chat_id for p in g.players] and g.type == 1:
                        found = 1
                        break
                if not found:
                    g = self.create_game(1)
                game_state = await g.add_player(player, chat.id)
                self.update_gamelists()
                return game_state
            else: # join auto game
                # add player to oldest waiting game
                game = None
                for g in self.waiting_games:
                    if len(g.players) < 4 and g.type == 0:
                        game = g
                        break
                if game is None:
                    game = self.create_game(0)
                game_state = await game.add_player(player, chat.id)
            self.update_gamelists()
            if game_state is None:
                return -1
            else:
                return game_state

        def find_game(self, player, chat_id):
            for g in self.waiting_games:
                if player.id in [p.id for p in g.players] and chat_id in [p.chat_id for p in g.players]:
                    return g
            for g in self.active_games:
                if player.id in [p.id for p in g.players] and chat_id in [p.chat_id for p in g.players]:
                    return g
            return None

        def leave_game(self, player, chat_id):
            for g in self.waiting_games:
                for cid in [p.chat_id for p in g.players]:
                    if chat_id == cid:
                        game = g.remove_player(player, chat_id)
                        self.update_gamelists()
                        return game
            for g in self.active_games:
                for cid in [p.chat_id for p in g.players]:
                    if chat_id == cid:
                        game = g.remove_player(player, chat_id)
                        self.update_gamelists()
                        return game
            return -1

        # scan list of games that need updating
        def update_gamelists(self):
            # move full games to active list
            for g in self.waiting_games:
                if g.num_players() == 4:
                    self.start_game(g.id)
                if g.num_players() == 0:
                    self.destroy_game(g.id)
            # remove games that no longer have real players
            for g in self.active_games:
                users = 0
                for p in g.players:
                    if not p.is_bot:
                        users += 1
                if users == 0:
                    self.end_game(g.id)
