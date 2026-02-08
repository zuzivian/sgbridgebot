from enum import IntEnum


class GameState(IntEnum):
    SETUP = 0
    AUCTION = 1
    PARTNER_CALL = 2
    PLAY = 3
    SCORING = 4


class GameType(IntEnum):
    PUBLIC = 0
    PRIVATE = 1


# Backward-compatible aliases for persisted/int usage.
GAME_STATE_SETUP = GameState.SETUP
GAME_STATE_AUCTION = GameState.AUCTION
GAME_STATE_PARTNER_CALL = GameState.PARTNER_CALL
GAME_STATE_PLAY = GameState.PLAY
GAME_STATE_SCORING = GameState.SCORING

GAME_TYPE_PUBLIC = GameType.PUBLIC
GAME_TYPE_PRIVATE = GameType.PRIVATE
