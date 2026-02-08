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
