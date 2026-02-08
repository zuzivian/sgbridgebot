A Telegram bot that allows users to play floating bridge, a variant of bridge
that is commonly played in Singapore.

#### Author: Nathaniel Wong | Version: 0.1.5-alpha

Canonical version source: `sgbridgebot/__init__.py` (`__version__`).


# Runtime and dependency compatibility

This project now uses the modern `python-telegram-bot` async handler style
(`Application`, `CommandHandler`, `MessageHandler` with regex filters).

Compatibility target:

+ Python compatibility target: **3.13.x** for deployment (`runtime.txt`) and CI
+ `python-telegram-bot`: **>=21,<22**


# Introduction

This project is under heavy development. sgBridgeBot allows users to play bridge
games with each other via the Telegram Bot API.
The bot allows games to be played by an online  per group chat.


# Rules of the Game

See this wiki page for a general idea of the ruleset:
https://en.wikipedia.org/wiki/Singaporean_bridge


# Try the bot

Link to telegram bot: http://t.me/sgbridgebot

## Running the bot

`sgbridgebot/main.py` supports two startup modes via `BOT_MODE`:

- `webhook` -> runs `bot.start(0)` (recommended default for public web-service deployments)
- `polling` -> runs `bot.start(1)` (recommended for VM/always-on worker setups)

Exact launch commands:

```bash
# Webhook mode (explicit)
BOT_MODE=webhook python3 -m sgbridgebot.main

# Webhook mode (default when BOT_MODE is unset)
python3 -m sgbridgebot.main

# Polling mode
BOT_MODE=polling python3 -m sgbridgebot.main
```

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

# Deployment

Deployment compatibility targets for this codebase:

- Python: **3.13.8** (`runtime.txt`)
- `python-telegram-bot`: **>=21,<22** (`requirements.txt`)

Before starting the bot in production, set the following environment variables:

- `TELEGRAM_BOT_TOKEN`: Telegram bot token used to initialize `ChatBot`.
- `PORT`: Optional webhook listen port. If unset, the bot defaults to `8000`; when running on Koyeb/Render this is typically platform-injected and should not be hardcoded.
- `WEBHOOK_BASE_URL`: Public HTTPS base URL for webhook mode (for example `https://your-app.herokuapp.com`).
  - Optional on Koyeb if `KOYEB_PUBLIC_DOMAIN` is present; the bot will auto-build `https://<KOYEB_PUBLIC_DOMAIN>`.

The webhook URL is constructed at startup as `<resolved_base_url>/<TELEGRAM_BOT_TOKEN>`.

### Koyeb notes

- Do **not** set `WEBHOOK_BASE_URL` to `0.0.0.0`, `127.0.0.1`, or `localhost`. Telegram rejects those with
  `Bad webhook: ip address 0.0.0.0 is reserved`.
- Ensure `BOT_MODE=webhook` for Koyeb Web Services so the process binds the platform-injected `$PORT` and passes TCP health checks.
- You can either set `WEBHOOK_BASE_URL` to your public app URL, or rely on Koyeb's `KOYEB_PUBLIC_DOMAIN`.



## Deployment troubleshooting

If your build fails with:

```
fatal: No url found for submodule path 'python-telegram-bot' in .gitmodules
```

remove any stale git submodule entry named `python-telegram-bot` from the repo index.
This project uses `requirements.txt` for `python-telegram-bot`, so it should not be
tracked as a git submodule.

## GitHub branch protection and required checks

Configure your protected branch (typically `main`) with required status checks so merges are blocked when quality gates fail.

Recommended required checks from the CI workflow:

- `Lint, type-check, and tests (Python 3.13)`
- `Packaging/import smoke (Python 3.13)`

Suggested setup path:

1. GitHub repository **Settings** -> **Branches**.
2. Add/Edit a branch protection rule for `main`.
3. Enable **Require status checks to pass before merging**.
4. Select the two checks above.

