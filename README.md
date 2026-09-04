# TradingView → OpenAI Crypto Long Entry Watch

This project receives a TradingView webhook on each closed 15-minute candle,
runs a profitability-first OpenAI analysis, and optionally sends an alert to Telegram
only when the AI returns an actionable LONG.

## Architecture

TradingView 15m alert
→ HTTPS webhook
→ FastAPI server immediately returns HTTP 202
→ OpenAI Responses API analysis
→ Telegram LONG alert (optional)

The webhook handler acknowledges quickly because TradingView can cancel webhook
requests if the receiver takes too long.

## 1. Install

Python 3.11+ recommended.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` values into your hosting provider's secret/environment settings.

Do NOT put your OpenAI API key inside TradingView or Pine Script.

## 2. Run locally

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

For TradingView, expose it behind an HTTPS domain on port 443 using a hosting service
such as Railway, Render, Fly.io, Cloud Run, or your own reverse proxy.

## 3. TradingView

1. Open the desired crypto chart.
2. Set chart timeframe to **15m**.
3. Open Pine Editor.
4. Paste `tradingview_ai_15m.pine`.
5. Add it to chart.
6. Create Alert.
7. Condition: **AI Crypto 15m Webhook Feed → Any alert() function call**
8. Frequency: **Once Per Bar Close**
9. Enable Webhook URL.
10. Use:
   `https://YOUR-DOMAIN.com/webhook/tradingview`
11. Enable TradingView 2FA because TradingView requires it for webhook alerts.

The Pine script sends each completed 15-minute bar plus:
- OHLCV
- EMA 9 / EMA 20
- RSI 14
- VWAP
- ATR 14
- volume SMA 20
- EMA cross state
- high-volume state
- previous-bar breakout state

## 4. Important webhook security

TradingView's alert body should NOT contain credentials or API keys.

This starter supports an `X-Webhook-Secret` header, but TradingView's standard webhook
UI does not provide arbitrary custom headers. Therefore, for production you should
either:

A) put the receiver behind Cloudflare/API Gateway with a hard-to-guess path/token,
B) validate TradingView's webhook certificate at your reverse proxy,
C) allowlist TradingView webhook IPs at the infrastructure layer,
or D) place an authenticated relay between TradingView and this app.

If you leave `WEBHOOK_SECRET` empty, the FastAPI endpoint accepts requests without
that header. Only do that if the endpoint is protected elsewhere.

## 5. Telegram alerts

Create a Telegram bot via BotFather, get:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

Set both as environment variables.

The server currently sends Telegram messages only when the AI response is interpreted
as an actionable LONG.

## 6. Add multiple coins

TradingView alerts are chart/script instances, so add the script and create an alert
for each symbol you want monitored, for example:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- UNIUSDT
- LINKUSDT
- ENAUSDT
- PONSUSDT (on a venue/feed where available)

For a broader universe, create alerts across the assets you actually trade rather than
blindly covering thousands of illiquid tokens.

## 7. What this does NOT do

- It does not place trades automatically.
- It does not guarantee profit.
- It does not magically have derivatives/order-book/on-chain/news data unless you
  explicitly add those data feeds.
- It does not replace exchange-side risk controls.

## 8. Recommended next upgrade

The strongest next version is to have the server maintain rolling 5m/15m/1h market
state and add exchange APIs for:
- funding
- open interest
- liquidation data
- cross-exchange price confirmation
- relative-strength ranking

Then the AI evaluates all of that together instead of only the TradingView bar payload.
