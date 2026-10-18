from enum import IntEnum


class GameState(IntEnum):
    SETUP = 0
    AUCTION = 1
    PARTNER_CALL = 2
    PLAY = 3
    SCORING = 4


class GameType(IntEnum):
    # Strangers matched through private chats with the bot.
    MATCHMAKING = 0
    # Friends playing together inside one group chat.
    GROUP = 1


IN_PROGRESS_STATES = (GameState.AUCTION, GameState.PARTNER_CALL, GameState.PLAY)
