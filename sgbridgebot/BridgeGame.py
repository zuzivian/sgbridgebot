import asyncio
import logging
import random
import uuid

from telegram import User

from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.BridgePlayer import BridgePlayer
from sgbridgebot.errors import (
    AlreadyInGameError,
    GameFullError,
    InvalidBidError,
    InvalidPlayError,
    NotInGameError,
)
from sgbridgebot.game_types import IN_PROGRESS_STATES, GameState, GameType
from sgbridgebot.StringUtils import StringUtils

BOT_PAUSE = 0.5
MAX_REDEAL_ATTEMPTS = 200
# A human who lets this many turns in a row time out is handed over to a bot.
MAX_IDLE_STRIKES = 3

SUIT_SYMBOLS = [BridgeCard.CARD_SUITS[suit] for suit in range(4)]

logger = logging.getLogger(__name__)


class BridgeGame:
    """
    Creates an instance of a BridgeGame
    which includes all information about the game

    ATTRIBUTES
    players (listof BridgePlayer)
    state (GameState): game lifecycle state
    lock (asyncio.Lock): serialises every action on this game
    action_seq (int): bumped whenever the turn moves on; prompts carry it so
        that stale buttons can be rejected

    ARGS
    add_player(Telegram.User):
    remove_player(Telegram.User):
    start_game(): moves from waiting
    """


    # Initial game state is an empty game in the PREGAME state
    def __init__(self, handler, type, num_bots=0, on_game_complete=None,
                 turn_timeout=None, bot_pause=BOT_PAUSE):
        self.id = uuid.uuid4()
        self.short_id = self.id.hex[:8]
        self.type = GameType(type)
        self.state = GameState.SETUP
        self.chat_handler = handler
        self.on_game_complete = on_game_complete
        self.turn_timeout = turn_timeout
        self.bot_pause = bot_pause
        self.lock = asyncio.Lock()
        self.players = []
        self.turn = 0 #1=,2,3,4 or 0 for nobody
        self.contract = -1 # winning bid
        self.consecutive_passes = 0
        self.declarer = None
        self.partner_card = None
        self.partner = None
        self.partner_suit_choice = None
        self.partner_revealed = False
        self.trick = []
        self.trick_start = None
        self.trick_message = {}  # chat_id -> message_id of the live trick message
        self.tricks_played = 0
        self.trump_broken = 0
        self.trick_history = []
        self.action_seq = 0
        self.last_prompt = None  # (chat_id, message_id) of the open inline prompt
        self.idle_strikes = {}
        self._idle_task = None

    '''
    PLAYER RELATED
    '''

    def num_players(self):
        return len(self.players)

    def has_humans(self):
        return any(not p.is_bot for p in self.players)

    def is_in_progress(self):
        return self.state in IN_PROGRESS_STATES

    def get_player(self, user_id):
        for p in self.players:
            if p.id == user_id:
                return p
        return None

    # adds a player to the game if it is not full
    async def add_player(self, user, chat_id):
        if not isinstance(user, User) or not isinstance(chat_id, int):
            raise TypeError
        elif self.num_players() == 4 or self.state != GameState.SETUP:
            raise GameFullError()
        elif user.id in [p.id for p in self.players]:
            raise AlreadyInGameError()
        else:
            player = BridgePlayer(user, chat_id)
            self.players.append(player)
            await self.chat_handler.player_joined_game(player, self)
            if self.num_players() == 4:
                # if room is full, get the game started
                await self.start_game()
            return self

    # removes a player from the game, handing their seat to a bot mid-game
    async def remove_player(self, user, chat_id):
        if not isinstance(user, User) or not isinstance(chat_id, int):
            raise TypeError
        player = self.get_player(user.id)
        if player is None:
            raise NotInGameError()
        if self.state == GameState.SETUP:
            self.players.remove(player)
            return self
        await self.replace_with_bot(player)
        return self

    async def replace_with_bot(self, player):
        was_current = self.is_in_progress() and player is self.curr_player()
        old_id = player.id
        player.player_to_bot()
        self.idle_strikes.pop(old_id, None)
        if not self.is_in_progress():
            return
        if not self.has_humans():
            await self.abandon()
        elif was_current:
            # The seat that just changed hands was on turn; let the bot move.
            self._cancel_idle_timer()
            await self.chat_handler.clear_prompt(self)
            await self.continue_play()

    async def add_bot(self):
        if self.num_players() == 4:
            raise GameFullError()
        newbot = BridgePlayer()
        self.players.append(newbot)
        await self.chat_handler.player_joined_game(newbot, self)
        if self.num_players() == 4:
            await self.start_game()

    def player_num(self, player):
        for i in range(4):
            if player is self.players[i]:
                return i

    def get_trump_suit(self):
        return self.contract%5

    def get_chat_ids(self):
        chat_ids = []
        for p in self.players:
            if p.chat_id is not None and p.chat_id not in chat_ids:
                chat_ids.append(p.chat_id)
        return chat_ids

    def player_listing(self):
        return ", ".join([p.disp_name() for p in self.players])


    '''
    CARD RELATED
    '''

    def deal_hands(self):
        '''
        Shuffles and deals cards to each player.
        '''
        # Makes cards a random list of BridgeCards.
        card_nums = list(range(52))
        random.shuffle(card_nums)
        cards = []
        for id in card_nums:
            cards.append(BridgeCard(id))
        for p in self.players:
            p.hand = []
        # Deal cards, cycling between players.
        for r in range(13):
            for p in range(4):
                self.players[p].hand.append(cards[4*r+p])
        # Sort each player's hand by card ID.
        for p in self.players:
            p.hand.sort(key=lambda c: c.id)
        return

    async def show_hands(self, player=None):
        if (self.type == GameType.GROUP):
            # Never in the group chat: hands go to each player's private chat.
            if player is None:
                await self.chat_handler.ask_private_chat(self)
            for p in ([player] if player is not None else self.players):
                if not p.is_bot:
                    await self.chat_handler.display_hand_privately(p)
            return
        if player is not None:
            await self.chat_handler.display_hand(player)
            return
        for p in self.players:
            await self.chat_handler.display_hand(p)
        return


    '''
    GAME STATE RELATED
    '''

    async def start_game(self):
        '''
        Takes a game instance and deals cards to each player.
        '''
        self.state = GameState.AUCTION
        await self.chat_handler.starting_game(self)
        #give each player a direction
        dirs = 1
        for p in self.players:
            p.give_direction(dirs)
            dirs += 1
        # Deal cards and ensure there is no wash.
        wash = True
        redeal_attempts = 0
        while wash:
            wash = False
            redeal_attempts += 1
            self.deal_hands()
            for p in self.players:
                if p.hand_score(p.hand) < 4:
                    wash = True
            if wash and redeal_attempts >= MAX_REDEAL_ATTEMPTS:
                logger.error(
                    "Redeal attempt limit exceeded: game_id=%s, attempts=%s",
                    self.id,
                    redeal_attempts,
                )
                logger.warning(
                    "Accepting latest deal after redeal limit reached; wash condition remains: "
                    "game_id=%s",
                    self.id,
                )
                wash = False
        await self.show_hands()
        self.turn = 0
        self.contract = -1
        self.consecutive_passes = 0
        self.declarer = self.curr_player()
        await self.get_next_bid()
        return

    async def end_game(self):
        self.state = GameState.SCORING
        self._cancel_idle_timer()
        required_tricks = 7 + self.contract//5
        assert self.declarer is not None
        assert self.partner is not None
        declarer_tricks = self.declarer.tricks_won + self.partner.tricks_won
        declarers = [self.declarer, self.partner]
        if self.declarer == self.partner:
            declarer_tricks //= 2
            declarers.remove(self.partner)
        if (declarer_tricks >= required_tricks):
            # declarer and partner won the game
            await self.chat_handler.game_winners(
                0, declarers, declarer_tricks, required_tricks, self
            )
        else:
            winning_team = list(self.players)
            winning_team.remove(self.declarer)
            if self.declarer != self.partner:
                winning_team.remove(self.partner)
            await self.chat_handler.game_winners(
                1, winning_team, declarer_tricks, required_tricks, self
            )
        # end of game.. exiting..
        self.players = []
        await self._notify_complete()

    async def abandon(self):
        '''
        Stops a game that has no human players left.
        '''
        self.state = GameState.SCORING
        self._cancel_idle_timer()
        logger.info("Game abandoned with no human players left: game_id=%s", self.id)
        await self._notify_complete()

    async def _notify_complete(self):
        if self.on_game_complete is not None:
            callback_result = self.on_game_complete(self.id)
            if asyncio.iscoroutine(callback_result):
                await callback_result

    def curr_player(self):
        return self.players[self.turn]

    async def continue_play(self):
        '''
        Prompts the player on turn, or lets the bot on turn move.
        '''
        if self.state == GameState.AUCTION:
            await self.get_next_bid()
        elif self.state == GameState.PARTNER_CALL:
            await self.get_partner_choice()
        elif self.state == GameState.PLAY:
            await self.get_next_card()

    async def next_turn(self):
        self.action_seq += 1
        self._cancel_idle_timer()
        if not self.has_humans():
            await self.abandon()
            return
        self.turn = (self.turn+1) % 4
        if (self.state == GameState.AUCTION):
            assert self.declarer is not None
            if (self.declarer.id == self.curr_player().id):
                self.state = GameState.PARTNER_CALL
                await self.chat_handler.bid_winner(self.curr_player(), self.contract, self)
                await self.get_partner_choice()
                return
            else:
                await self.get_next_bid()
                return
        elif (self.state == GameState.PARTNER_CALL):
            self.state = GameState.PLAY
            if self.contract % 5 == 4:
                # start with declarer
                self.turn = (self.turn-1) % 4
            self.trick_start = self.curr_player().direction - 1
        if (self.state == GameState.PLAY):
            #play logic
            if len(self.trick) == 4:
                self.trick_history.append(self.trick)
                await self.decide_trick_winner()
                self.tricks_played += 1
                self.trick_message = {}
            if self.tricks_played == 13:
                await self.end_game()
                return
            await self.get_next_card()
        return

    def is_declarer_side(self, player):
        return player is self.declarer or player is self.partner

    def known_teammate(self, viewer, other):
        '''
        What `viewer` can know about `other` during play: True if they are on
        the same side, False if not, None while the partner is still hidden.
        Everyone knows their own side; the partner's side is public once the
        partner card is played, and the partner knows it from the start.
        '''
        if viewer is other:
            return True
        same_side = self.is_declarer_side(viewer) == self.is_declarer_side(other)
        if self.partner_revealed or other is self.declarer:
            return same_side
        if viewer is self.partner:
            # The partner holds the card, so it can tell everyone's side.
            return same_side
        if viewer is self.declarer and self.partner is self.declarer:
            # Calling a card of your own means the other three are all against you.
            return False
        return None

    def player_holding_card(self, card_id):
        for p in self.players:
            for card in p.hand:
                if card.id == card_id:
                    return p


    '''
    IDLE TIMER
    '''

    def _arm_idle_timer(self):
        self._cancel_idle_timer()
        if not self.turn_timeout:
            return
        self._idle_task = asyncio.get_running_loop().create_task(
            self._idle_timeout(self.action_seq)
        )

    def _cancel_idle_timer(self):
        if self._idle_task is not None and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

    async def _idle_timeout(self, seq):
        await asyncio.sleep(self.turn_timeout)
        async with self.lock:
            if seq != self.action_seq or not self.is_in_progress():
                return
            # This task is about to act, so it must not cancel itself on re-arm.
            self._idle_task = None
            player = self.curr_player()
            if player.is_bot:
                return
            strikes = self.idle_strikes.get(player.id, 0) + 1
            self.idle_strikes[player.id] = strikes
            handed_over = strikes >= MAX_IDLE_STRIKES
            await self.chat_handler.clear_prompt(self)
            await self.chat_handler.player_timed_out(player, self, handed_over)
            if handed_over:
                await self.replace_with_bot(player)
                return
            await self.auto_act(player)

    async def auto_act(self, player):
        '''
        Makes a move on behalf of a player who ran out of time.
        '''
        if self.state == GameState.AUCTION:
            await self.process_bid(-1)
        elif self.state == GameState.PARTNER_CALL:
            await self.choose_partner(player.make_auto_partner(self.get_trump_suit()))
        elif self.state == GameState.PLAY:
            await self._commit_card(player, player.play_auto_card(self.trick, self))

    def note_activity(self, player):
        self.idle_strikes.pop(player.id, None)


    '''
    BIDDING RELATED
    '''

    def validate_bid(self, bid):
        if bid == -1:
            return
        if not 0 <= bid <= 34:
            raise InvalidBidError('That is not a valid bid.')
        if bid <= self.contract:
            current = StringUtils().bid_id_to_str(self.contract)
            raise InvalidBidError(f'You must bid higher than {current}, or pass.')

    async def make_bid(self, player, bid):
        if self.state != GameState.AUCTION or player is not self.curr_player():
            raise InvalidBidError('You cannot bid right now. Wait for your turn.')
        self.validate_bid(bid)
        self.note_activity(player)
        await self.process_bid(bid)

    async def process_bid(self, bid):
        if bid == -1:
            self.consecutive_passes += 1
            await self.chat_handler.player_passed(self.curr_player(), self)
            if self.contract == -1 and self.consecutive_passes == 4:
                # Four opening passes: redeal and restart auction from North.
                self.action_seq += 1
                self.consecutive_passes = 0
                self.turn = 0
                self.contract = -1
                self.declarer = self.curr_player()
                self.deal_hands()
                await self.show_hands()
                await self.get_next_bid()
                return
            await self.next_turn()
        elif bid > self.contract:
            self.contract = bid
            self.consecutive_passes = 0
            self.declarer = self.curr_player()
            await self.chat_handler.player_bid(bid, self.curr_player(), self)
            await self.next_turn()
        elif not self.curr_player().is_bot:
            await self.chat_handler.invalid_bid(self.curr_player(), self)
        else:
            logger.warning(
                "Invalid bid made by bot; ignoring bid and continuing auction context: "
                "game_id=%s, player_id=%s, contract=%s, attempted_bid=%s",
                self.id,
                self.curr_player().id,
                self.contract,
                bid,
            )
        return

    async def get_next_bid(self):
        if not self.curr_player().is_bot:
            await self.chat_handler.request_bid(self.curr_player(), self)
            self._arm_idle_timer()
        else:
            bid = self.curr_player().make_auto_bid(self.contract)
            if bid != -1 and bid <= self.contract:
                # Never let a bad bot bid stall the auction.
                bid = -1
            await asyncio.sleep(self.bot_pause)
            await self.process_bid(bid)
        return

    '''
    PARTNER CHOOSING
    '''

    async def get_partner_choice(self):
        if self.curr_player().is_bot:
            await self.choose_partner(
                self.curr_player().make_auto_partner(self.get_trump_suit())
            )
            return
        else:
            # request partner choice
            self.partner_suit_choice = None
            await self.show_hands(self.curr_player())
            await self.chat_handler.request_partner_choice(self.curr_player(), self)
            self._arm_idle_timer()
            return

    async def choose_partner(self, card_id):
        if not isinstance(card_id, int) or not 0 <= card_id <= 51:
            raise InvalidPlayError('That is not a valid card.')
        if self.state != GameState.PARTNER_CALL:
            raise InvalidPlayError('You cannot call a partner right now.')
        self.partner = self.player_holding_card(card_id)
        self.partner_card = BridgeCard(card_id)
        self.partner_suit_choice = None
        #broadcast partner choice
        await self.chat_handler.partner_chosen(self.curr_player(), card_id, self)
        #update game state
        await self.next_turn()

    '''
    GAME PLAY
    '''
    async def decide_trick_winner(self):
        # winner is p[0] by default for now
        trump_suit = self.contract % 5
        w = 0
        best_suit = self.trick[0].suit
        best_rank = self.trick[0].rank
        for id in range(4):
            c = self.trick[id]
            if (c.suit == trump_suit and (best_suit != trump_suit or c.rank > best_rank)):
                best_suit = c.suit
                best_rank = c.rank
                w = id
            elif (c.suit == best_suit and c.rank > best_rank):
                best_rank = c.rank
                w = id
        assert self.trick_start is not None
        winner = (self.trick_start + w) % 4

        self.players[winner].tricks_won += 1
        # announce winner of trick with card
        await self.chat_handler.announce_trick(self.players[winner], self.trick[w], self)
        # start next trick
        self.turn = winner
        self.trick_start = winner
        self.trick = []
        return

    async def get_next_card(self):
        if (self.curr_player().is_bot):
            played_card = self.curr_player().play_auto_card(self.trick, self)
            await asyncio.sleep(self.bot_pause)
            await self._commit_card(self.curr_player(), played_card)
        else:
            await self.chat_handler.request_card(self.curr_player(), self)
            self._arm_idle_timer()
        return

    def validate_card(self, player, card_id):
        if self.state != GameState.PLAY or player is not self.curr_player():
            raise InvalidPlayError('It is not your turn to play a card.')
        card = BridgeCard(card_id)
        if card.id not in [c.id for c in player.hand]:
            raise InvalidPlayError(
                f'You do not hold {card!r}.', self.legal_cards(player)
            )
        is_valid, reason, legal_cards = self.valid_play_details(card)
        if not is_valid:
            raise InvalidPlayError(reason, legal_cards)
        return card

    async def play_card(self, player, card_id):
        card = self.validate_card(player, card_id)
        removed_card = player.remove_card(card)
        if removed_card is None:
            raise InvalidPlayError('Could not play card. Please try again.')
        self.note_activity(player)
        await self._commit_card(player, removed_card)

    async def _commit_card(self, player, card):
        self.trick.append(card)
        if card.suit == self.get_trump_suit():
            self.trump_broken = 1
        if self.partner_card is not None and card.id == self.partner_card.id:
            self.partner_revealed = True
        await self.chat_handler.card_played(player, card, self)
        await self.next_turn()

    def legal_cards(self, player):
        return [repr(c) for c in player.hand if self._play_allowed(player, c)]

    def legal_card_objects(self, player):
        return [c for c in player.hand if self._play_allowed(player, c)]

    def _play_allowed(self, player, card):
        trump_suit = self.get_trump_suit()
        if len(self.trick) == 0:
            if card.suit == trump_suit and not self.trump_broken:
                # Trump may only be led before it is broken by a hand of all trumps.
                return all(c.suit == trump_suit for c in player.hand)
            return True
        leading_suit = self.trick[0].suit
        if card.suit != leading_suit and player.get_all_suit(leading_suit):
            return False
        return True

    def valid_play(self, card):
        is_valid, _, _ = self.valid_play_details(card)
        return is_valid

    def valid_play_details(self, card):
        player = self.curr_player()
        if self._play_allowed(player, card):
            return True, None, []
        legal_cards = self.legal_cards(player)
        if len(self.trick) == 0:
            trump_suit = self.get_trump_suit()
            return False, f"Trump ({SUIT_SYMBOLS[trump_suit]}) is not broken yet.", legal_cards
        leading_suit = self.trick[0].suit
        return False, f"You must follow suit ({SUIT_SYMBOLS[leading_suit]}).", legal_cards
