import logging

from sgbridgebot.ChatHandler import HTML
from sgbridgebot.errors import GameError, InvalidPlayError, NotInGameError
from sgbridgebot.game_types import GameState
from sgbridgebot.retry_utils import retry_on_timeout

logger = logging.getLogger(__name__)

NOT_IN_GAME = 'You are not in an active game. Use /join first.'


class CommandUtils:
    def __init__(self, manager, chat_handler):
        self.manager = manager
        self.chat = chat_handler

    async def reply_text(self, update, message):
        return await retry_on_timeout(
            "reply_text",
            lambda: update.message.reply_text(message),
            chat_id=update.effective_chat.id,
            message_id=getattr(update.message, "message_id", None),
        )

    def _mark_reachable_privately(self, update):
        '''
        A message in a private chat proves the bot can now DM this user.
        '''
        if update.effective_chat.type != 'private':
            return
        user_id = update.message.from_user.id
        for game in self.manager.games_for_user(user_id):
            player = game.get_player(user_id)
            if player is not None:
                player.dm_blocked = False

    async def start(self, update, context):
        self._mark_reachable_privately(update)
        await self.reply_text(
            update,
            (
                "Welcome to sgBridgeBot!\n"
                "Quick start:\n"
                "1) /join in your group chat (or here, to be matched with strangers)\n"
                "2) Wait for 4 players, or /forcestart to fill seats with bots\n"
                "3) Tap the buttons I send you to bid, call a partner and play\n"
                "4) In group games your cards come to this private chat\n\n"
                "Use /help anytime for command and syntax reference."
            ),
        )

    async def help(self, update, context):
        await self.reply_text(
            update,
            (
                "Commands:\n"
                "• /join — join a game lobby\n"
                "• /leave — leave your current game (a bot takes your seat)\n"
                "• /hand — show your hand (private chat only)\n"
                "• /forcestart — fill missing seats with bots\n\n"
                "Tap the buttons to play. You can also type:\n"
                "• Bid: PASS, 1NT, 1♣, 1C\n"
                "• Card: ♣2, ♠A, C10, SA\n"
                "• Partner call: suit first (♣/♦/♥/♠ or C/D/H/S), then rank\n\n"
                "If you take too long, a move is made for you."
            ),
        )

    async def forcestart(self, update, context):
        user = update.message.from_user
        try:
            game = await self.manager.forcestart(user, update.effective_chat.id)
        except NotInGameError as exc:
            await self.reply_text(update, str(exc))
            return
        if game is None:
            await self.reply_text(update, 'Game already started!')

    async def join(self, update, context):
        user = update.message.from_user
        try:
            await self.manager.join_game(user, update.effective_chat)
        except GameError as exc:
            await self.reply_text(update, str(exc))

    async def leave(self, update, context):
        user = update.message.from_user
        try:
            game = await self.manager.leave_game(user, update.effective_chat.id)
        except NotInGameError:
            await self.reply_text(update, 'You are already not in the game.')
            return

        await self.reply_text(update, 'You left the game.')
        await self.chat.player_left_game(user, game)

    async def hand(self, update, context):
        user = update.message.from_user
        chat_id = update.effective_chat.id
        self._mark_reachable_privately(update)

        for game in self.manager.active_games:
            for player in game.players:
                if player.id == user.id:
                    if update.effective_chat.type != 'private':
                        await self.chat.ask_private_chat(game)
                        return
                    await self.chat.display_game_players(chat_id, game)
                    await self.chat.display_hand(player, chat_id)
                    return

        for game in self.manager.waiting_games:
            for player in game.players:
                if player.id == user.id:
                    await self.reply_text(
                        update,
                        (
                            'You are in a game lobby. Wait for the game to start, '
                            'then use /hand in a private chat.'
                        ),
                    )
                    return

        await self.reply_text(update, NOT_IN_GAME)

    async def _find_text_game(self, update):
        '''
        Finds the sender's game for a typed bid or card. In group chats,
        text from people who are not playing is ignored, so ordinary chat
        such as "A" or "pass" gets no reply.
        '''
        user = update.message.from_user
        chat = update.effective_chat
        game = self.manager.find_game_for_user(user.id, chat.id, chat.type)
        if game is None and chat.type == 'private':
            await self.reply_text(update, NOT_IN_GAME)
        return game

    async def bidding(self, update, context):
        game = await self._find_text_game(update)
        if game is None:
            return
        try:
            bid_id = self.chat.str_utils.bid_str_to_id(update.message.text)
        except ValueError as exc:
            await self.reply_text(
                update,
                f'Invalid bid: {exc} Example valid bids: PASS, 1NT, 1♣, 1C.',
            )
            return
        async with game.lock:
            player = game.get_player(update.message.from_user.id)
            if game.state != GameState.AUCTION or player is not game.curr_player():
                await self.reply_text(update, 'You cannot bid right now. Wait for your turn.')
                return
            try:
                await game.make_bid(player, bid_id)
            except GameError as exc:
                await self.reply_text(update, str(exc))

    def _resolve_partner_card_input(self, game, text):
        '''
        Returns a card id, or None after recording a suit choice.
        '''
        str_utils = self.chat.str_utils
        suit_choice = str_utils.normalize_suit_token(text)
        if suit_choice is not None:
            game.partner_suit_choice = str_utils.suit_str.index(suit_choice)
            return None

        if game.partner_suit_choice is not None:
            rank_choice = str_utils.normalize_rank_token(text)
            if rank_choice is not None:
                return str_utils.card_str_to_id(
                    str_utils.suit_str[game.partner_suit_choice] + rank_choice
                )

        return str_utils.card_str_to_id(text)

    async def card(self, update, context):
        game = await self._find_text_game(update)
        if game is None:
            return

        async with game.lock:
            player = game.get_player(update.message.from_user.id)
            if game.state == GameState.PARTNER_CALL and player is game.curr_player():
                try:
                    card_id = self._resolve_partner_card_input(game, update.message.text)
                except ValueError as exc:
                    await self.reply_text(
                        update,
                        f'Invalid partner card selection: {exc} '
                        'Pick suit first (♣/♦/♥/♠), then rank.',
                    )
                    await self.chat.request_partner_choice(player, game)
                    return

                if card_id is None:
                    await self.chat.request_partner_rank(player, game, game.partner_suit_choice)
                    return

                game.note_activity(player)
                await self.chat.clear_prompt(game)
                await game.choose_partner(card_id)
                return

            try:
                card_id = self.chat.str_utils.card_str_to_id(update.message.text)
            except ValueError as exc:
                await self.reply_text(
                    update,
                    f'Invalid card: {exc} Example valid cards: ♣2, ♠A, C10, SA.',
                )
                return

            if game.state == GameState.PLAY and player is game.curr_player():
                try:
                    game.validate_card(player, card_id)
                except InvalidPlayError as exc:
                    await self.reply_text(update, self._invalid_card_message(exc))
                    await self.chat.request_card(player, game)
                    return
                await self.chat.clear_prompt(game)
                await game.play_card(player, card_id)
            elif game.is_in_progress():
                await self.reply_text(
                    update,
                    f'Not your turn to play a card. Current turn: {game.curr_player().disp_name()}',
                )
            else:
                await self.reply_text(update, 'The game has not started yet.')

    def _invalid_card_message(self, exc):
        message = f'Invalid card! {exc}'
        if exc.legal_cards:
            message += f" Legal options: {', '.join(exc.legal_cards)}."
        return message

    async def callback(self, update, context):
        '''
        Handles taps on inline buttons. Button data is action:game:seq[:arg].
        '''
        query = update.callback_query
        parts = (query.data or '').split(':')
        if len(parts) < 3:
            await query.answer()
            return
        action, short_id, seq = parts[0], parts[1], parts[2]
        args = parts[3:]

        game = self.manager.find_game_by_short_id(short_id)
        if game is None or game.state == GameState.SCORING:
            await query.answer('This game has ended.')
            await self._remove_query_keyboard(query, None)
            return

        async with game.lock:
            if not seq.isdigit() or int(seq) != game.action_seq or not game.is_in_progress():
                await query.answer('This prompt has expired.')
                await self._remove_query_keyboard(query, game)
                return
            player = game.curr_player()
            if query.from_user.id != player.id:
                await query.answer(f"It's {player.disp_name()}'s turn, not yours.")
                return
            try:
                await self._handle_action(query, game, player, action, args)
            except InvalidPlayError as exc:
                await query.answer(self._invalid_card_message(exc)[:200], show_alert=True)
            except GameError as exc:
                await query.answer(str(exc)[:200], show_alert=True)
            except (ValueError, IndexError):
                await query.answer('That button is no longer valid.')

    async def _handle_action(self, query, game, player, action, args):
        if action == 'b':
            bid = int(args[0])
            game.validate_bid(bid)
            await self._close_query(query, game)
            await game.make_bid(player, bid)
        elif action in ('ps', 'pb', 'pc'):
            if game.state != GameState.PARTNER_CALL:
                raise InvalidPlayError('You cannot call a partner right now.')
            if action == 'ps':
                suit = int(args[0])
                if not 0 <= suit <= 3:
                    raise ValueError(suit)
                game.partner_suit_choice = suit
                await query.answer()
                await self._edit_query(
                    query,
                    self.chat.partner_rank_prompt_text(player, suit),
                    self.chat.partner_rank_markup(game, suit),
                )
            elif action == 'pb':
                game.partner_suit_choice = None
                await query.answer()
                await self._edit_query(
                    query,
                    self.chat.partner_suit_prompt_text(player, game),
                    self.chat.partner_suit_markup(game),
                )
            else:
                card_id = int(args[0])
                if not 0 <= card_id <= 51:
                    raise ValueError(card_id)
                game.note_activity(player)
                await self._close_query(query, game)
                await game.choose_partner(card_id)
        elif action == 'c':
            card_id = int(args[0])
            if not 0 <= card_id <= 51:
                raise ValueError(card_id)
            game.validate_card(player, card_id)
            await self._close_query(query, game)
            await game.play_card(player, card_id)
        else:
            await query.answer()

    def _query_message_ids(self, query):
        message = getattr(query, 'message', None)
        chat = getattr(message, 'chat', None)
        if message is None or chat is None:
            return None
        return chat.id, message.message_id

    async def _remove_query_keyboard(self, query, game):
        ids = self._query_message_ids(query)
        if ids is None:
            return
        if game is not None and game.last_prompt == ids:
            game.last_prompt = None
        await self.chat.remove_keyboard(*ids)

    async def _close_query(self, query, game):
        await query.answer()
        await self._remove_query_keyboard(query, game)

    async def _edit_query(self, query, text, reply_markup):
        ids = self._query_message_ids(query)
        if ids is None:
            return
        await self.chat.edit_message_text(
            text, ids[0], ids[1], parse_mode=HTML, reply_markup=reply_markup
        )
