'''
benchmark.py

Plays bot-only games through the real BridgeGame engine, with no Telegram
involved, and reports how the bots bid and play. Every card a bot plays is
checked against the rules, so this also works as a fuzz test of the bot AI.

    python -m sgbridgebot.benchmark --games 500 --seed 1
'''

import argparse
import asyncio
import random
from collections import Counter
from dataclasses import dataclass, field

from sgbridgebot.BridgeGame import BridgeGame
from sgbridgebot.BridgePlayer import BridgePlayer
from sgbridgebot.game_types import GameType


class IllegalBotMove(AssertionError):
    pass


class CheckedBot(BridgePlayer):
    '''
    A bot that fails loudly if it ever bids or plays against the rules.
    '''

    def __init__(self, game):
        super().__init__()
        self.game = game

    def make_auto_bid(self, contract):
        bid = super().make_auto_bid(contract)
        if bid != -1 and not contract < bid <= 34:
            raise IllegalBotMove(f'{self.disp_name()} bid {bid} over {contract}')
        return bid

    def play_auto_card(self, trick, game):
        legal = {c.id for c in game.legal_card_objects(self)}
        card = super().play_auto_card(trick, game)
        if card is None or card.id not in legal:
            raise IllegalBotMove(f'{self.disp_name()} played {card!r}, legal: {sorted(legal)}')
        return card


class SimulatedGame(BridgeGame):
    # Real games stop once no humans are left; here bots play every seat.
    def has_humans(self):
        return True


class ResultRecorder:
    '''
    Stands in for ChatHandler: ignores every message except the final result.
    '''

    def __init__(self):
        self.result = None

    async def game_winners(self, team, winners, declarer_tricks, required_tricks, game):
        self.result = (team, declarer_tricks, required_tricks)

    def __getattr__(self, name):
        async def ignore(*args, **kwargs):
            return None
        return ignore


@dataclass
class BenchmarkReport:
    games: int = 0
    made: int = 0
    levels: Counter = field(default_factory=Counter)
    denominations: Counter = field(default_factory=Counter)
    solo_calls: int = 0
    # Declarer-side tricks minus tricks required, summed over games.
    margin_total: int = 0

    @property
    def make_rate(self):
        return self.made / self.games if self.games else 0.0

    def summary(self):
        names = ['♣', '♦', '♥', '♠', 'NT']
        lines = [
            f'Games played: {self.games}',
            f'Contracts made: {self.made} ({self.make_rate:.0%})',
            f'Average margin (tricks over/under target): '
            f'{self.margin_total / max(self.games, 1):+.2f}',
            f'Declarer called their own card: {self.solo_calls}',
            'Contract levels: ' + ', '.join(
                f'{level}: {self.levels[level]}' for level in sorted(self.levels)
            ),
            'Denominations: ' + ', '.join(
                f'{names[d]}: {self.denominations[d]}' for d in sorted(self.denominations)
            ),
        ]
        return '\n'.join(lines)


async def play_one_game():
    recorder = ResultRecorder()
    game = SimulatedGame(recorder, GameType.MATCHMAKING, bot_pause=0)
    game.players = [CheckedBot(game) for _ in range(4)]
    await game.start_game()
    return game, recorder.result


async def run_benchmark(games=200, seed=None):
    if seed is not None:
        random.seed(seed)
    report = BenchmarkReport()
    for _ in range(games):
        game, result = await play_one_game()
        if result is None:
            raise AssertionError('A bot game ended without a result.')
        team, declarer_tricks, required_tricks = result
        report.games += 1
        report.made += team == 0
        report.levels[game.contract // 5 + 1] += 1
        report.denominations[game.contract % 5] += 1
        report.solo_calls += game.partner is game.declarer
        report.margin_total += declarer_tricks - required_tricks
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Benchmark the sgBridgeBot bots.')
    parser.add_argument('--games', type=int, default=200)
    parser.add_argument('--seed', type=int, default=None)
    args = parser.parse_args(argv)
    report = asyncio.run(run_benchmark(args.games, args.seed))
    print(report.summary())


if __name__ == '__main__':
    main()
