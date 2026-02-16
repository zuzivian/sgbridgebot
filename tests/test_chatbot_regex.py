import re

from sgbridgebot.ChatBot import _build_input_regexes


def test_partner_call_two_step_tokens_are_accepted():
    bids, cards, partner_tokens = _build_input_regexes()

    assert re.match(cards, '❤A')
    assert re.match(partner_tokens, '❤')
    assert re.match(partner_tokens, 'A')

    assert re.match(bids, '1♣')
    assert not re.match(bids, '❤')
