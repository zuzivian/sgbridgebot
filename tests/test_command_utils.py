import asyncio
from types import SimpleNamespace
from unittest import mock

from telegram import User

from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.ChatHandler import ChatHandler
from sgbridgebot.CommandUtils import NOT_IN_GAME, CommandUtils
from sgbridgebot.GameManager import GameManager
from sgbridgebot.game_types import GameState, GameType

GROUP_ID = -500


class RecordingChat(ChatHandler):
    """The real ChatHandler, with Telegram calls recorded instead of sent."""

    def __init__(self):
        super().__init__(bot=None)
        self.sent = []
        self.edited = []
        self.removed = []

    async def send_message(self, chat_id, message, parse_mode=None, reply_markup=None):
        self.sent.append((chat_id, message, reply_markup))
        return SimpleNamespace(message_id=len(self.sent))

    async def edit_message_text(self, text, chat_id, message_id, parse_mode=None,
                                reply_markup=None):
        self.edited.append((chat_id, message_id, text, reply_markup))

    async def remove_keyboard(self, chat_id, message_id):
        self.removed.append((chat_id, message_id))

    def texts_to(self, chat_id):
        return [text for cid, text, _ in self.sent if cid == chat_id]


def make_user(user_id, username=None):
    return User(id=user_id, is_bot=False, first_name=f"P{user_id}", username=username or f"u{user_id}")


def message_update(user, chat_id, chat_type, text=""):
    message = SimpleNamespace(from_user=user, text=text, message_id=1, replies=[])

    async def reply_text(reply):
        message.replies.append(reply)

    message.reply_text = reply_text
    return SimpleNamespace(message=message, effective_chat=SimpleNamespace(id=chat_id, type=chat_type))


def callback_update(user, data, chat_id=1, message_id=1):
    query = SimpleNamespace(
        data=data,
        from_user=user,
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=message_id),
        answer=mock.AsyncMock(),
    )
    return SimpleNamespace(callback_query=query)


def answer_text(update):
    call = update.callback_query.answer.await_args
    if call is None:
        return None
    return call.args[0] if call.args else call.kwargs.get("text")


async def started(game_type=GameType.MATCHMAKING):
    chat = RecordingChat()
    manager = GameManager(chat, bot_pause=0)
    utils = CommandUtils(manager, chat)
    users = [make_user(i + 1) for i in range(4)]
    for user in users:
        chat_id = GROUP_ID if game_type == GameType.GROUP else user.id
        chat_type = "group" if game_type == GameType.GROUP else "private"
        await utils.join(message_update(user, chat_id, chat_type, "/join"), None)
    return utils, manager, chat, users, manager.active_games[0]


def run(coro):
    return asyncio.run(coro)


def test_join_twice_reports_already_in_game():
    async def scenario():
        chat = RecordingChat()
        utils = CommandUtils(GameManager(chat), chat)
        update = message_update(make_user(1), 1, "private", "/join")
        await utils.join(update, None)
        await utils.join(update, None)
        return update

    update = run(scenario())
    assert update.message.replies == ["You are already in the game."]


def test_leave_when_not_in_game():
    chat = RecordingChat()
    utils = CommandUtils(GameManager(chat), chat)
    update = message_update(make_user(1), 1, "private", "/leave")

    run(utils.leave(update, None))

    assert update.message.replies == ["You are already not in the game."]


def test_leave_on_own_turn_hands_seat_to_bot_that_moves():
    async def scenario():
        utils, manager, chat, users, game = await started(GameType.GROUP)
        seat, seq = game.turn, game.action_seq
        quitter = users[seat]
        update = message_update(quitter, GROUP_ID, "group", "/leave")
        await utils.leave(update, None)
        return game, seat, seq, update

    game, seat, seq, update = run(scenario())
    assert game.players[seat].is_bot
    assert game.players[seat].disp_name() == "u1 (bot)"
    assert game.action_seq > seq  # the bot made its bid
    assert not game.curr_player().is_bot
    assert update.message.replies == ["You left the game."]


