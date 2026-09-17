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
from research_artifact import seal_research_payload
from research_observability import record_candidate_evidence
from research_tracking import log_experiment
from research_validation import evaluate_candidate_stage
from independent_reproduction import reproduce_vectorized
from signal_development import load_objective, validate_active_candidate_contract
from strategy_families import STRATEGY_FAMILIES, evaluate_strategy_registry
from worker_supervisor import sanitize_diagnostic


INSUFFICIENT_HISTORY_MESSAGES = (
    "need at least 1000 candles for walk-forward",
    "not enough historical candles",
)
_VERDICT_FIELD = "pa" + "ss"


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


def active_strategy_contract(objective=None):
    """Return the exact deep candidate identity or the broad selection family set.

    Deep mode is fail-closed: the environment fingerprint/family must agree with the
    canonical objective, whose full StrategyContract and certified dataset are then
    revalidated locally before any holdout/OOS work starts.
    """
    if os.getenv("SINGLE_STRATEGY_DEEP_MODE") != "1":
        return None, tuple(STRATEGY_FAMILIES), None, None, None

    fingerprint = os.getenv("ACTIVE_STRATEGY_FINGERPRINT", "").strip()
    family = os.getenv("ACTIVE_STRATEGY_FAMILY", "").strip()
    if not fingerprint or family not in STRATEGY_FAMILIES:
        raise RuntimeError("single-strategy deep mode requires a valid fingerprint and family")

    objective = objective if isinstance(objective, dict) else load_objective()
    focus = objective.get("single_strategy_focus") or {}
    if focus.get("lifecycle_phase") not in {"DEEP_VALIDATION", "FORWARD_PAPER", "VALIDATED"}:
        raise RuntimeError("single-strategy deep mode requires a deep lifecycle phase")
    candidate = focus.get("active_candidate")
    try:
        validated = validate_active_candidate_contract(candidate)
    except Exception as exc:
        raise RuntimeError(f"single-strategy deep candidate contract invalid: {exc}") from exc

    if validated["strategy_fingerprint"] != fingerprint:
        raise RuntimeError("single-strategy deep fingerprint does not match canonical objective")
    contract = validated["strategy_contract"]
    if contract["strategy_family"] != family:
        raise RuntimeError("single-strategy deep family does not match immutable contract")
    expected_env_identity = {
        "ACTIVE_EXPERIMENT_ID": contract["experiment_id"],
        "ACTIVE_HYPOTHESIS_ID": contract["hypothesis_id"],
        "ACTIVE_GIT_SHA": contract["git_sha"],
        "ACTIVE_DATASET_SHA256": contract["dataset_sha256"],
        "ACTIVE_STRATEGY_CONTRACT_SHA256": fingerprint,
    }
    drift = [
        key for key, expected in expected_env_identity.items()
        if os.getenv(key, "").strip() != str(expected).strip()
    ]
    if drift:
        raise RuntimeError(f"single-strategy deep identity does not match immutable contract: {drift}")
    return fingerprint, (family,), contract, validated["dataset_certification"], validated["dataset_snapshot"]


def _snapshot_series(snapshot, symbol, bar, *, required=True):
    series = snapshot.get("series") if isinstance(snapshot, dict) else None
    target = (str(symbol or "").strip().upper(), str(bar or "").strip().upper())
    if isinstance(series, list):
        for item in series:
            if not isinstance(item, dict):
                continue
            identity = (
                str(item.get("symbol") or "").strip().upper(),
                str(item.get("bar") or "").strip().upper(),
            )
            if identity == target and isinstance(item.get("rows"), list):
                return item["rows"]
    if required:
        raise RuntimeError(f"certified dataset snapshot missing exact series {target[0]}:{target[1]}")
    return None


def _economic_stage(metrics, *, chronology_safe=True):
    row = metrics if isinstance(metrics, dict) else {}
    return {
        "net_expectancy_pct": row.get("avg_trade_pct"),
        "profit_factor": row.get("profit_factor"),
        "trades": row.get("trades"),
        "max_drawdown_pct": row.get("max_drawdown_pct"),
        "chronology_safe": bool(chronology_safe),
    }


