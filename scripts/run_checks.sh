#!/usr/bin/env bash
set -euo pipefail

ruff check sgbridgebot/ChatBot.py sgbridgebot/ChatHandler.py sgbridgebot/BridgeGame.py sgbridgebot/CommandUtils.py tests
mypy
pytest -q
