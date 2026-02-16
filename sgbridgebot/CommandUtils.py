import asyncio

from sgbridgebot.BridgeCard import BridgeCard
from sgbridgebot.BridgeGame import BridgeGame
from sgbridgebot.game_types import GameState
from sgbridgebot.retry_utils import retry_on_timeout


class CommandUtils:
    def __init__(self, manager, chat_handler):
        self.manager = manager
        self.chat = chat_handler
        self.partner_call_suit_selection = {}

    async def reply_text(self, update, message):
        return await retry_on_timeout(
            "reply_text",
            lambda: update.message.reply_text(message),
            chat_id=update.effective_chat.id,
            message_id=getattr(update.message, "message_id", None),
        )

    async def start(self, update, context):
        await self.reply_text(
            update,
            (
                "Welcome to sgBridgeBot!\n"
                "Quick start:\n"
                "1) /join in your group chat\n"
                "2) Wait for 4 players\n"
                "3) DM @sgbridgebot and use /hand\n"
                "4) Bid/play using symbols or aliases (1♣ or 1C, ♠A or SA)\n\n"
                "Use /help anytime for command and syntax reference."
            ),
        )

    async def help(self, update, context):
        await self.reply_text(
            update,
            (
                "Commands:\n"
                "• /join — join a game lobby\n"
                "• /leave — leave your current game\n"
                "• /hand — show your hand (private chat only)\n"
                "• /forcestart — fill missing seats with bots\n\n"
                "Input examples:\n"
                "• Bid: PASS, 1NT, 1♣, 1C\n"
                "• Card: ♣2, ♠A, C10, SA\n"
                "• Partner call: choose suit first (♣/♦/♥/♠ or C/D/H/S), then rank"
            ),
        )

    async def forcestart(self, update, context):
        user = update.message.from_user
        game = self.manager.find_game(user, update.effective_chat.id)
        if not game:
            await self.reply_text(update, 'Please join the game first before starting one!')
            return
        if game.state != GameState.SETUP:
            await self.reply_text(update, 'Game already started!')
            return
        while await game.add_bot() != -1:
            await asyncio.sleep(0.5)
        if game.state == GameState.SETUP:
            await game.start_game()
        self.manager.update_gamelists()

    async def join(self, update, context):
        user = update.message.from_user
        game = await self.manager.join_game(user, update.effective_chat)

        if game == -1:
            await self.reply_text(update, 'Could not join: games are currently full.')
            return
        if game == -2:
            await self.reply_text(update, 'You are already in the game.')
            return
        if not isinstance(game, BridgeGame):
            raise TypeError('GameManager.join_game() did not return a valid BridgeGame object')

        await self.chat.player_joined_game(user, game)

    async def leave(self, update, context):
        user = update.message.from_user
        game = self.manager.leave_game(user, update.effective_chat.id)

        if game == -1:
            await self.reply_text(update, 'You are already not in the game.')
            return
        if not isinstance(game, BridgeGame):
            raise TypeError('GameManager.join_game() did not return a valid BridgeGame object')

        await self.reply_text(update, 'You left the game.')
        await self.chat.player_left_game(user, game)

    async def hand(self, update, context):
        user = update.message.from_user
        chat_id = update.effective_chat.id
        found_active_player = False

        for game in self.manager.active_games:
            for player in game.players:
                if player.id == user.id:
                    found_active_player = True
                    if update.effective_chat.type != 'private':
                        await self.chat.ask_private_chat(game)
                        return
                    await self.chat.display_game_players(chat_id, game)
                    await self.chat.display_hand(player, chat_id)
                    return

        if found_active_player:
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

        await self.reply_text(update, 'You are not in an active game. Use /join first.')

    async def bidding(self, update, context):
        user = update.message.from_user
        game = self.manager.find_game(user, update.effective_chat.id)
        try:
            bid_id = self.chat.str_utils.bid_str_to_id(update.message.text)
        except ValueError as exc:
            await self.reply_text(
                update,
                f'Invalid bid: {exc} Example valid bids: PASS, 1NT, 1♣, 1C.',
            )
            return
        if not isinstance(game, BridgeGame):
            await self.reply_text(update, 'You are not in an active game. Use /join first.')
            return
        if game.state != GameState.AUCTION or user.id != game.curr_player().id:
            await self.reply_text(update, 'You cannot bid right now. Wait for your turn.')
            return
        await game.process_bid(bid_id)

    def _resolve_partner_card_input(self, user, text):
        normalize_suit = getattr(self.chat.str_utils, 'normalize_suit_token', None)
        normalize_rank = getattr(self.chat.str_utils, 'normalize_rank_token', None)

        if callable(normalize_suit):
            suit_choice = normalize_suit(text)
            if suit_choice is not None:
                self.partner_call_suit_selection[user.id] = suit_choice
                return None

        selected_suit = self.partner_call_suit_selection.get(user.id)
        if selected_suit is not None and callable(normalize_rank):
            rank_choice = normalize_rank(text)
            if rank_choice is not None:
                return self.chat.str_utils.card_str_to_id(selected_suit + rank_choice)

        return self.chat.str_utils.card_str_to_id(text)

    async def card(self, update, context):
        user = update.message.from_user
        game = self.manager.find_game(user, update.effective_chat.id)

        if not isinstance(game, BridgeGame):
            await self.reply_text(update, 'You are not in an active game. Use /join first.')
            return

        if game.state == GameState.PARTNER_CALL and user.id == game.curr_player().id:
            try:
                card_id = self._resolve_partner_card_input(user, update.message.text)
            except ValueError as exc:
                await self.reply_text(
                    update,
                    f'Invalid partner card selection: {exc} Pick suit first (♣/♦/♥/♠), then rank.',
                )
                await self.chat.request_partner_choice(game.curr_player())
                return

            if card_id is None:
                suit = self.partner_call_suit_selection[user.id]
                await self.chat.request_partner_rank(game.curr_player(), suit)
                return

            self.partner_call_suit_selection.pop(user.id, None)
            game.partner = game.player_holding_card(card_id)
            game.partner_card = BridgeCard(card_id)
            await self.chat.partner_chosen(game.curr_player(), card_id, game)
            await game.next_turn()
            return

        try:
            card_id = self.chat.str_utils.card_str_to_id(update.message.text)
        except ValueError as exc:
            await self.reply_text(
                update,
                f'Invalid card: {exc} Example valid cards: ♣2, ♠A, C10, SA.',
            )
            return

        if game.state == GameState.PLAY and user.id == game.curr_player().id:
            card = BridgeCard(card_id)
            card_ids_in_hand = [c.id for c in game.curr_player().hand]
            is_valid_play = game.valid_play(card)
            reason, legal_cards = None, []
            if not is_valid_play and hasattr(game, 'valid_play_details'):
                _, reason, legal_cards = game.valid_play_details(card)
            if card.id in card_ids_in_hand and is_valid_play:
                removed_card = game.curr_player().remove_card(card)
                if removed_card is None:
                    await self.reply_text(update, 'Could not play card. Please try again.')
                    await self.chat.request_card(game.curr_player(), game)
                    return
                game.trick.append(removed_card)
                if removed_card.suit == game.get_trump_suit():
                    game.trump_broken = 1
                await self.chat.card_played(game.curr_player(), removed_card, game)
                await game.next_turn()
            else:
                extra = ''
                if reason:
                    extra = f' {reason}'
                if legal_cards:
                    extra += f" Legal options: {', '.join(legal_cards)}."
                await self.reply_text(update, f'Invalid card!{extra}'.strip())
                await self.chat.request_card(game.curr_player(), game)
        else:
            await self.reply_text(
                update,
                f'Not your turn to play a card. Current turn: {game.curr_player().disp_name()}',
            )
