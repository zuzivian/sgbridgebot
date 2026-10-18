import re

from sgbridgebot.ChatBot import _build_input_regexes


def test_partner_call_two_step_tokens_are_accepted():
    bids, cards, partner_tokens, wash = _build_input_regexes()

    assert re.match(cards, '❤A')
    assert re.match(partner_tokens, '❤')
    assert re.match(partner_tokens, 'A')

    assert re.match(bids, '1♣')
    assert not re.match(bids, '❤')


def test_wash_is_typed_in_any_case():
    _, _, _, wash = _build_input_regexes()

    assert re.match(wash, 'wash')
    assert re.match(wash, 'WASH')
    assert not re.match(wash, 'washing')
