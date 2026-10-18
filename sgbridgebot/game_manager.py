import asyncio
import logging
from dataclasses import dataclass

from sgbridgebot.bridge_game import BOT_PAUSE, BridgeGame
from sgbridgebot.errors import AlreadyInGameError, GameError, NotInGameError
from sgbridgebot.game_types import GameState, GameType

logger = logging.getLogger(__name__)

# Finished tables remembered for "Deal again"; the oldest are forgotten first.
MAX_REMATCH_OFFERS = 500


@dataclass
class RematchOffer:
    '''
    A finished table whose players can deal another hand together.
    seats lists (user id, chat id) per seat, with None as the user id for bots.
    '''
    game_type: GameType
    seats: list
    match_scores: dict
    match_names: dict
    hands_played: int
    next_game: BridgeGame | None = None

    def chat_id_for(self, user_id):
        for seat_user_id, chat_id in self.seats:
            if seat_user_id == user_id:
                return chat_id
        return None

    def bot_seats(self):
        return sum(1 for user_id, _ in self.seats if user_id is None)


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
        rematch(user, short_id): seats a player from a finished table at its next hand
        """

        # Initial bot state contains empty game list
        def __init__(self, handler, turn_timeout=None, bot_pause=BOT_PAUSE, stats=None):
            self.waiting_games = []
            self.stats = stats  # StatsStore, or None to keep no records
            self.active_games = []
            self.chat_handler = handler
            self.turn_timeout = turn_timeout
            self.bot_pause = bot_pause
            self.lock = asyncio.Lock()
            self.rematch_offers = {}  # short id of a finished game -> RematchOffer

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
                    if g.result is not None:
                        self._offer_rematch(g)
                        self._record_stats(g)
                    return

        def _record_stats(self, game):
            if self.stats is None:
                return
            try:
                self.stats.record_hand(game)
            except Exception:
                # Losing a stats row must never break the game itself.
                logger.exception('Could not record stats for game %s', game.id)

        def _offer_rematch(self, game):
            seats = [(None if p.is_bot else p.id, p.chat_id) for p in game.final_players]
            # Only the newest hand of a table can be dealt again.
            self.rematch_offers.pop(game.rematch_of, None)
            if all(user_id is None for user_id, _ in seats):
                return
            self.rematch_offers[game.short_id] = RematchOffer(
                game_type=game.type,
                seats=seats,
                match_scores=dict(game.match_scores),
                match_names=dict(game.match_names),
                hands_played=game.hands_played,
            )
            while len(self.rematch_offers) > MAX_REMATCH_OFFERS:
                self.rematch_offers.pop(next(iter(self.rematch_offers)))

        async def rematch(self, user, short_id):
            '''
            Seats a player from a finished table at that table's next hand.
            The first player back opens the lobby, with bots in the bot seats;
            the hand starts once every human is back, or on /forcestart.
            '''
            async with self.lock:
                offer = self.rematch_offers.get(short_id)
                if offer is None:
                    raise GameError('That table has closed. Use /join for a new game.')
                chat_id = offer.chat_id_for(user.id)
                if chat_id is None:
                    raise GameError('Only players from that table can deal again.')
                game = offer.next_game
                if game is not None and game.get_player(user.id) is not None:
                    raise AlreadyInGameError('You are already back at the table.')
                if game is not None and game.state != GameState.SETUP:
                    raise GameError(
                        'That table has already dealt the next hand. Use /join for a new game.'
                    )
                if self.games_for_user(user.id):
                    raise AlreadyInGameError()
                # A lobby everyone left is gone; the next player back opens a fresh one.
                is_new = game is None or game not in self.waiting_games
                if is_new:
                    game = self.create_game(offer.game_type)
                    game.rematch_of = short_id
                    game.match_scores = dict(offer.match_scores)
                    game.match_names = dict(offer.match_names)
                    game.hands_played = offer.hands_played
                    offer.next_game = game
                assert game is not None
                try:
                    async with game.lock:
                        await game.add_player(user, chat_id)
                        if is_new:
                            for _ in range(offer.bot_seats()):
                                if game.num_players() < 4:
                                    await game.add_bot()
                finally:
                    self.update_gamelists()
                return game

        async def join_game(self, player, chat):
            async with self.lock:
                # don't allow joining if already in a game
                if self.find_game(player, chat.id) is not None:
                    raise AlreadyInGameError()
                game = None
                if chat.type != 'private':
                    # allow friends in group chat to join group game
                    for g in self.waiting_games:
                        if g.rematch_of is None and g.type == GameType.GROUP \
                                and chat.id in g.get_chat_ids():
                            game = g
                            break
                    if game is None:
                        game = self.create_game(GameType.GROUP)
                else: # join auto game
                    # add player to oldest waiting game
                    for g in self.waiting_games:
                        if g.rematch_of is None and len(g.players) < 4 \
                                and g.type == GameType.MATCHMAKING:
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