def test_forcestart_fills_lobby_with_bots():
    async def scenario():
        chat = RecordingChat()
        manager = GameManager(chat, bot_pause=0)
        utils = CommandUtils(manager, chat)
        user = make_user(1)
        await utils.join(message_update(user, GROUP_ID, "group", "/join"), None)
        await utils.forcestart(message_update(user, GROUP_ID, "group", "/forcestart"), None)
        again = message_update(user, GROUP_ID, "group", "/forcestart")
        await utils.forcestart(again, None)
        return manager, again

    manager, again = run(scenario())
    game = manager.active_games[0]
    assert [p.is_bot for p in game.players] == [False, True, True, True]
    assert game.state == GameState.AUCTION
    assert again.message.replies == ["Game already started!"]


def test_hand_in_group_asks_for_private_chat_and_in_private_shows_hand():
    async def scenario():
        utils, manager, chat, users, game = await started(GameType.GROUP)
        before = len(chat.sent)
        await utils.hand(message_update(users[0], GROUP_ID, "group", "/hand"), None)
        group_reply = chat.sent[before:]
        await utils.hand(message_update(users[0], users[0].id, "private", "/hand"), None)
        return chat, users, group_reply

    chat, users, group_reply = run(scenario())
    assert "Open a private chat" in group_reply[0][1]
    assert any("following cards in your hand" in t for t in chat.texts_to(users[0].id))


def test_hand_when_only_in_lobby():
    async def scenario():
        chat = RecordingChat()
        utils = CommandUtils(GameManager(chat), chat)
        user = make_user(1)
        await utils.join(message_update(user, 1, "private", "/join"), None)
        update = message_update(user, 1, "private", "/hand")
        await utils.hand(update, None)
        return update

    update = run(scenario())
    assert update.message.replies == [
        "You are in a game lobby. Wait for the game to start, then use /hand in a private chat."
    ]


def test_group_text_from_bystander_is_ignored_but_private_text_gets_a_hint():
    async def scenario():
        utils, manager, chat, users, game = await started(GameType.GROUP)
        bystander = make_user(99)
        before = len(chat.sent)
        in_group = [message_update(bystander, GROUP_ID, "group", text) for text in ("A", "S", "SA")]
        for update in in_group:
            await utils.card(update, None)
        typed_pass = message_update(bystander, GROUP_ID, "group", "pass")
        await utils.bidding(typed_pass, None)
        in_group.append(typed_pass)
        private = message_update(bystander, bystander.id, "private", "1NT")
        await utils.bidding(private, None)
        return chat, before, in_group, private

    chat, before, in_group, private = run(scenario())
    assert len(chat.sent) == before
    assert all(update.message.replies == [] for update in in_group)
    assert private.message.replies == [NOT_IN_GAME]


def test_text_bid_out_of_turn_and_too_low():
    async def scenario():
        utils, manager, chat, users, game = await started()
        out_of_turn = message_update(users[1], users[1].id, "private", "1C")
        await utils.bidding(out_of_turn, None)
        await utils.bidding(message_update(users[0], users[0].id, "private", "2H"), None)
        too_low = message_update(users[1], users[1].id, "private", "1NT")
        await utils.bidding(too_low, None)
        return game, out_of_turn, too_low

    game, out_of_turn, too_low = run(scenario())
    assert out_of_turn.message.replies == ["You cannot bid right now. Wait for your turn."]
    assert game.contract == 7
    assert too_low.message.replies == ["You must bid higher than 2❤, or pass."]


def test_text_partner_call_in_two_steps_accepts_heart_variation_selector():
    async def scenario():
        utils, manager, chat, users, game = await started()
        game.state = GameState.PARTNER_CALL
        game.contract = 0
        player = game.curr_player()
        user = next(u for u in users if u.id == player.id)
        await utils.card(message_update(user, user.id, "private", "♥️"), None)
        suit_choice = game.partner_suit_choice
        await utils.card(message_update(user, user.id, "private", "A"), None)
        return game, suit_choice

    game, suit_choice = run(scenario())
    assert suit_choice == 2
    assert game.partner_card.id == 38
    assert game.state == GameState.PLAY


def test_text_card_that_does_not_follow_suit_lists_legal_cards():
    async def scenario():
        utils, manager, chat, users, game = await started()
        game.state = GameState.PLAY
        game.contract = 4  # 1NT
        game.declarer = game.partner = game.players[0]
        game.partner_card = BridgeCard(51)
        game.trick_start = 0
        player = game.players[0]
        player.hand = [BridgeCard(0), BridgeCard(13)]
        game.trick = [BridgeCard(1)]
        game.trick_start = 3
        game.turn = 0
        update = message_update(users[0], users[0].id, "private", "♦2")
        await utils.card(update, None)
        return update, chat, users

    update, chat, users = run(scenario())
    assert update.message.replies == [
        "Invalid card! You must follow suit (♣). Legal options: ♣2."
    ]
    assert "your turn to play" in chat.texts_to(users[0].id)[-1]


