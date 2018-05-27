# sgBridge changelog
### Author: Nathaniel Wong
See README for further details about this project.

## How to maintain this changelog
major.minor.patch-release[: build YYMMDD/HHMM]

Build numbers are included in the alpha stage of development. Time in UTC-5

## 0.0.3-alpha: build 180526/1905
Cleaning. Reorganized code on main script into chunks
- CommandUtils now holds all command handler functions
- ChatBot object created, acts as an wrapper for all bot elements

## 0.0.2-alpha: build 180526/0328
- Created BridgeGame and GameManager classes with simple lobby
- Added support for bot players

## 0.0.1-alpha: build 180525/1513
Initial commit.
- Created /join command handler
- Created /leave command handler
- Created /hello command handler
- Simple lobby for 4 players
