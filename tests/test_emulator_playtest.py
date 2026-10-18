import asyncio
import random

import pytest

from sgbridgebot import emulator


@pytest.mark.parametrize("scenario", emulator.SCENARIOS, ids=lambda s: s.__name__)
def test_emulated_scenario(scenario):
    asyncio.run(scenario(random.Random(7)))


def test_emulated_random_full_games():
    asyncio.run(emulator.scenario_random_games(random.Random(11), games=6))


def test_fake_telegram_rejects_bad_html():
    with pytest.raises(emulator.ApiError):
        emulator.check_html("a < b")
    with pytest.raises(emulator.ApiError):
        emulator.check_html("<b>unclosed")
    emulator.check_html('<a href="tg://user?id=1">A &amp; B</a> 1 &lt; 2')
