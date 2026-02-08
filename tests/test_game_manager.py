import asyncio

from sgbridgebot.BridgeGame import BridgeGame
from sgbridgebot.GameManager import GameManager


def test_join_and_leave_lifecycle_in_public_game(mock_handler, make_user):
    manager = GameManager(mock_handler)

    private_chat = type("Chat", (), {"id": 10, "type": "private"})
    game = asyncio.run(manager.join_game(make_user(1, username="u1"), private_chat))

    assert len(manager.waiting_games) == 1
    assert game in manager.waiting_games

    left = manager.leave_game(make_user(1, username="u1"), private_chat.id)
    assert left is game
    assert len(manager.waiting_games) == 0


def test_waiting_game_moves_to_active_when_four_players_join(mock_handler, make_user):
    manager = GameManager(mock_handler)
    private_chat = type("Chat", (), {"id": 10, "type": "private"})

    for user_id in [1, 2, 3, 4]:
        asyncio.run(manager.join_game(make_user(user_id, username=f"u{user_id}"), private_chat))

    assert len(manager.waiting_games) == 0
    assert len(manager.active_games) == 1
    assert manager.active_games[0].state == 1


def test_update_gamelists_moves_multiple_full_games_without_skipping(mock_handler, make_user):
    manager = GameManager(mock_handler)
    private_chat = type("Chat", (), {"id": 10, "type": "private"})

    for user_id in range(1, 9):
        asyncio.run(manager.join_game(make_user(user_id, username=f"u{user_id}"), private_chat))

    assert len(manager.waiting_games) == 0
    assert len(manager.active_games) == 2
    assert all(g.state == 1 for g in manager.active_games)


def test_update_gamelists_removes_all_empty_waiting_games_without_skipping(mock_handler):
    manager = GameManager(mock_handler)

    empty_1 = manager.create_game(0)
    empty_2 = manager.create_game(0)

    assert empty_1 in manager.waiting_games
    assert empty_2 in manager.waiting_games

    manager.update_gamelists()

    assert manager.waiting_games == []
def test_update_gamelists_processes_all_waiting_transitions_without_skipping(mock_handler, make_user):
    manager = GameManager(mock_handler)

    # Full waiting game should transition to active.
    full_game = BridgeGame(mock_handler, 0)
    for idx in range(4):
        full_game.players.append(type("Player", (), {"id": idx + 1, "chat_id": 100, "is_bot": False})())

    # Empty waiting game should be destroyed.
    empty_game = BridgeGame(mock_handler, 0)

    # Partial waiting game should remain waiting.
    partial_game = BridgeGame(mock_handler, 0)
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

    bot_only_game_1 = BridgeGame(mock_handler, 0)
    bot_only_game_1.players = [type("Player", (), {"is_bot": True})()]

    bot_only_game_2 = BridgeGame(mock_handler, 0)
    bot_only_game_2.players = [type("Player", (), {"is_bot": True})()]

    mixed_game = BridgeGame(mock_handler, 0)
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
