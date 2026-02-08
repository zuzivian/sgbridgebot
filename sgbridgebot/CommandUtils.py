from telegram.error import TimedOut
from sgbridgebot.BridgeGame import BridgeGame
from sgbridgebot.BridgeCard import BridgeCard
import asyncio
from sgbridgebot.game_types import GameState


class CommandUtils(object):
    def __init__(self, manager, chat_handler):
        self.manager = manager
        self.chat = chat_handler

    async def reply_text(self, update, message):
        while True:
            try:
                await update.message.reply_text(message)
            except TimedOut:
                await asyncio.sleep(0.5)
                continue
            break

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
        for game in self.manager.active_games:
            for player in game.players:
                if player.id == user.id:
                    if update.effective_chat.type != 'private':
                        await self.chat.ask_private_chat(game)
                        return
                    await self.chat.display_game_players(chat_id, game)
                    await self.chat.display_hand(player, chat_id)

    async def bidding(self, update, context):
        user = update.message.from_user
        game = self.manager.find_game(user, update.effective_chat.id)
        bid_id = self.chat.str_utils.bid_str_to_id(update.message.text)
        if isinstance(game, BridgeGame):
            if game.state != GameState.AUCTION or user.id != game.curr_player().id:
                await self.reply_text(update, 'You cannot bid at this time!')
                return
            await game.process_bid(bid_id)

    async def card(self, update, context):
        user = update.message.from_user
        game = self.manager.find_game(user, update.effective_chat.id)
        card_id = self.chat.str_utils.card_str_to_id(update.message.text)
        if isinstance(game, BridgeGame):
            if game.state == GameState.PARTNER_CALL and user.id == game.curr_player().id:
                game.partner = game.player_holding_card(card_id)
                game.partner_card = BridgeCard(card_id)
                await self.chat.partner_chosen(game.curr_player(), card_id, game)
                await game.next_turn()
            elif game.state == GameState.PLAY and user.id == game.curr_player().id:
                card = BridgeCard(card_id)
                if card.id in [c.id for c in game.curr_player().hand] and game.valid_play(card):
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
                    await self.reply_text(update, 'Invalid card!')
                    await self.chat.request_card(game.curr_player(), game)
            else:
                await self.reply_text(update, 'Not you turn to play a card! Current turn: {}'.format(game.curr_player().disp_name()))