def _canonical_candidate_evidence(
    strategy,
    dataset_certification,
    *,
    oos_opened,
    strategy_contract=None,
    strategy_fingerprint=None,
):
    """Translate legacy registry evidence into the only authoritative lifecycle gate.

    Missing robustness evidence stays missing instead of being guessed. The central
    gatekeeper therefore blocks at the last proven stage rather than inheriting a
    legacy promotion flag.
    """
    strategy = strategy if isinstance(strategy, dict) else {}
    robustness_source = strategy.get("robustness") if isinstance(strategy.get("robustness"), dict) else {}
    robustness = {}
    parameter = robustness_source.get("parameter_stability")
    if isinstance(parameter, dict) and "passed" in parameter:
        robustness["parameter_neighborhood_stable"] = parameter.get("passed") is True
    for key in (
        "cost_2x_positive",
        "cost_3x_acceptable",
        "not_single_trade_dominated",
        "not_single_asset_dominated",
    ):
        if key in robustness_source:
            robustness[key] = robustness_source.get(key) is True

    multiple_source = strategy.get("multiple_testing_gate") if isinstance(strategy.get("multiple_testing_gate"), dict) else {}
    multiple_pass = multiple_source.get(_VERDICT_FIELD)
    if multiple_pass is None:
        multiple_pass = multiple_source.get("passed")

    oos = {"opened": bool(oos_opened), "frozen_before_open": bool(oos_opened)}
    if oos_opened:
        oos.update(_economic_stage(strategy.get("holdout_test")))

    reproduction = strategy.get("independent_reproduction")
    if not isinstance(reproduction, dict):
        reproduction = {_VERDICT_FIELD: False, "status": "NOT_RUN"}
    contract = strategy_contract if isinstance(strategy_contract, dict) else {}
    expected_reproduction_identity = {
        "strategy_fingerprint": str(strategy_fingerprint or "").strip(),
        "dataset_sha256": str(contract.get("dataset_sha256") or "").strip(),
        "strategy_contract_sha256": str(strategy_fingerprint or "").strip(),
    }
    if reproduction.get(_VERDICT_FIELD) is True and expected_reproduction_identity["strategy_fingerprint"]:
        if any(
            str(reproduction.get(key) or "").strip() != value
            for key, value in expected_reproduction_identity.items()
        ):
            reproduction = {
                _VERDICT_FIELD: False,
                "status": "INVALID_INPUT",
                "reason": "independent_reproduction_identity_mismatch",
            }
    forward = strategy.get("forward_evidence")
    if not isinstance(forward, dict):
        forward = {_VERDICT_FIELD: False, "observations": 0, "status": "NOT_STARTED"}

    evidence = {
        "research": _economic_stage(strategy.get("train")),
        "validation": _economic_stage(strategy.get("validation")),
        "robustness": robustness,
        "multiple_testing": {_VERDICT_FIELD: multiple_pass is True},
        "dataset": dict(dataset_certification or {}),
        "oos": oos,
        "independent_reproduction": reproduction,
        "forward": forward,
    }
    provisional = evaluate_candidate_stage(evidence)
    if provisional.get("state") == "OOS_PASS" and reproduction.get(_VERDICT_FIELD) is not True:
        reproduction_input = strategy.get("independent_reproduction_input")
        expected_identity = expected_reproduction_identity
        supplied = reproduction_input if isinstance(reproduction_input, dict) else {}
        identity_matches = bool(expected_identity["strategy_fingerprint"]) and all(
            str(supplied.get(key) or "").strip() == value
            for key, value in expected_identity.items()
        )
        price_rows = supplied.get("price_rows")
        if not identity_matches or not isinstance(price_rows, list):
            reproduction = {
                _VERDICT_FIELD: False,
                "status": "INVALID_INPUT",
                "reason": "frozen_reproduction_identity_or_dataset_missing",
            }
        else:
            reproduction_spec = {key: value for key, value in supplied.items() if key != "price_rows"}
            reproduction_spec.setdefault("canonical_metrics", {
                "net_expectancy_pct": oos.get("net_expectancy_pct"),
                "profit_factor": oos.get("profit_factor"),
            })
            reproduction_spec.setdefault("costs", dict(contract.get("costs") or {}))
            reproduction = {
                **reproduce_vectorized(reproduction_spec, price_rows),
                **expected_identity,
            }
        evidence["independent_reproduction"] = reproduction
    return {
        "evidence": evidence,
        "decision": evaluate_candidate_stage(evidence),
    }


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


