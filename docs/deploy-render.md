# Deploy sgbridgebot on Render (Fallback)

This is a practical **fallback path**. You can run either webhook mode (preferred on Render Web Service) or polling mode (Background Worker).

## Option A: Render Web Service (Webhook mode)

Use this if you want Telegram to call your bot over HTTPS.

### Build command
```bash
pip install -r requirements.txt
```

### Start command
```bash
python sgbridgebot/main.py
```

### Required env vars
- `TELEGRAM_BOT_TOKEN` = token from BotFather
- `WEBHOOK_BASE_URL` = `https://<your-service>.onrender.com`
- `PORT` = injected by Render

### Port binding behavior
- Render sets `$PORT`.
- Bot binds `0.0.0.0:$PORT`.

### Webhook URL setup
Webhook is automatically configured to:

```text
$WEBHOOK_BASE_URL/$TELEGRAM_BOT_TOKEN
```

### Sleeping/uptime notes
- Render free web services may spin down after inactivity.
- Spin-down can delay or interrupt webhook handling.
- Upgrade to a non-sleeping plan for production bot reliability.

---

## Option B: Render Background Worker (Polling mode)

Use this if webhook hosting is inconvenient.

### Build command
```bash
pip install -r requirements.txt
```

### Start command
```bash
python sgbridgebot/localtestbot.py
```

### Required env vars
- `TELEGRAM_BOT_TOKEN` = token from BotFather

### Port binding behavior
- Not applicable for polling mode.
- Polling opens outbound connections to Telegram and does not require inbound HTTP.

### Webhook URL setup
- Not used.
- Ensure no stale webhook is set on your bot (`deleteWebhook`) before switching to polling.

### Sleeping/uptime notes
- Polling requires a process that stays continuously running.
- If worker sleeps/restarts often, updates may be delayed or dropped depending on restart timing.
