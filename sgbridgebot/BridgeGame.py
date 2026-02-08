from telegram import User
from sgbridgebot.BridgePlayer import BridgePlayer
from sgbridgebot.BridgeCard import BridgeCard
import uuid, random, asyncio

BOT_PAUSE = 0.5


class BridgeGame(object):
    """
    Creates an instance of a BridgeGame
    which includes all information about the game

    ATTRIBUTES
    players (listof Telegram.User)
    state (int): 0=setup; 1=auction; 2=partner_call; 3=play; 4=scoring

    ARGS
    add_player(Telegram.User):
    remove_player(Telegram.User):
    start_game(): moves from waiting
    """


    # Initial game state is an empty game in the PREGAME state
    def __init__(self, handler, type, num_bots=0):
        self.id = uuid.uuid1()
        self.type = type # 0 for public, 1 for private
        self.state = 0
        self.chat_handler = handler
        self.players = []
        self.turn = 0 #1=,2,3,4 or 0 for nobody
        self.contract = -1 # winning bid
        self.consecutive_passes = 0
        self.declarer = None
        self.partner_card = None
        self.partner = None
        self.trick = []
        self.trick_start = None
        self.trick_message = []
        self.tricks_played = 0
        self.trump_broken = 0
        self.trick_history = []

    '''
    PLAYER RELATED
    '''

    def num_players(self):
        return len(self.players)

    # adds a player to the game if it is not full
    async def add_player(self, user, chat_id):
        if not isinstance(user, User) or not isinstance(chat_id, int):
            raise TypeError
        elif self.num_players() == 4 or self.state != 0:
            return -1 # full
        elif user.id in [p.id for p in self.players]:
            return -2 # already in game
        else:
            self.players.append(BridgePlayer(user, chat_id))
            if self.num_players() == 4:
                # if room is full, get the game started
                await self.start_game()
            return self

    # removes a player from the game
    def remove_player(self, user, chat_id):
        if not isinstance(user, User) or not isinstance(chat_id, int):
            raise TypeError
        elif user.id not in [p.id for p in self.players]:
            return -1
        else:
            #replace with bot if necessary
            for p in self.players:
                if p.id == user.id:
                    if (self.state > 0):
                        p.player_to_bot()
                    else:
                        self.players.remove(p)
                    break
            return self

    async def add_bot(self):
        if self.num_players() == 4:
            return -1
        newbot = BridgePlayer()
        self.players.append(newbot)
        await self.chat_handler.player_joined_game(newbot, self)
        if self.num_players() == 4:
            await self.start_game()
        return 1

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
        if (self.type == 1):
            await self.chat_handler.ask_private_chat(self)
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
        self.state = 1
        await self.chat_handler.starting_game(self)
        #give each player a direction
        dirs = 1
        for p in self.players:
            p.give_direction(dirs)
            dirs += 1
        # Deal cards and ensure there is no wash.
        wash = True
        while wash:
            wash = False
            self.deal_hands()
            for p in self.players:
                if p.hand_score(p.hand) < 4:
                    wash = True
        await self.show_hands()
        self.turn = 0
        self.contract = -1
        self.consecutive_passes = 0
        self.declarer = self.curr_player()
        if not self.curr_player().is_bot:
            await self.chat_handler.request_bid(self.curr_player())
        return

    async def end_game(self):
        self.state = 4
        required_tricks = 7 + self.contract//5
        declarer_tricks = self.declarer.tricks_won + self.partner.tricks_won
        declarers = [self.declarer, self.partner]
        if self.declarer == self.partner:
            declarer_tricks //= 2
            declarers.remove(self.partner)
        if (declarer_tricks >= required_tricks):
            # declarer and partner won the game
            await self.chat_handler.game_winners(0, declarers, declarer_tricks, required_tricks, self)
        else:
            winning_team = list(self.players)
            winning_team.remove(self.declarer)
            if self.declarer != self.partner:
                winning_team.remove(self.partner)
            await self.chat_handler.game_winners(1, winning_team, declarer_tricks, required_tricks, self)
        # end of game.. exiting..
        self.players = []

    def curr_player(self):
        return self.players[self.turn]

    async def next_turn(self):
        self.turn = (self.turn+1) % 4
        if (self.state == 1):
            if (self.declarer.id == self.curr_player().id):
                self.state = 2
                await self.chat_handler.bid_winner(self.curr_player(), self.contract, self)
                await self.get_partner_choice()
            else:
                await self.get_next_bid()
        elif (self.state == 2):
            self.state = 3
            if self.contract % 5 == 4:
                # start with declarer
                self.turn = (self.turn-1) % 4
            self.trick_start = self.curr_player().direction - 1
        if (self.state == 3):
            #play logic
            if len(self.trick) == 4:
                self.trick_history.append(self.trick)
                await self.decide_trick_winner()
                self.tricks_played += 1
                self.trick_message = []
            if self.tricks_played == 13:
                await self.end_game()
                return
            await self.get_next_card()
        return

    def player_holding_card(self, card_id):
        for p in self.players:
            for card in p.hand:
                if card.id == card_id:
                    return p


    '''
    BIDDING RELATED
    '''

    async def process_bid(self, bid):
        if bid == -1:
            self.consecutive_passes += 1
            await self.chat_handler.player_passed(self.curr_player(), self)
            if self.contract == -1 and self.consecutive_passes == 4:
                # Four opening passes: redeal and restart auction from North.
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
            await self.chat_handler.invalid_bid(self.curr_player())
        else:
            print('invalid bid made by bot')
        return

    async def get_next_bid(self):
        if not self.curr_player().is_bot:
            await self.chat_handler.request_bid(self.players[self.turn])
        else:
            bid = self.curr_player().make_auto_bid(self.contract)
            await asyncio.sleep(BOT_PAUSE)
            await self.process_bid(bid)
        return

    '''
    PARTNER CHOOSING
    '''

    async def get_partner_choice(self):
        if self.curr_player().is_bot:
            card_id = self.curr_player().make_auto_partner()
            self.partner = self.player_holding_card(card_id)
            self.partner_card = BridgeCard(card_id)
            #broadcast partner choice
            await self.chat_handler.partner_chosen(self.curr_player(), card_id, self)
            #update game state
            await self.next_turn()
            return
        else:
            # request partner choice
            await self.show_hands(self.curr_player())
            await self.chat_handler.request_partner_choice(self.curr_player())
            return

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
            self.trick.append(played_card)
            if played_card.suit == self.get_trump_suit():
                self.trump_broken = 1
            await asyncio.sleep(BOT_PAUSE)
            await self.chat_handler.card_played(self.curr_player(), played_card, self)
            await self.next_turn()
        else:
            await self.chat_handler.request_card(self.curr_player(), self)
        return

    def valid_play(self, card):
        trump_suit = self.get_trump_suit()
        # can lead trump?
        if len(self.trick) == 0:
            if card.suit == trump_suit and not self.trump_broken:
                return False
            else:
                return True
        # can play other suit?
        leading_suit = self.trick[0].suit
        suit_cards_available = len(self.curr_player().get_all_suit(leading_suit)) != 0
        if leading_suit != card.suit and suit_cards_available:
            return False
        # if not, everything else if cool
        return True