def test_callback_bid_removes_keyboard_and_records_bid():
    async def scenario():
        utils, manager, chat, users, game = await started()
        update = callback_update(users[0], f"b:{game.short_id}:{game.action_seq}:2", chat_id=1, message_id=7)
        await utils.callback(update, None)
        return game, chat, update

    game, chat, update = run(scenario())
    assert game.contract == 2
    assert (1, 7) in chat.removed
    update.callback_query.answer.assert_awaited()


def test_callback_refuses_other_players_stale_prompts_and_ended_games():
    async def scenario():
        utils, manager, chat, users, game = await started()
        wrong_user = callback_update(users[1], f"b:{game.short_id}:{game.action_seq}:2")
        await utils.callback(wrong_user, None)
        stale = callback_update(users[0], f"b:{game.short_id}:{game.action_seq + 5}:2")
        await utils.callback(stale, None)
        ended = callback_update(users[0], "b:deadbeef:0:2")
        await utils.callback(ended, None)
        return game, wrong_user, stale, ended

    game, wrong_user, stale, ended = run(scenario())
    assert answer_text(wrong_user) == "It's u1's turn, not yours."
    assert answer_text(stale) == "This prompt has expired."
    assert answer_text(ended) == "This game has ended."
    assert game.contract == -1


def test_callback_partner_suit_then_rank():
    async def scenario():
        utils, manager, chat, users, game = await started()
        game.state = GameState.PARTNER_CALL
        game.contract = 0
        user = next(u for u in users if u.id == game.curr_player().id)
        seq = game.action_seq
        await utils.callback(callback_update(user, f"ps:{game.short_id}:{seq}:3"), None)
        rank_markup = chat.edited[-1][3]
        await utils.callback(callback_update(user, f"pc:{game.short_id}:{seq}:51"), None)
        return game, rank_markup

    game, rank_markup = run(scenario())
    labels = [b.text for row in rank_markup.inline_keyboard for b in row]
    assert labels[:2] == ["♠A", "♠K"] and labels[-1] == "« Back to suits"
    assert game.partner_card.id == 51
    assert game.state == GameState.PLAY


def test_callback_illegal_card_shows_alert_with_legal_cards():
    async def scenario():
        utils, manager, chat, users, game = await started()
        game.state = GameState.PLAY
        game.contract = 0  # clubs are trump
        game.declarer = game.partner = game.players[0]
        game.partner_card = BridgeCard(51)
        game.turn = 0
        game.trick = []
        game.trick_start = 0
        game.players[0].hand = [BridgeCard(0), BridgeCard(13)]
        update = callback_update(users[0], f"c:{game.short_id}:{game.action_seq}:0")
        await utils.callback(update, None)
        return game, update

    game, update = run(scenario())
    call = update.callback_query.answer.await_args
    assert call.kwargs["show_alert"] is True
    assert call.args[0] == "Invalid card! Trump (♣) is not broken yet. Legal options: ♦2."
    assert game.trick == []


def test_start_and_help_commands_return_guidance_text():
    chat = RecordingChat()
    utils = CommandUtils(GameManager(chat), chat)
    start = message_update(make_user(1), 1, "private", "/start")
    help_update = message_update(make_user(1), 1, "private", "/help")

    run(utils.start(start, None))
    run(utils.help(help_update, None))

    assert "Quick start" in start.message.replies[0]
    assert "Commands" in help_update.message.replies[0]


async def _finish_hand(game, declarer_tricks=7):
    game.state = GameState.PLAY
    game.contract = 0
    game.declarer = game.players[0]
    game.partner = game.players[2]
    game.partner_card = game.players[2].hand[0]
    game.declarer.tricks_won = declarer_tricks
    game.players[1].tricks_won = 13 - declarer_tricks
    game.tricks_played = 13
    async with game.lock:
        await game.end_game()


