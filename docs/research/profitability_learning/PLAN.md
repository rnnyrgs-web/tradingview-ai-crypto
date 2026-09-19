# Profitability learning and strategy evolution implementation plan

Spec: supplied user milestone, summarized in `ARCHITECTURE.md`. Initial base: c51a59dbac604a2e0b2eefa2b68ae025d4c5b0e3.
Direct user-assigned milestone: PROFITABILITY-LEARNING-EVOLUTION-001.
Branch: agent/profitability-learning-evolution. Implement inline, independently review the whole branch.

## Architecture and decisions

Use a dependency-free Python package with strict versioned evidence contracts,
portfolio NAV analytics, development-only ablation/mining, immutable SQLite
research memory and deterministic evidence-weighted mission proposals. Existing
completion and director entry points consume the package. It grants no execution,
promotion or trading authority. No data download or paid model is needed.

Ruling: implement the supplied detailed user specification directly; the user
explicitly authorized continuous implementation through tested PR handoff.
Ruling: do not edit the active discovery supervisor (#432), Big-Move lab (#433),
coordination (#435), foundation (#387), or frozen strategy screens. Integrate
through new completion adapters and the existing research director/factory.
Ruling: missing NAV/position sizing cannot produce compounded portfolio returns.
Legacy completion summaries receive classified learning artifacts with explicit
missing-evidence requirements; they cannot fabricate component evidence.
Ruling: persistent memory requires an explicit durable local path or a versioned
JSON export/import. Unconfigured runtime reports WAIT_MEMORY_NOT_CONFIGURED,
never claims that an ephemeral cache is durable. No database/service migration.

## Tasks and interfaces

1. Strict evidence + economic analytics (`profitability_learning/contracts.py`,
   `analytics.py`). Tests first: hand-calculated NAV/cost reconciliation,
   catastrophic high-win-rate loss, lucky-trade concentration, stale/future PIT
   features, overlapping positions, missing data, nonfinite values, insolvency.
   API: `analyze(experiment: dict) -> dict` with no side effects.
2. Development component ablation + subgroup miner (`development.py`). Tests
   first: useful component in losing strategy, harmful component in winner,
   factorial interaction, OOS callback never called, search breadth enforced,
   non-independent events cannot inflate sample sizes. API:
   `run_ablation(contract, dataset, evaluator)`, `mine_conditions(experiment)`.
3. Memory + evolution (`memory.py`, `evolution.py`). Tests first: immutable replay,
   conflicting results, concurrent insert, restart, corruption, component
   aggregation, rejection preservation, semantic duplicate suppression, changed
   mechanism requirement, fresh chronological boundaries, evidence ancestry.
   API: `Memory(path).complete(experiment)`, `.snapshot()`, `.propose(...)`.
4. Runtime integration (`runtime.py`, CLI; existing completion, factory and
   director). Tests first: real completion-to-memory-to-ranked-mission chain,
   safe missing store, corrupt configured store, legacy sparse outcomes, no
   OOS-derived successor, deterministic explore/exploit/learn balance.
5. Full applicable suite, security checks, independent branch review, precise
   architecture/limitations/handoff. Publish isolated PR and verify Security and
   Reliability at its exact head; never merge this PR.

## Review focus

- Concurrent workers/replays must not inflate independent evidence or lose data.
- Portfolio compounding must use reconciled NAV, not multiply overlapping trades.
- Future feature availability and protected splits must fail before analysis.
- Cosmetic/parameter-only mutations must not resurrect a rejected mechanism.
- Missing persistence/provenance must produce explicit blocked states.

## Verification

`PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_profitability_learning*.py`
then `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q`.
Run Bandit, committed-secret scan and applicable dependency audit. Synthetic
fixtures verify software only; no strategy backtest/OOS/forward success claimed.

## Progress

- Startup: current main, complete canonical rules, ranked queue, negative memory,
  override-applied specialist ownership, all 8 open PRs and active CI inspected.
- Baseline environment needed pytest and SOCKS transport support; installed only
  in the task environment, with no repository dependency change.

- Re-synced to bd44b9e957c915774833ccc11060548a5693ddf8 after PR #435; QUANT-004 remains independently owned.
- Removed verbatim uploaded instructions from publication; implementation documentation contains the project requirements and interfaces.
