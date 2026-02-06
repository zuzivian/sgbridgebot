# Deploy sgbridgebot on Koyeb (Recommended)

This is the **recommended path** for this project because it supports a stable HTTPS endpoint and always-on web services, which are required for Telegram **webhook mode**.

## Why this path
- Telegram webhooks require a public **HTTPS** URL.
- Koyeb web services expose stable HTTPS URLs and bind to the `$PORT` runtime variable.
- The bot already starts a webhook server on `0.0.0.0:$PORT` in `sgbridgebot/main.py` + `sgbridgebot/ChatBot.py`.

## 1) Create the app/service
1. Push this repo to GitHub.
2. In Koyeb, create a **Web Service** from the GitHub repo.
3. Use these commands:

### Build command
```bash
pip install -r requirements.txt
```

### Start command
```bash
python sgbridgebot/main.py
```

## 2) Configure environment variables
Set these env vars in Koyeb:

- `TELEGRAM_BOT_TOKEN` = token from BotFather (**required**)
- `WEBHOOK_BASE_URL` = your Koyeb app URL, e.g. `https://your-app-name.koyeb.app` (**required for production webhook routing**)
- `PORT` = provided by Koyeb runtime (do not hardcode unless needed)

## 3) Port binding behavior
- Koyeb injects `PORT`.
- The bot listens on `0.0.0.0:$PORT`.
- This matches Telegram webhook requirements when behind Koyeb’s HTTPS edge.

## 4) Webhook URL setup
The bot sets webhook to:

```text
$WEBHOOK_BASE_URL/$TELEGRAM_BOT_TOKEN
```

Example:

```text
https://your-app-name.koyeb.app/123456:ABCDEF...
```

No manual `setWebhook` call is required if the app starts successfully.

## 5) Sleeping/uptime notes
- Use an always-on web service tier for reliable webhook delivery.
- If the instance sleeps or scales to zero, Telegram webhook deliveries may fail/retry and user experience degrades.
- For bots, avoid free tiers that aggressively sleep.
