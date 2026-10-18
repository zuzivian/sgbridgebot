'''
stats.py

Keeps finished hands in SQLite so players can see their record (/stats)
and a leaderboard (/leaderboard). Live games still live in memory only.
'''

import logging
import sqlite3
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Players need this many hands before they appear on a leaderboard.
LEADERBOARD_MIN_HANDS = 3

SCHEMA = '''
CREATE TABLE IF NOT EXISTS hands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finished_at REAL NOT NULL,
    game_type INTEGER NOT NULL,
    contract INTEGER NOT NULL,
    declarer_tricks INTEGER NOT NULL,
    required_tricks INTEGER NOT NULL,
    made INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS hand_players (
    hand_id INTEGER NOT NULL REFERENCES hands(id),
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    chat_id INTEGER,
    declarer INTEGER NOT NULL,
    partner INTEGER NOT NULL,
    won INTEGER NOT NULL,
    tricks INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS hand_players_user ON hand_players(user_id);
CREATE INDEX IF NOT EXISTS hand_players_chat ON hand_players(chat_id);
'''


@dataclass
class PlayerStats:
    name: str
    hands: int
    won: int
    declared: int
    declared_made: int
    tricks: int

    @property
    def win_rate(self):
        return self.won / self.hands if self.hands else 0.0


class StatsStore:
    '''
    ARGS
    record_hand(game): stores a scored hand; bots are not recorded
    player_stats(user_id): PlayerStats, or None if they have no hands
    leaderboard(chat_id=None, limit=10): best win rates, in one chat or overall
    '''

    def __init__(self, path=':memory:'):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self):
        self.db.close()

    def record_hand(self, game):
        if game.result is None:
            return
        humans = [p for p in game.final_players if not p.is_bot]
        if not humans:
            return
        team, declarer_tricks, required_tricks = game.result
        with self.db:
            cursor = self.db.execute(
                'INSERT INTO hands (finished_at, game_type, contract, declarer_tricks, '
                'required_tricks, made) VALUES (?, ?, ?, ?, ?, ?)',
                (time.time(), int(game.type), game.contract, declarer_tricks,
                 required_tricks, int(team == 0)),
            )
            hand_id = cursor.lastrowid
            for p in humans:
                on_declarer_side = game.is_declarer_side(p)
                self.db.execute(
                    'INSERT INTO hand_players (hand_id, user_id, name, chat_id, declarer, '
                    'partner, won, tricks) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        hand_id, p.id, p.disp_name(), p.chat_id,
                        int(p is game.declarer),
                        int(p is game.partner and p is not game.declarer),
                        int(on_declarer_side == (team == 0)),
                        p.tricks_won,
                    ),
                )

    def player_stats(self, user_id):
        row = self.db.execute(
            'SELECT (SELECT name FROM hand_players WHERE user_id = ? '
            '        ORDER BY hand_id DESC LIMIT 1), '
            'COUNT(*), SUM(won), SUM(declarer), SUM(declarer * won), SUM(tricks) '
            'FROM hand_players WHERE user_id = ?',
            (user_id, user_id),
        ).fetchone()
        if not row or not row[1]:
            return None
        return PlayerStats(row[0], row[1], row[2], row[3], row[4], row[5])

    def leaderboard(self, chat_id=None, limit=10):
        where = 'WHERE chat_id = ?' if chat_id is not None else ''
        params = (chat_id,) if chat_id is not None else ()
        rows = self.db.execute(
            'SELECT user_id, COUNT(*) AS hands, SUM(won) AS won, SUM(declarer), '
            'SUM(declarer * won), SUM(tricks) '
            f'FROM hand_players {where} GROUP BY user_id HAVING hands >= ? '
            # Aggregates spelled out: "won" alone would mean the column, not SUM(won).
            'ORDER BY CAST(SUM(won) AS REAL) / COUNT(*) DESC, SUM(won) DESC LIMIT ?',
            (*params, LEADERBOARD_MIN_HANDS, limit),
        ).fetchall()
        names = dict(self.db.execute(
            'SELECT user_id, name FROM hand_players h WHERE hand_id = '
            '(SELECT MAX(hand_id) FROM hand_players WHERE user_id = h.user_id)'
        ).fetchall())
        return [
            PlayerStats(names.get(row[0], '?'), row[1], row[2], row[3], row[4], row[5])
            for row in rows
        ]


def open_store(path):
    '''
    Opens the stats database, falling back to memory if the file cannot be used.
    '''
    try:
        return StatsStore(path)
    except sqlite3.Error as exc:
        logger.error('Cannot open stats database %r (%s); keeping stats in memory', path, exc)
        return StatsStore()
