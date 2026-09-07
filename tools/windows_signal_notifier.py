import ctypes
import json
import os
import time
import urllib.parse
import urllib.request
import webbrowser
import winsound

BASE_URL = os.getenv("SIGNAL_SERVER_URL", "https://tradingview-ai-crypto.onrender.com").rstrip("/")
SCAN_SECRET = os.getenv("SCAN_SECRET", "")
POLL_SECONDS = max(5, int(os.getenv("SIGNAL_POLL_SECONDS", "15")))

INTERVAL_MAP = {
    "intraday": "15",
    "24h": "60",
    "7d": "240",
    "30d": "D",
}


def _validated_base_url():
    parsed = urllib.parse.urlparse(BASE_URL)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise RuntimeError("SIGNAL_SERVER_URL must be a credential-free HTTPS URL")
    return BASE_URL


def get_json(path):
    if not SCAN_SECRET:
        raise RuntimeError("SCAN_SECRET environment variable is required")
    url = f"{_validated_base_url()}{path}"
    req = urllib.request.Request(url, headers={"X-Scan-Secret": SCAN_SECRET})
    with urllib.request.urlopen(req, timeout=20) as r:  # nosec B310 - HTTPS scheme is validated above
        return json.loads(r.read().decode("utf-8"))


def fetch_signals(after_id):
    return get_json(f"/signals?after_id={int(after_id)}&limit=20")


def fetch_cursor():
    return int(get_json("/signals/cursor").get("latest_id", 0))


def tradingview_url(signal):
    symbol = str(signal["symbol"]).replace("-", "")
    interval = INTERVAL_MAP.get(str(signal.get("timeframe", "")), "15")
    params = urllib.parse.urlencode({"symbol": f"OKX:{symbol}", "interval": interval})
    return f"https://www.tradingview.com/chart/?{params}"


def alert(signal):
    text = (
        f"{signal['direction']} {signal['symbol']} ({signal['timeframe']})\n"
        f"Entry: {signal.get('entry_price')}\n"
        f"Stop: {signal.get('stop_loss')}\n"
        f"Target 1: {signal.get('target_1')}\n"
        f"Target 2: {signal.get('target_2')}\n"
        f"Evidence: {signal.get('evidence_score')}\n"
        f"Regime: {signal.get('market_regime')}"
    )
    winsound.Beep(1200, 500)
    winsound.Beep(1500, 500)
    webbrowser.open_new_tab(tradingview_url(signal))
    ctypes.windll.user32.MessageBoxW(0, text, "CRYPTO SIGNAL", 0x00001000)


def main():
    configured_start = os.getenv("SIGNAL_START_AFTER_ID")
    last_id = int(configured_start) if configured_start else fetch_cursor()
    print(f"Signal notifier armed after id {last_id}; historical signals will not alert.", flush=True)
    while True:
        try:
            payload = fetch_signals(last_id)
            for signal in payload.get("signals", []):
                sid = int(signal["id"])
                if sid <= last_id:
                    continue
                alert(signal)
                last_id = sid
        except Exception as exc:
            print(f"signal notifier error: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
