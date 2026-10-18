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
python -m sgbridgebot.main
```

## 2) Configure environment variables
Set these env vars in Koyeb:

- `TELEGRAM_BOT_TOKEN` = token from BotFather (**required**)
- `WEBHOOK_BASE_URL` = the public URL Telegram should call. Use the custom domain once it is verified (see section 6), e.g. `https://bridge.natwong.dev`. Before that, use the Koyeb app URL, e.g. `https://your-app-name.koyeb.app`. If unset, the bot falls back to Koyeb's `KOYEB_PUBLIC_DOMAIN`.
- `PORT` = provided by Koyeb runtime (**do not hardcode**; setting `PORT=80` will fail because the app runs as non-root)

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

## 6) Serve the bot from a natwong.dev subdomain

The bot keeps running on Koyeb. Only its public hostname moves to natwong.dev,
for example `bridge.natwong.dev`. natwong.dev itself stays on Vercel; a CNAME
for one subdomain doesn't affect the main site.

Why not run the bot on Vercel itself: Vercel runs Python as serverless
functions. Each update can land on a different, short-lived instance, so the
in-memory games (`GameManager`), per-table locks, and the turn timer and bot
moves (`asyncio` tasks in `BridgeGame`) would not survive between messages.
Moving to Vercel would mean an external state store and a queue for timers.

### Steps

1. **Koyeb:** open the app -> **Domains** -> **Add domain** -> enter
   `bridge.natwong.dev`. Koyeb shows a CNAME target for the record.
2. **DNS:** add that record wherever natwong.dev's DNS is hosted.
   - If natwong.dev uses Vercel's nameservers: Vercel dashboard -> **Domains**
     -> `natwong.dev` -> **DNS Records** -> add type `CNAME`, name `bridge`,
     value = the Koyeb target. CLI equivalent:
     `vercel dns add natwong.dev bridge CNAME <koyeb-target>`.
   - Otherwise, add the same CNAME at the registrar or DNS provider.
   - Don't add `bridge` as a domain on the Vercel project. That would route
     it to the website instead of to Koyeb.
3. **Wait for Koyeb to show the domain as active** (it issues the TLS
   certificate). Check with `curl -sI https://bridge.natwong.dev/` and confirm a
   valid TLS handshake. Any HTTP status is fine, because the only route is the token path.
4. **Switch the webhook:** in Koyeb, set
   `WEBHOOK_BASE_URL=https://bridge.natwong.dev` and redeploy. On startup the
   bot calls `setWebhook` with `https://bridge.natwong.dev/<token>`, replacing
   the old `koyeb.app` URL. No manual Telegram call is needed.
5. **Verify:** check that `getWebhookInfo` reports the new URL and no
   `last_error_message`:
   `curl -s https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo`.
   Then send `/help` to the bot.

Rollback: set `WEBHOOK_BASE_URL` back to the `koyeb.app` URL, or unset it so
the bot uses `KOYEB_PUBLIC_DOMAIN`, and redeploy.

The same steps work on any always-on host that gives you a CNAME target and
issues TLS for custom domains (Fly.io, Railway, Render).
