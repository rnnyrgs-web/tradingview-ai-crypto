import json
import os
import time
from datetime import datetime, timezone

from backtest import run_backtest, walk_forward
from strategy_families import evaluate_strategy_registry


def csv_env(name, default):
    raw = os.getenv(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


def main():
    symbols = csv_env("RESEARCH_SYMBOLS", "BTC-USDT,ETH-USDT,SOL-USDT,XRP-USDT,LINK-USDT")
    timeframes = csv_env("RESEARCH_TIMEFRAMES", "15m,1H")
    bars = int(os.getenv("RESEARCH_BARS", "5000"))
    threshold = float(os.getenv("RESEARCH_THRESHOLD", "2.25"))

    started = datetime.now(timezone.utc).isoformat()
    results = []

    for symbol in symbols:
        for bar in timeframes:
            item = {
                "symbol": symbol,
                "bar": bar,
                "bars_requested": bars,
            }
            t0 = time.time()
            try:
                item["backtest"] = run_backtest(symbol, bar=bar, bars=bars, threshold=threshold)
                item["walk_forward"] = walk_forward(symbol, bar=bar, bars=bars)
                item["strategy_registry"] = evaluate_strategy_registry(symbol, bar=bar, bars=bars)
                item["ok"] = True
            except Exception as exc:
                item["ok"] = False
                item["error"] = f"{type(exc).__name__}: {exc}"
            item["elapsed_seconds"] = round(time.time() - t0, 2)
            results.append(item)
            print(json.dumps(item, default=str), flush=True)

    eligible = []
    for item in results:
        registry = (item.get("strategy_registry") or {}).get("registry", [])
        for strategy in registry:
            if strategy.get("quality_gate", {}).get("passed"):
                eligible.append({
                    "symbol": item["symbol"],
                    "bar": item["bar"],
                    "strategy_family": strategy["strategy_family"],
                    "validation": strategy["validation"],
                    "holdout_test": strategy["holdout_test"],
                })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started,
        "source": "OKX public historical API",
        "compute": "GitHub Actions cloud runner",
        "symbols": symbols,
        "timeframes": timeframes,
        "bars_requested": bars,
        "threshold": threshold,
        "strategy_policy": "research-only unless strict validation+holdout OOS quality gate passes",
        "eligible_strategy_count": len(eligible),
        "eligible_strategies": eligible,
        "results": results,
    }

    os.makedirs("research_output", exist_ok=True)
    with open("research_output/backtest_results.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with open("research_output/strategy_registry.json", "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": payload["generated_at"],
            "policy": payload["strategy_policy"],
            "eligible_strategy_count": len(eligible),
            "eligible_strategies": eligible,
        }, f, indent=2)

    failures = sum(1 for x in results if not x.get("ok"))
    print(f"Completed {len(results)} research jobs with {failures} failures and {len(eligible)} OOS-eligible strategies.")
    if failures == len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