def test_finished_hand_offers_deal_again_and_keeps_table_score():
    async def scenario():
        utils, manager, chat, users, game = await started()
        await _finish_hand(game)
        recap = chat.sent[-1]
        taps = []
        for user in users:
            update = callback_update(user, f"r:{game.short_id}:0")
            await utils.callback(update, None)
            taps.append(update)
        return manager, game, recap, taps

    manager, old_game, recap, taps = run(scenario())
    _, text, markup = recap
    assert "made 1♣: 7 of the 7 required tricks" in text
    assert "Hands won at this table (1 hand)" in text
    assert [b.text for row in markup.inline_keyboard for b in row] == ["🔁 Deal again"]
    assert all(answer_text(t) == "You are back at the table." for t in taps)
    new_game = manager.active_games[0]
    assert new_game is not old_game
    assert new_game.hands_played == 1
    assert new_game.match_scores == {1: 1, 2: 0, 3: 1, 4: 0}
    assert {p.id for p in new_game.players} == {1, 2, 3, 4}


def test_deal_again_refuses_strangers_repeats_and_closed_tables():
    async def scenario():
        utils, manager, chat, users, game = await started()
        await _finish_hand(game, declarer_tricks=3)
        first = callback_update(users[0], f"r:{game.short_id}:0")
        await utils.callback(first, None)
        again = callback_update(users[0], f"r:{game.short_id}:0")
        await utils.callback(again, None)
        stranger = callback_update(make_user(99), f"r:{game.short_id}:0")
        await utils.callback(stranger, None)
        closed = callback_update(users[1], "r:deadbeef:0")
        await utils.callback(closed, None)
        return manager, again, stranger, closed

    manager, again, stranger, closed = run(scenario())
    assert answer_text(again) == "You are already back at the table."
    assert answer_text(stranger) == "Only players from that table can deal again."
    assert "closed" in answer_text(closed)
    assert len(manager.waiting_games) == 1


def test_deal_again_with_bots_starts_when_the_only_human_returns():
    async def scenario():
        chat = RecordingChat()
        manager = GameManager(chat, bot_pause=0)
        utils = CommandUtils(manager, chat)
        user = make_user(1)
        await utils.join(message_update(user, GROUP_ID, "group", "/join"), None)
        await utils.forcestart(message_update(user, GROUP_ID, "group", "/forcestart"), None)
        game = manager.active_games[0]
        await _finish_hand(game)
        await utils.callback(callback_update(user, f"r:{game.short_id}:0"), None)
        return manager

    manager = run(scenario())
    assert len(manager.active_games) == 1
    assert sum(p.is_bot for p in manager.active_games[0].players) == 3


def test_wash_by_button_and_by_text(monkeypatch):
    monkeypatch.setattr("sgbridgebot.BridgePlayer.BridgePlayer.hand_score", lambda self, hand: 3)

    async def scenario():
        utils, manager, chat, users, game = await started()
        markup = chat.sent[-1][2]
        seq = game.action_seq
        await utils.callback(callback_update(users[0], f"w:{game.short_id}:{seq}"), None)
        # Seat 0 deals again and may wash again; East may not wash out of turn.
        typed = message_update(users[1], users[1].id, "private", "wash")
        await utils.wash(typed, None)
        return chat, markup, game, seq, typed

    chat, markup, game, seq, typed = run(scenario())
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert "🔄 Wash" in labels
    assert any("called a wash with 3 point(s)" in text for _, text, _ in chat.sent)
    assert game.action_seq > seq
    assert "only call a wash" in typed.message.replies[0]


def test_stats_and_leaderboard_commands():
    from sgbridgebot.stats import StatsStore

    async def scenario():
        utils, manager, chat, users, game = await started()
        manager.stats = StatsStore()
        empty = message_update(users[0], users[0].id, "private", "/stats")
        await utils.stats(empty, None)
        for _ in range(3):
            await _finish_hand(game)
            for user in users:
                await utils.callback(callback_update(user, f"r:{game.short_id}:0"), None)
            game = manager.active_games[0]
        mine = message_update(users[0], users[0].id, "private", "/stats")
        await utils.stats(mine, None)
        board = message_update(users[1], users[1].id, "private", "/leaderboard")
        await utils.leaderboard(board, None)
        return empty, mine, board

    empty, mine, board = run(scenario())
    assert "No finished hands yet" in empty.message.replies[0]
    assert "u1: 3 of 3 hands won (100%)" in mine.message.replies[0]
    assert "3/3 contracts made as declarer" in mine.message.replies[0]
    assert "Leaderboard for everyone" in board.message.replies[0]
    assert "🥇" in board.message.replies[0]
