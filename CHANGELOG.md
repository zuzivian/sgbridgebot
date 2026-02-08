# sgBridge CHANGELOG
See README for further details about this project.

## How to maintain this changelog
Add a section here for every commit that is made, in the following format: major.minor.patch[: build YYMMDD/HHMM]

Build numbers are included in the alpha stage of development, and will be dropped eventually. Time is in UTC-5.

Canonical package version is defined in `sgbridgebot/__init__.py` as `__version__`, and release entries should match it.


## 0.1.5-alpha
Python runtime/tooling refresh
+ Standardized project Python targets on 3.13.8 across runtime, local tooling, and CI
+ Replaced multi-version CI matrix with a single latest-stable Python 3.13 checks job
+ Updated packaging smoke check and branch-protection docs to target Python 3.13

## 0.1.4-alpha
Maintenance and deployment hardening
+ Added CI matrix coverage for Python 3.10 and 3.11
+ Added packaging/import smoke check to CI for Python 3.10
+ Aligned README branch protection guidance with actual CI checks
+ Added TODO note to improve bot bidding aggressiveness with strong hands

## 0.1.3-alpha: build 180608/2100
Bug fixes
+ Fixed win conditions when calling ownself as partner

## 0.1.2-alpha: build 180608/2100
Bug and cosmetic fixes
+ Improved bot bidding dice roll
+ Added game information to keyboard

## 0.1.1-alpha: build 180607/1641
Bug fixes
+ Fixed play not being able to break trump
+ Fixed end of game message not displaying if you lost your contract
+ Fixed no trump games starting on wrong player
+ Added temporary pauses between each bot play to avoid spamminess
+ Improved bot player logic

## 0.1-alpha: build 180603/1955
First stable release, soft release on production server for testing
+ chatbot now retries sending message on timeout
+ fixed weird trumping behavior by bot
- does not yet have idle timer

## 0.0.7-alpha: build 180603/0302
Bot intelligence upgraded
+ Bots now play reasonably well (beginning human)
+ Players now must observe game rules (breaking trump etc)
+ Stability improvements and bug fixes
+ Some support for group chats

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
