import asyncio

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
