from telegram.ext import Updater, CommandHandler
from telegram import User, Chat
from BridgePlayer import BridgePlayer
from BridgeCard import BridgeCard
import uuid, random



class BridgeGame(object):
    """
    Creates an instance of a BridgeGame
    which includes all information about the game

    ATTRIBUTES
    players (listof Telegram.User)
    state (int): 0=setup; 1=auction; 2=call; 3=play; 4=scoring

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

    def num_players(self):
        return len(self.players)

    # adds a player to the game if it is not full
    def add_player(self, user, chat_id):
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
                self.start_game()
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

    def add_bot(self, dir=-1, hand=[]):
        if self.num_players() == 4:
            return -1
        newbot = BridgePlayer()
        newbot.give_direction(dir)
        newbot.hand = hand
        self.players.append(newbot)
        self.chat_handler.player_joined_game(newbot, self)
        if self.num_players() == 4:
            self.start_game()
        return 1

    def start_game(self):
        #starts the game
        self.state = 1
        self.chat_handler.starting_game(self)
        #give each player a direction
        dirs = 1
        for p in self.players:
            p.give_direction(dirs)
            dirs += 1
        wash = True
        while wash:
            wash = False
            self.deal_hands()
            for p in self.players:
                if p.hand_score() < 4:
                    wash = True
        self.show_hands()
        # TODO: handle turns for bots
        self.turn = 0
        if not self.curr_player().is_bot:
            self.chat_handler.request_bid(self.curr_player())
        return

    def curr_player(self):
        return self.players[self.turn]

    def next_turn(self):
        self.turn = (self.turn+1) % 4
        if (self.state == 1):
            self.get_next_bid()
        return

    def deal_hands(self):
        # send list of cards to players' hands
        card_nums = range(52)
        random.shuffle(card_nums)
        cards = []
        for id in card_nums:
            cards.append(BridgeCard(id))
        for p in self.players:
            p.hand = []
        for r in range(13):
            self.players[0].hand.append(cards[4*r+0])
            self.players[1].hand.append(cards[4*r+1])
            self.players[2].hand.append(cards[4*r+2])
            self.players[3].hand.append(cards[4*r+3])
        for p in self.players:
            p.hand.sort(key=lambda c: c.id)
        return

    def process_bid(self, bid):
        if bid == -1:
            self.chat_handler.player_passed(self.curr_player(), self)
            self.next_turn()
        elif bid > self.contract:
            self.contract = bid
            self.chat_handler.player_bid(bid, self.curr_player(), self)
            self.next_turn()
        else:
            # TODO: bid invalid. ask for a better bid
            self.chat_handler.request_bid(self.curr_player())
        return

    def get_next_bid(self):
        if not self.curr_player().is_bot:
            self.chat_handler.request_bid(self.players[self.turn])
        else:
            self.curr_player().make_auto_bid(self.contract)
            self.next_turn()
        return

    def show_hands(self):
        for p in self.players:
            self.chat_handler.display_hand(p)
        return

    def get_chat_ids(self):
        chat_ids = []
        for p in self.players:
            if p.chat_id is not None and p.chat_id not in chat_ids:
                chat_ids.append(p.chat_id)
        return chat_ids

    def player_listing(self):
        return ", ".join([p.disp_name() for p in self.players])
