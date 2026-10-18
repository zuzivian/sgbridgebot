import asyncio

from tools import benchmark


def test_bot_only_games_finish_with_legal_moves():
    # CheckedBot raises IllegalBotMove on any bid or card that breaks the rules.
    report = asyncio.run(benchmark.run_benchmark(games=40, seed=3))

    assert report.games == 40
    assert 0 < report.made <= 40
    assert sum(report.levels.values()) == 40
    assert "Contracts made" in report.summary()
