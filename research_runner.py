import json
import os
import time
import zlib
from datetime import datetime, timezone

from backtest import run_backtest, walk_forward
from execution_oos import evaluate_execution_oos
from market_data import build_universe
from strategy_families import evaluate_strategy_registry
from research_artifact import seal_research_payload


def csv_env(name, default=""):
    raw = os.getenv(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


def stable_shard(symbol, shard_count):
    count = max(1, int(shard_count))
    return zlib.crc32(symbol.encode("utf-8")) % count


def resolve_research_symbols():
    explicit = csv_env("RESEARCH_SYMBOLS")
    if explicit:
        return explicit, {
            "mode": "explicit",
            "universe_size_target": len(explicit),
            "universe_size_resolved": len(explicit),
            "forced_symbols": [],
            "shard_index": 0,
            "shard_count": 1,
        }

    target = max(1, min(int(os.getenv("RESEARCH_UNIVERSE_SIZE", "80")), 100))
    shard_count = max(1, int(os.getenv("RESEARCH_SHARD_COUNT", "1")))
    shard_index = int(os.getenv("RESEARCH_SHARD_INDEX", "0"))
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("RESEARCH_SHARD_INDEX must be within RESEARCH_SHARD_COUNT")

    ranked = [row["symbol"] for row in build_universe()[:target]]
    forced = csv_env("RESEARCH_FORCE_SYMBOLS", "PONS-USDT-SWAP")
    for symbol in forced:
        if symbol not in ranked:
            ranked.append(symbol)

    selected = [
        symbol for symbol in ranked
        if stable_shard(symbol, shard_count) == shard_index
    ]
    return selected, {
        "mode": "dynamic_liquid_universe",
        "universe_size_target": target,
        "universe_size_resolved": len(ranked),
        "forced_symbols": forced,
        "shard_index": shard_index,
        "shard_count": shard_count,
    }


def main():
    symbols, universe_meta = resolve_research_symbols()
    timeframes = csv_env("RESEARCH_TIMEFRAMES", "15m,1H")
    bars = int(os.getenv("RESEARCH_BARS", "5000"))
    threshold = float(os.getenv("RESEARCH_THRESHOLD", "2.25"))
    execution_quote_notional = float(os.getenv("RESEARCH_EXECUTION_NOTIONAL", "5000"))

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
                item["execution_oos_robustness"] = evaluate_execution_oos(
                    symbol,
                    bar=bar,
                    bars=bars,
                    quote_notional=execution_quote_notional,
                )
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
            if strategy.get("eligible_for_promotion_review") is True:
                eligible.append({
                    "symbol": item["symbol"],
                    "bar": item["bar"],
                    "strategy_family": strategy["strategy_family"],
                    "validation": strategy["validation"],
                    "holdout_test": strategy["holdout_test"],
                    "robustness": strategy["robustness"],
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
        "execution_quote_notional": execution_quote_notional,
        "universe": universe_meta,
        "strategy_policy": "research-only unless strict validation+holdout OOS quality gate passes",
        "execution_policy": (
            "Current live order-book slippage may expand conservative untouched-OOS cost stress only; "
            "it is never backfilled as historical execution data and cannot authorize promotion."
        ),
        "eligible_strategy_count": len(eligible),
        "eligible_strategies": eligible,
        "results": results,
    }

    os.makedirs("research_output", exist_ok=True)
    sealed_payload = seal_research_payload(payload)
    with open("research_output/backtest_results.json", "w", encoding="utf-8") as f:
        json.dump(sealed_payload, f, indent=2)

    with open("research_output/strategy_registry.json", "w", encoding="utf-8") as f:
        registry_payload = {
            "generated_at": payload["generated_at"],
            "policy": payload["strategy_policy"],
            "execution_policy": payload["execution_policy"],
            "universe": universe_meta,
            "eligible_strategy_count": len(eligible),
            "eligible_strategies": eligible,
        }
        json.dump(seal_research_payload(registry_payload), f, indent=2)

    failures = sum(1 for x in results if not x.get("ok"))
    print(
        f"Completed {len(results)} research jobs with {failures} failures and "
        f"{len(eligible)} OOS-eligible strategies. Universe={universe_meta}."
    )
    if results and failures == len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
