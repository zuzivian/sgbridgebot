A Telegram bot that allows users to play floating bridge, a variant of bridge
that is commonly played in Singapore.

#### Author: Nathaniel Wong | Version: 0.1.3-alpha


# Introduction

This project is under heavy development. sgBridgeBot allows users to play bridge
games with each other via the Telegram Bot API.
The bot allows games to be played by an online  per group chat.


# Rules of the Game

See this wiki page for a general idea of the ruleset:
https://en.wikipedia.org/wiki/Singaporean_bridge


# Try the bot

Link to telegram bot: http://t.me/sgbridgebot

# Features

+ Game management system that is able to handle concurrent game sessions
+ Players able to leave or join games at will
+ Game starts when 4 players join a game lobby
+ Game will proceed in turn-based fashion, with an idle timer of 30s
+ Players will be dealt a hand of 13 cards at random
+ Players will use buttons to select their bid or pass
+ Players will be able to select a card (using buttons) to call a partner
+ Players will use buttons to play a card when it is their turn
+ Chatbot will only allow valid cards to be played
+ Game ends when a partnership wins or a player leaves
+ When game ends, players are kicked and are free to join a new game

Please see the wiki for more information about the bot's planned features: https://github.com/zuzivian/sgbridgebot/wiki/


# MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
