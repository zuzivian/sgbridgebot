# sgBridge CHANGELOG
See README for further details about this project.

## How to maintain this changelog
Add a section here for every commit that is made, in the following format: major.minor.patch+release[: build YYMMDD/HHMM]

Build numbers are included in the alpha stage of development, and will be dropped eventually. For now time is in UTC+5.

## 0.0.6-alpha: build 180602/1841
Upgraded to python 3.6
+ players can now play a full game
+ implemented trick winning logic
+ implemented game winning logic based on contract
+ cards now shown on an inline keyboard - players can select card to play
- have yet to implement card checking
- bots do not choose cards well


## 0.0.5-alpha: build 180602/0135
Implemented partner choice
+ Players can choose their partner using inline keyboard
- Bug: card values not displaying properly sometimes

## 0.0.5-alpha: build 180601/0221
Fully implemented bidding system
+ bots can now choose their partner
+ bots now randomly choose a bid
+ one pass around ends bidding phase

## 0.0.4-alpha: build 180531/2216
Partially implemented bidding system
+ Using keyboard markup to provide bidding options
+ Full support for bots
+ Handles rouge bids gracefully

## 0.0.3-alpha: build 180531/0304
Begin forming main game components
+ Added playable hands and cards
+ Full games (4/4 players) transition to dealing phase
+ Added ability to shuffle and deal deck of cards
+ Some support for adding bots to games

## 0.0.2-alpha: build 180526/1913
Cleaning. Reorganized code on main script into chunks
+ CommandUtils now holds all command handler functions
+ ChatBot object created, acts as an wrapper for all bot elements

## 0.0.2-alpha: build 180526/0328
+ Added support for bot players

## 0.0.1-alpha: build 180525/1513
Initial commit.
+ Created /join command handler
+ Created /leave command handler
+ Created /hello command handler
+ Simple lobby for 4 players
