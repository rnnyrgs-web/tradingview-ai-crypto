import json
import os
import sys
import time
import zlib
from datetime import datetime, timezone

from backtest import run_backtest, walk_forward
from execution_oos import evaluate_execution_oos
from market_data import build_universe
from multiple_testing import apply_registry_firewall
from point_in_time_universe import assess_symbol_set, load_manifest
from strategy_families import STRATEGY_FAMILIES, evaluate_strategy_registry
from research_artifact import seal_research_payload
from worker_supervisor import sanitize_diagnostic


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

    selected = [symbol for symbol in ranked if stable_shard(symbol, shard_count) == shard_index]
    return selected, {
        "mode": "dynamic_liquid_universe",
        "universe_size_target": target,
        "universe_size_resolved": len(ranked),
        "resolved_symbols": ranked,
        "forced_symbols": forced,
        "shard_index": shard_index,
        "shard_count": shard_count,
    }


def declared_hypothesis_trials(symbols, timeframes, universe_meta):
    resolved = int(universe_meta.get("universe_size_resolved") or len(symbols) or 1)
    return max(1, resolved) * max(1, len(timeframes)) * len(STRATEGY_FAMILIES) * 3


def _demote_for_survivorship(registry_result, survivorship):
    """ACC-011 is restrictive only and cannot make a strategy eligible."""
    for row in (registry_result.get("registry") or []):
        row["point_in_time_universe_gate"] = survivorship
        if row.get("eligible_for_promotion_review") is True and not survivorship.get("promotion_allowed"):
            row["eligible_for_promotion_review"] = False
            row["status"] = "RESEARCH_ONLY"
            quality = row.setdefault("quality_gate", {})
            reasons = list(quality.get("reasons") or [])
            if "point_in_time_universe_evidence_insufficient" not in reasons:
                reasons.append("point_in_time_universe_evidence_insufficient")
            quality["reasons"] = reasons
    registry_result["eligible_count"] = sum(1 for row in (registry_result.get("registry") or []) if row.get("eligible_for_promotion_review") is True)
    registry_result["point_in_time_universe"] = survivorship
    return registry_result


def _emit_private_failure_diagnostic(symbol, bar, exc):
    diagnostic = sanitize_diagnostic(f"{type(exc).__name__}: {exc}")
    print(
        f"research_job_failure symbol={symbol} bar={bar} diagnostic={diagnostic or '<none>'}",
        file=sys.stderr,
        flush=True,
    )


def main():
    symbols, universe_meta = resolve_research_symbols()
    timeframes = csv_env("RESEARCH_TIMEFRAMES", "15m,1H")
    bars = int(os.getenv("RESEARCH_BARS", "5000"))
    threshold = float(os.getenv("RESEARCH_THRESHOLD", "2.25"))
    execution_quote_notional = float(os.getenv("RESEARCH_EXECUTION_NOTIONAL", "5000"))
    trial_count = declared_hypothesis_trials(symbols, timeframes, universe_meta)

    manifest = load_manifest(os.getenv("POINT_IN_TIME_UNIVERSE_MANIFEST", "").strip() or None)
    full_research_symbol_set = universe_meta.get("resolved_symbols") or symbols
    survivorship = assess_symbol_set(manifest, full_research_symbol_set)

    started = datetime.now(timezone.utc).isoformat()
    results = []

    for symbol in symbols:
        for bar in timeframes:
            item = {
                "symbol": symbol,
                "bar": bar,
                "bars_requested": bars,
                "declared_hypothesis_trials": trial_count,
                "point_in_time_universe": survivorship,
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
                raw_registry = evaluate_strategy_registry(symbol, bar=bar, bars=bars)
                multiple_testing_registry = apply_registry_firewall(raw_registry, trial_count)
                item["strategy_registry"] = _demote_for_survivorship(multiple_testing_registry, survivorship)
                item["ok"] = True
            except Exception as exc:
                item["ok"] = False
                item["error"] = f"{type(exc).__name__}: {exc}"
                _emit_private_failure_diagnostic(symbol, bar, exc)
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
                    "multiple_testing_gate": strategy["multiple_testing_gate"],
                    "point_in_time_universe_gate": strategy["point_in_time_universe_gate"],
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
        "point_in_time_universe": survivorship,
        "declared_hypothesis_trials": trial_count,
        "strategy_policy": "research-only unless validation+holdout OOS+robustness+search-breadth+point-in-time-universe gates pass",
        "multiple_testing_policy": (
            "Search breadth is declared before OOS inspection. More strategy/parameter hypotheses require deeper OOS "
            "and stronger bootstrap support. This is a conservative evidence penalty, not a claimed formal p-value correction."
        ),
        "survivorship_policy": (
            "Today's survivors cannot establish historical universe membership. Promotion review is blocked unless a "
            "provenanced point-in-time snapshot manifest covers all historical universe members used by the research search."
        ),
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
            "multiple_testing_policy": payload["multiple_testing_policy"],
            "survivorship_policy": payload["survivorship_policy"],
            "point_in_time_universe": survivorship,
            "declared_hypothesis_trials": trial_count,
            "execution_policy": payload["execution_policy"],
            "universe": universe_meta,
            "eligible_strategy_count": len(eligible),
            "eligible_strategies": eligible,
        }
        json.dump(seal_research_payload(registry_payload), f, indent=2)

    failures = sum(1 for x in results if not x.get("ok"))
    print(
        f"Completed {len(results)} research jobs with {failures} failures and "
        f"{len(eligible)} promotion-review-eligible strategies after {trial_count} declared hypotheses. Universe={universe_meta}."
    )
    if results and failures == len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
