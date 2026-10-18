import asyncio

from sgbridgebot.BridgeGame import BridgeGame
from sgbridgebot.game_types import GameType
from sgbridgebot.stats import LEADERBOARD_MIN_HANDS, StatsStore


def _finished_game(mock_handler, make_user, chat_id=-10, declarer_tricks=8, with_bot=False):
    async def build():
        game = BridgeGame(mock_handler, GameType.GROUP, bot_pause=0)
        for i in range(3 if with_bot else 4):
            await game.add_player(make_user(i + 1, username=f"u{i + 1}"), chat_id)
        if with_bot:
            await game.add_bot()
        game.contract = 0  # 1♣: 7 tricks
        game.declarer = game.players[0]
        game.partner = game.players[2]
        game.declarer.tricks_won = declarer_tricks
        game.players[1].tricks_won = 13 - declarer_tricks
        game.tricks_played = 13
        await game.end_game()
        return game

    return asyncio.run(build())


def test_record_hand_and_player_stats(mock_handler, make_user):
    store = StatsStore()
    store.record_hand(_finished_game(mock_handler, make_user, declarer_tricks=8))
    store.record_hand(_finished_game(mock_handler, make_user, declarer_tricks=3))

    declarer = store.player_stats(1)
    defender = store.player_stats(2)

    assert (declarer.name, declarer.hands, declarer.won) == ("u1", 2, 1)
    assert (declarer.declared, declarer.declared_made) == (2, 1)
    assert declarer.tricks == 11
    assert (defender.won, defender.declared) == (1, 0)
    assert store.player_stats(99) is None


def test_bots_are_not_recorded(mock_handler, make_user):
    store = StatsStore()
    store.record_hand(_finished_game(mock_handler, make_user, with_bot=True))

    rows = store.db.execute("SELECT COUNT(*) FROM hand_players").fetchone()
    assert rows[0] == 3


def test_leaderboard_needs_min_hands_and_can_be_scoped_to_a_chat(mock_handler, make_user):
    store = StatsStore()
    for _ in range(LEADERBOARD_MIN_HANDS - 1):
        store.record_hand(_finished_game(mock_handler, make_user, chat_id=-10))
    assert store.leaderboard() == []

    store.record_hand(_finished_game(mock_handler, make_user, chat_id=-20, declarer_tricks=2))

    overall = store.leaderboard()
    assert len(overall) == 4
    # Declarer side won 2 of 3; defenders 1 of 3.
    assert {row.name for row in overall[:2]} == {"u1", "u3"}
    assert store.leaderboard(chat_id=-10) == []
    assert store.leaderboard(chat_id=-20) == []
