class GameError(Exception):
    """Base class for errors that should be shown to the player who caused them."""


class GameFullError(GameError):
    def __init__(self, message='Could not join: games are currently full.'):
        super().__init__(message)


class AlreadyInGameError(GameError):
    def __init__(self, message='You are already in the game.'):
        super().__init__(message)


class NotInGameError(GameError):
    def __init__(self, message='You are not in a game.'):
        super().__init__(message)


class InvalidBidError(GameError):
    pass


class InvalidPlayError(GameError):
    def __init__(self, message, legal_cards=None):
        super().__init__(message)
        self.legal_cards = legal_cards or []
