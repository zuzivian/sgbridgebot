from telegram.ext import Updater, CommandHandler
from telegram import User, Chat
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
    def __init__(self, num_bots=0):
        self.id = uuid.uuid1()
        self.state = 0
        self.players = []
        self.player_chat_ids = []
        self.num_bots = num_bots
        self.hands = []
        self.turn = 0 #1=,2,3,4 or 0 for nobody

    def num_players(self):
        return self.num_bots + len(self.players)

    # adds a player to the game if it is not full
    def add_player(self, player, chat_id):
        if not isinstance(player, User) or not isinstance(chat_id, int):
            raise TypeError
        elif self.num_players() == 4 or self.state != 0:
            return -1
        elif player in self.players:
            return -2
        else:
            self.players.append(player)
            self.player_chat_ids.append(chat_id)
            if self.num_players() == 4:
                # if room is full, get the game started
                self.start_game()
            return self

    # removes a player from the game
    def remove_player(self, player, chat_id):
        if not isinstance(player, User) or not isinstance(chat_id, int):
            raise TypeError
        elif player not in self.players:
            return -1
        else:
            self.players.remove(player)
            self.player_chat_ids.remove(chat_id)
            return self

    def add_bot(self):
        if self.num_players() == 4:
            return -1
        self.num_bots += 1
        if self.num_players() == 4:
            start_game()
        return 1

    def start_game(self):
        #starts the game
        self.state = 1
        self.deal_hands()
        return

    def deal_hands(self):
        # send list of cards to players' hands
        card_nums = random.shuffle(range(52))
        cards = []
        self.hands = [[], [], [], []]
        for id in card_nums:
            cards.append(BridgeCard(id))
        for r in range(0,12):
            self.hands[0].append(cards[4*r+0])
            self.hands[1].append(cards[4*r+1])
            self.hands[2].append(cards[4*r+2])
            self.hands[3].append(cards[4*r+3])
        return

    # player utility. should move to Player object in future
    def player_name(self, player):
        return player.username if player.username else player.first_name

    def player_listing(self):
        return ", ".join([self.player_name(p) for p in self.players])