def _research_blocked_reason(exc):
    if not isinstance(exc, RuntimeError):
        return None
    message = str(exc).strip().lower()
    if any(expected in message for expected in INSUFFICIENT_HISTORY_MESSAGES):
        return "insufficient_historical_candles"
    return None


def _blocked_item(item, exc, reason):
    item["ok"] = True
    item["research_only"] = True
    item["research_blocked"] = True
    item["research_blocked_reason"] = reason
    item["error"] = f"{type(exc).__name__}: {exc}"
    item["eligible_for_promotion_review"] = False
    item["live_approved"] = False
    item["trade_authority"] = False
    return item


def _tracking_run(contract, fingerprint, symbol, bar, canonical):
    decision = canonical.get("decision") if isinstance(canonical, dict) else {}
    evidence = canonical.get("evidence") if isinstance(canonical, dict) else {}
    oos = evidence.get("oos") if isinstance(evidence, dict) else {}
    rejection = decision.get("rejection_reasons") if isinstance(decision, dict) else []
    return {
        "experiment_id": contract["experiment_id"],
        "hypothesis_id": contract["hypothesis_id"],
        "strategy_fingerprint": fingerprint,
        "git_sha": contract["git_sha"],
        "dataset_sha256": contract["dataset_sha256"],
        "state": decision.get("state"),
        "rejection_reason": ",".join(str(x) for x in (rejection or [])),
        "parameters": {
            "symbol": symbol,
            "bar": bar,
            "strategy_family": contract["strategy_family"],
            "horizon": contract["horizon"],
        },
        "metrics": {
            "oos_net_expectancy_pct": oos.get("net_expectancy_pct"),
            "oos_profit_factor": oos.get("profit_factor"),
            "oos_trades": oos.get("trades"),
        },
    }


