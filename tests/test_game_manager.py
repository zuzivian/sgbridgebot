import asyncio

from sgbridgebot.BridgeGame import BridgeGame
from sgbridgebot.GameManager import GameManager
from sgbridgebot.game_types import GameState, GameType


def test_join_and_leave_lifecycle_in_public_game(mock_handler, make_user):
    manager = GameManager(mock_handler)

    private_chat = type("Chat", (), {"id": 10, "type": "private"})
    game = asyncio.run(manager.join_game(make_user(1, username="u1"), private_chat))

    assert len(manager.waiting_games) == 1
    assert game in manager.waiting_games

    left = asyncio.run(manager.leave_game(make_user(1, username="u1"), private_chat.id))
    assert left is game
    assert len(manager.waiting_games) == 0


def test_waiting_game_moves_to_active_when_four_players_join(mock_handler, make_user):
    manager = GameManager(mock_handler)
    private_chat = type("Chat", (), {"id": 10, "type": "private"})

    for user_id in [1, 2, 3, 4]:
        asyncio.run(manager.join_game(make_user(user_id, username=f"u{user_id}"), private_chat))

    assert len(manager.waiting_games) == 0
    assert len(manager.active_games) == 1
    assert manager.active_games[0].state == GameState.AUCTION


def test_update_gamelists_processes_all_waiting_transitions_without_skipping(mock_handler):
    manager = GameManager(mock_handler)

    # Full waiting game should transition to active.
    full_game = BridgeGame(mock_handler, GameType.MATCHMAKING)
    for idx in range(4):
        full_game.players.append(type("Player", (), {"id": idx + 1, "chat_id": 100, "is_bot": False})())

    # Empty waiting game should be destroyed.
    empty_game = BridgeGame(mock_handler, GameType.MATCHMAKING)

    # Partial waiting game should remain waiting.
    partial_game = BridgeGame(mock_handler, GameType.MATCHMAKING)
    partial_game.players.append(type("Player", (), {"id": 99, "chat_id": 101, "is_bot": False})())

    manager.waiting_games = [full_game, empty_game, partial_game]

    manager.update_gamelists()

    assert full_game in manager.active_games
    assert full_game not in manager.waiting_games
    assert empty_game not in manager.waiting_games
    assert partial_game in manager.waiting_games
    assert len(manager.waiting_games) == 1


def test_update_gamelists_processes_all_active_removals_without_skipping(mock_handler):
    manager = GameManager(mock_handler)

    bot_only_game_1 = BridgeGame(mock_handler, GameType.MATCHMAKING)
    bot_only_game_1.players = [type("Player", (), {"is_bot": True})()]

    bot_only_game_2 = BridgeGame(mock_handler, GameType.MATCHMAKING)
    bot_only_game_2.players = [type("Player", (), {"is_bot": True})()]

    mixed_game = BridgeGame(mock_handler, GameType.MATCHMAKING)
    mixed_game.players = [
        type("Player", (), {"is_bot": True})(),
        type("Player", (), {"is_bot": False})(),
    ]

    manager.active_games = [bot_only_game_1, bot_only_game_2, mixed_game]

    manager.update_gamelists()

    assert bot_only_game_1 not in manager.active_games
    assert bot_only_game_2 not in manager.active_games
    assert mixed_game in manager.active_games
    assert len(manager.active_games) == 1


def test_update_gamelists_transitions_multiple_full_waiting_games_without_skip(mock_handler):
    manager = GameManager(mock_handler)

    full_game_1 = BridgeGame(mock_handler, GameType.MATCHMAKING)
    full_game_2 = BridgeGame(mock_handler, GameType.MATCHMAKING)
    partial_game = BridgeGame(mock_handler, GameType.MATCHMAKING)

    for game, base_chat in ((full_game_1, 500), (full_game_2, 600)):
        game.state = GameState.AUCTION
        game.players = [
            type("Player", (), {"id": idx + 1, "chat_id": base_chat, "is_bot": False})()
            for idx in range(4)
        ]

    partial_game.players = [type("Player", (), {"id": 99, "chat_id": 700, "is_bot": False})()]

    manager.waiting_games = [full_game_1, full_game_2, partial_game]

    manager.update_gamelists()

    assert full_game_1 in manager.active_games
    assert full_game_2 in manager.active_games
    assert partial_game in manager.waiting_games
    assert full_game_1 not in manager.waiting_games
    assert full_game_2 not in manager.waiting_games
    assert len(manager.active_games) == 2
    assert len(manager.waiting_games) == 1


def test_end_game_callback_removes_game_from_active_immediately(mock_handler, make_user):
    manager = GameManager(mock_handler)
    private_chat = type("Chat", (), {"id": 10, "type": "private"})

    for user_id in [1, 2, 3, 4]:
        asyncio.run(manager.join_game(make_user(user_id, username=f"u{user_id}"), private_chat))

    game = manager.active_games[0]
    game.contract = 5
    game.declarer = game.players[0]
    game.partner = game.players[2]
    game.declarer.tricks_won = 5
    game.partner.tricks_won = 3

    asyncio.run(game.end_game())

    assert game not in manager.active_games


def test_join_and_leave_raise_typed_errors(mock_handler, make_user):
    import pytest

    from sgbridgebot.errors import AlreadyInGameError, NotInGameError

    manager = GameManager(mock_handler)
    chat = type("Chat", (), {"id": 10, "type": "private"})
    asyncio.run(manager.join_game(make_user(1), chat))

    with pytest.raises(AlreadyInGameError):
        asyncio.run(manager.join_game(make_user(1), chat))
    with pytest.raises(NotInGameError):
        asyncio.run(manager.leave_game(make_user(2), chat.id))


def test_leaving_active_group_game_while_a_new_lobby_waits_in_same_chat(mock_handler, make_user):
    manager = GameManager(mock_handler, bot_pause=0)
    group = type("Chat", (), {"id": -7, "type": "group"})
    for user_id in [1, 2, 3, 4]:
        asyncio.run(manager.join_game(make_user(user_id, username=f"u{user_id}"), group))
    asyncio.run(manager.join_game(make_user(5, username="u5"), group))
    active = manager.active_games[0]

    left = asyncio.run(manager.leave_game(make_user(2, username="u2"), group.id))

    assert left is active
    assert active.players[1].is_bot
    assert len(manager.waiting_games) == 1
