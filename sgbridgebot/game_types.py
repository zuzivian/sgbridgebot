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

# Backward-compatible aliases for persisted/int usage.
GAME_STATE_SETUP = GameState.SETUP
GAME_STATE_AUCTION = GameState.AUCTION
GAME_STATE_PARTNER_CALL = GameState.PARTNER_CALL
GAME_STATE_PLAY = GameState.PLAY
GAME_STATE_SCORING = GameState.SCORING

GAME_TYPE_PUBLIC = GameType.MATCHMAKING
GAME_TYPE_PRIVATE = GameType.GROUP