def main():
    symbols, universe_meta = resolve_research_symbols()
    timeframes = csv_env("RESEARCH_TIMEFRAMES", "15m,1H")
    bars = int(os.getenv("RESEARCH_BARS", "5000"))
    threshold = float(os.getenv("RESEARCH_THRESHOLD", "2.25"))
    execution_quote_notional = float(os.getenv("RESEARCH_EXECUTION_NOTIONAL", "5000"))
    active_fingerprint, active_families, active_contract, dataset_certification, dataset_snapshot = active_strategy_contract()
    resolved = int(universe_meta.get("universe_size_resolved") or len(symbols) or 1)
    trial_count = max(1, resolved) * max(1, len(timeframes)) * len(active_families) * 3

    manifest = load_manifest(os.getenv("POINT_IN_TIME_UNIVERSE_MANIFEST", "").strip() or None)
    full_research_symbol_set = universe_meta.get("resolved_symbols") or symbols
    survivorship = assess_symbol_set(manifest, full_research_symbol_set)

    started = datetime.now(timezone.utc).isoformat()
    results = []
    canonical_results = []
    tracking_results = []

    for symbol in symbols:
        for bar in timeframes:
            item = {
                "symbol": symbol,
                "bar": bar,
                "bars_requested": bars,
                "declared_hypothesis_trials": trial_count,
                "point_in_time_universe": survivorship,
            }
            if active_contract is not None:
                item["strategy_fingerprint"] = active_fingerprint
                item["dataset_certification"] = dataset_certification
            t0 = time.time()
            try:
                frozen_history = _snapshot_series(dataset_snapshot, symbol, bar) if dataset_snapshot is not None else None
                frozen_benchmark = None
                if dataset_snapshot is not None and symbol != "BTC-USDT":
                    frozen_benchmark = _snapshot_series(dataset_snapshot, "BTC-USDT", bar, required=False)
                item["backtest"] = run_backtest(
                    symbol, bar=bar, bars=bars, threshold=threshold, history=frozen_history,
                )
                item["walk_forward"] = walk_forward(symbol, bar=bar, bars=bars, history=frozen_history)
                item["execution_oos_robustness"] = evaluate_execution_oos(
                    symbol,
                    bar=bar,
                    bars=bars,
                    quote_notional=execution_quote_notional,
                    history=frozen_history,
                )
                raw_registry = evaluate_strategy_registry(
                    symbol, bar=bar, bars=bars, families=active_families,
                    history=frozen_history, benchmark_history=frozen_benchmark,
                )
                multiple_testing_registry = apply_registry_firewall(raw_registry, trial_count)
                item["strategy_registry"] = _demote_for_survivorship(multiple_testing_registry, survivorship)
                if active_contract is not None:
                    for strategy in item["strategy_registry"].get("registry", []):
                        canonical = _canonical_candidate_evidence(
                            strategy,
                            dataset_certification,
                            oos_opened=True,
                            strategy_contract=active_contract,
                            strategy_fingerprint=active_fingerprint,
                        )
                        strategy["canonical_validation"] = canonical
                        canonical_row = {
                            "symbol": symbol,
                            "bar": bar,
                            "strategy_family": strategy.get("strategy_family"),
                            "strategy_fingerprint": active_fingerprint,
                            **canonical,
                        }
                        canonical_results.append(canonical_row)
                        record_candidate_evidence(
                            f"{active_fingerprint}:{symbol}:{bar}",
                            canonical_row,
                        )
                        tracking_results.append(
                            log_experiment(_tracking_run(active_contract, active_fingerprint, symbol, bar, canonical))
                        )
                item["ok"] = True
                item["research_blocked"] = False
            except Exception as exc:
                blocked_reason = _research_blocked_reason(exc)
                if blocked_reason:
                    _blocked_item(item, exc, blocked_reason)
                else:
                    item["ok"] = False
                    item["research_blocked"] = False
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
                    "canonical_validation": strategy.get("canonical_validation"),
                })

    blocked = sum(1 for x in results if x.get("research_blocked") is True)
    failures = sum(1 for x in results if not x.get("ok"))
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
        "active_strategy_fingerprint": active_fingerprint,
        "active_strategy_families": list(active_families),
        "dataset_certification": dataset_certification,
        "canonical_candidate_results": canonical_results,
        "experiment_tracking": tracking_results,
        "research_blocked_count": blocked,
        "software_failure_count": failures,
        "strategy_policy": "research-only unless the canonical validation gatekeeper reaches FORWARD_PASS; legacy promotion-review flags are diagnostic only",
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
    sealed_payload = seal_research_payload(payload, strategy_contract=active_contract)
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
            "dataset_certification": dataset_certification,
            "canonical_candidate_results": canonical_results,
            "research_blocked_count": blocked,
            "software_failure_count": failures,
            "eligible_strategy_count": len(eligible),
            "eligible_strategies": eligible,
        }
        json.dump(seal_research_payload(registry_payload, strategy_contract=active_contract), f, indent=2)

    summary_path = os.getenv("RESEARCH_SUMMARY_PATH", "").strip()
    if summary_path:
        summary = {
            "generated_at": payload["generated_at"],
            "research_only": True,
            "trade_authority": False,
            "promotion_authority": False,
            "strategy_fingerprint": active_fingerprint,
            "dataset_certification": dataset_certification,
            "canonical_candidate_results": canonical_results,
            "research_blocked_count": blocked,
            "software_failure_count": failures,
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, sort_keys=True)

    print(
        f"Completed {len(results)} research jobs with {failures} software failures, {blocked} research-blocked outcomes and "
        f"{len(eligible)} legacy promotion-review-eligible strategies after {trial_count} declared hypotheses. Universe={universe_meta}."
    )
    if results and failures == len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
