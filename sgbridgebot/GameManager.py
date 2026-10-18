import asyncio

from sgbridgebot.BridgeGame import BOT_PAUSE, BridgeGame
from sgbridgebot.errors import AlreadyInGameError, NotInGameError
from sgbridgebot.game_types import GameState, GameType


class GameManager:
        """
        Manages all instances of waiting and active BridgeGame,
        Manages player and bot events

        ATTRIBUTES
        waiting_games (listof BridgeGame)
        active_games (listof BridgeGame)
        lock (asyncio.Lock): serialises lobby changes (join/leave/forcestart).
            Always take it before a game's own lock, never after.

        ARGS
        create_game():
        destroy_game(uuid):
        end_game(uuid): removes game from active_games list
        join_game(player): returns the BridgeGame joined, raises GameError otherwise
        find_game(player, chat_id):
        leave_game(player): returns the BridgeGame left, raises NotInGameError otherwise
        update_gamelists(): when game state is changed, call to move games to appropriate lists
        """

        # Initial bot state contains empty game list
        def __init__(self, handler, turn_timeout=None, bot_pause=BOT_PAUSE):
            self.waiting_games = []
            self.active_games = []
            self.chat_handler = handler
            self.turn_timeout = turn_timeout
            self.bot_pause = bot_pause
            self.lock = asyncio.Lock()

        def create_game(self, type, num_bots=0):
            g = BridgeGame(
                self.chat_handler, type, num_bots, on_game_complete=self.end_game,
                turn_timeout=self.turn_timeout, bot_pause=self.bot_pause,
            )
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
            async with self.lock:
                # don't allow joining if already in a game
                if self.find_game(player, chat.id) is not None:
                    raise AlreadyInGameError()
                game = None
                if chat.type != 'private':
                    # allow friends in group chat to join group game
                    for g in self.waiting_games:
                        if g.type == GameType.GROUP and chat.id in g.get_chat_ids():
                            game = g
                            break
                    if game is None:
                        game = self.create_game(GameType.GROUP)
                else: # join auto game
                    # add player to oldest waiting game
                    for g in self.waiting_games:
                        if len(g.players) < 4 and g.type == GameType.MATCHMAKING:
                            game = g
                            break
                    if game is None:
                        game = self.create_game(GameType.MATCHMAKING)
                try:
                    async with game.lock:
                        await game.add_player(player, chat.id)
                finally:
                    self.update_gamelists()
                return game

        def find_game(self, player, chat_id):
            for g in self.waiting_games + self.active_games:
                for p in g.players:
                    if p.id == player.id and p.chat_id == chat_id:
                        return g
            return None

        def find_game_for_user(self, user_id, chat_id, chat_type='private'):
            '''
            Finds the game a message from this user in this chat belongs to.
            A private chat with the bot also reaches the user's group game.
            '''
            for g in self.waiting_games + self.active_games:
                for p in g.players:
                    if p.id == user_id and p.chat_id == chat_id:
                        return g
            if chat_type == 'private':
                for g in self.active_games:
                    if any(p.id == user_id for p in g.players):
                        return g
            return None

        def find_game_by_short_id(self, short_id):
            # A game is still in waiting_games while its first prompt goes out.
            for g in self.waiting_games + self.active_games:
                if g.short_id == short_id:
                    return g
            return None

        def games_for_user(self, user_id):
            return [
                g for g in self.waiting_games + self.active_games
                if any(p.id == user_id for p in g.players)
            ]

        async def leave_game(self, player, chat_id):
            async with self.lock:
                game = self.find_game(player, chat_id)
                if game is None:
                    raise NotInGameError()
                try:
                    async with game.lock:
                        await game.remove_player(player, chat_id)
                finally:
                    self.update_gamelists()
                return game

        async def forcestart(self, player, chat_id):
            '''
            Fills the empty seats of the player's lobby with bots.
            Returns the game, or None if it had already started.
            '''
            async with self.lock:
                game = self.find_game(player, chat_id)
                if game is None:
                    raise NotInGameError('Please join the game first before starting one!')
                if game.state != GameState.SETUP:
                    return None
                try:
                    async with game.lock:
                        while game.num_players() < 4:
                            await game.add_bot()
                finally:
                    self.update_gamelists()
                return game

        def all_chat_ids(self):
            chat_ids = []
            for g in self.waiting_games + self.active_games:
                for chat_id in g.get_chat_ids():
                    if chat_id not in chat_ids:
                        chat_ids.append(chat_id)
            return chat_ids

        # scan list of games that need updating
        def update_gamelists(self):
            to_start = []
            to_destroy = []
            to_end = []

            # identify waiting games to transition/remove
            for g in self.waiting_games:
                player_count = g.num_players()
                if player_count == 4:
                    to_start.append(g.id)
                elif player_count == 0:
                    to_destroy.append(g.id)

            # identify active games that no longer have real players
            for g in self.active_games:
                users = 0
                for p in g.players:
                    if not p.is_bot:
                        users += 1
                if users == 0:
                    to_end.append(g.id)

            # apply waiting game transitions/removals
            for game_id in to_start:
                self.start_game(game_id)
            for game_id in to_destroy:
                self.destroy_game(game_id)

            # apply active game removals
            for game_id in to_end:
                self.end_game(game_id)
