# AI DEVELOPMENT STATE
Last updated: 2026-09-11

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current functional baseline through PR #269: merge commit `9e179015c443e9e8eb0467239f68b9a8ea81dffd`.

Production is GitHub -> Render -> Python/FastAPI V3 -> Supabase. Governed horizons are 6h, 12h, 24h, 48h, 72h and 7d. New horizons remain WAIT/LEARNING unless every canonical gate is independently satisfied. Production scans run about every 15 minutes. Continuous research/backtesting uses the existing Render coordinator with bounded concurrency.

Primary production service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Recurring infrastructure ceiling: USD 30/month unless explicitly approved otherwise.

The always-on research architecture includes bounded Python workers, deterministic experiment generation, adaptive-accuracy research, durable research memory, economic calibration/meta-WAIT, regime x strategy diagnostics, cross-sectional/residual diagnostics, microstructure/execution diagnostics, ensemble-diversity/error attribution, selective-WAIT research, and evidence-value scheduling. Logical specialist scale is not physical compute scale. Heavy experiment admission remains capped at one unless separately reviewed and cost-approved.

## RECENT INTEGRATED EVIDENCE / CHANGES
- Multi-horizon production and research remain governed by exact immutable horizons and chronology. Calibration evaluates due predictions before the next production scan.
- FFriZz V1 is research/shadow only. Eligible prospective persistence remains blocked whenever the coordinator lacks the complete canonical prediction-ledger configuration. `PredictionLedgerNotConfigured` is fail-closed and must not be bypassed.
- FFriZz V2 exact candle-end = Binance OI period-end matching is a durable negative timestamp-coverage result. Do not loosen matching or repeat it unless source timestamp semantics materially change.
- FFriZz V3 causal-as-of remains a separately fingerprinted research-only data-semantics challenger: latest already-completed 1H price endpoint at or before the OI timestamp, staleness strictly below one hour, no future selection, no nearest-neighbour/interpolation, duplicate OI rejection, and ambiguous price-endpoint reuse rejection. It has no persistence or trading authority.
- Binance historical OI from the present Render environment is consistently blocked by HTTP 451. Bounded diagnostics expose only allowlisted status buckets. PR #260 circuit-breaks redundant Binance OI calls after the first confirmed 451 in each research run; the next run probes once again so recovery can be detected. Missing OI remains fail-closed.
- PRs #262 and #264-#268 added, runtime-wired, invoked, and hardened a strictly bounded research-only Bybit V5 historical-OI accessibility probe. It makes at most the predeclared small accessibility request, exposes only bounded aggregate status/point-count diagnostics, and has zero signal, persistence, paper, promotion, broker, or live authority.
- Fresh live evidence from the current Render research environment: the Bybit historical-OI accessibility probe returned `http_403`, with one request and zero usable points. This is an infrastructure/source-access result only. It is not alpha evidence and does not falsify causal OI alignment itself.
- PR #269 preserves that Bybit 403 result in `orchestration/ffrizz_v4_bybit_accessibility.json` as durable negative research memory. Exact head `c05404d0f23011747df7d1c19111fac05f09c701` passed Security and Reliability #1875 before expected-head merge as `9e179015c443e9e8eb0467239f68b9a8ea81dffd`.
- The Bybit route must not be repeatedly re-probed unless the deployment/network environment, Bybit access policy, or documented request contract materially changes. Do not proxy around or spoof geography. Do not silently substitute Bybit into Binance V1/V2/V3 fingerprints.

## SAFETY INVARIANTS
No AI opinion, dashboard value, paper P&L, model count, ensemble weight, feature availability, OI status, accessibility probe, historical diagnostic, experiment priority, single OOS result, or single forward result may authorize live BUY/SELL by itself.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, persistence-unsafe, chronology-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real-order capability without explicit user approval plus all canonical gates.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace, or manufacture its history. Paper performance is evidence only.

## SCIENTIFIC RESEARCH DISCIPLINE
- Chronological validation remains development -> validation -> untouched OOS. Genuine forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable fingerprint.
- Never improve headline accuracy through lookahead, leakage, threshold mining, OOS reuse, survivorship substitution, overlapping observations treated as independent, or fabricated evidence.
- Simultaneous cross-symbol crypto outcomes are not automatically independent; family/model count is not independence.
- Never backfill unavailable timestamp-sensitive OI, funding, order-flow, cross-sectional, leadership, or other prospective features merely to improve coverage.
- Realistic fees, spread, slippage, funding/carry, liquidity, and execution assumptions remain mandatory.
- Robustness requires parameter perturbation, regime stability, conservative execution-cost stress, search-breadth/multiple-testing protection, and genuine forward confirmation.
- Repeated or disproven hypotheses receive research-memory penalties rather than blind recycling. Re-test only after a material premise/environment change.
- Research scheduling should favor expected information gain and plausible after-cost signal-quality improvement, discounted for compute cost, redundancy, data weakness, and overfitting risk.
- Production WAIT/abstention may be diagnosed but never weakened merely to generate more trades.
- Accessibility/source diagnostics are infrastructure evidence only. Never reinterpret them as alpha, use them to tune thresholds, or pool them with predictive/OOS/forward evidence.
- Every alternative OI venue requires its own bounded accessibility check and separately predeclared immutable venue/timestamp/provenance fingerprint before predictive testing.
- No self-improvement cycle may force paid calls, bypass provider budget/cooldown controls, raise physical concurrency, or create production authority.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 market/execution realism: complete.
- ACC-002 cross-asset rank research: fail-closed before untouched OOS because historical coverage remains insufficient. Never lower `minimum_subset_coverage=0.80`, the two-supported-subset requirement, Top-N ordering, required history, or untouched-OOS rules merely to pass.
- ACC-003 through ACC-014 safety/validation layers: complete.
- Selective precision, economic meta-WAIT, regime x strategy, calibration, selective-WAIT fusion, cross-sectional/residual, microstructure veto, ensemble diversity, and error attribution remain governed research-only diagnostics until their own evidence gates are satisfied.
- FFriZz V1/V2/V3 evidence may not be pooled. V4 is not currently a predictive challenger; the tested Bybit source is inaccessible from the current environment and is recorded as such.

## CURRENT LIVE / OPERATIONAL FACTS
- Binance historical OI: HTTP 451 from the current Render environment; per-run redundant-request circuit breaker is integrated.
- Bybit historical OI accessibility probe: HTTP 403 from the current Render research environment; one bounded probe, zero points. Do not repeatedly probe without a material premise change.
- FFriZz remains research/shadow only. Recent sampled all-WAIT cycles with `unexpected_wait_state=0` are legitimate abstention, not permission to loosen thresholds.
- Eligible FFriZz V1 prospective persistence still requires the canonical privileged prediction-ledger configuration. Never commit credentials, substitute an anonymous key, weaken RLS, or create an unauthenticated bypass.
- ACC-002 remains blocked by `InsufficientHistory`; untouched OOS remains unopened.
- Provider/model budget exhaustion remains fail-closed and may not be bypassed by automated development.
- GitHub branch protection is not relied upon as the safety mechanism: isolated branch, exact-head Security and Reliability, current-main compatibility review, and expected-head merge protection are mandatory.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection, and bounded concurrency. No paid feed/service/compute without explicit approval.

Do not expand worker count merely for appearance. Prefer experiments that materially increase information value per unit of compute. Blind indicator permutations, duplicate ensemble members, pure repeat `InsufficientHistory` investigations, and repeated falsified hypotheses without changed premises remain deprioritized.

## CURRENT OPEN DEVELOPMENT / NEXT PRIORITIES
1. Treat both tested OI routes as unavailable from the current Render environment: Binance = 451, Bybit = 403. Do not bypass restrictions, silently change venue, or repeatedly probe unchanged blocked routes.
2. Do not change V3 causal timestamp semantics merely because OI is unavailable. Availability and predictive usefulness are separate questions.
3. Before adding another OI venue, first determine whether an already-accessible, free/public, timestamp-defensible source or a non-OI feature experiment has higher expected information value. Any new venue must begin with a bounded accessibility/provenance test and separate fingerprint.
4. Restore the coordinator's canonical prediction-ledger configuration through authorized environment configuration before treating FFriZz V1 prospective evidence accumulation as operational. Then verify eligible persisted rows read-only before drawing conclusions.
5. Let valid prospective rows resolve naturally. Compare exact fingerprints using non-overlapping full-horizon evidence, realistic costs, calibration, multiple-testing protection, regime attribution, and untouched OOS. No unresolved-row tuning or promotion.
6. Continue diagnosing resolved primary-system false positives/false negatives, calibration, regime behavior, cross-sectional information, execution realism, market-data failures, paper rejection attribution, and worker experiment outcomes. Rank new tests by expected information gain and expected after-cost improvement rather than novelty.
7. Treat cache/network optimization as throughput research only; preserve exact request identity, freshness, completed-candle chronology, and provenance.
8. Keep ACC-002 blocked while failures remain pure `InsufficientHistory`.
9. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, authentic paper baseline/history immutable, heavy concurrency bounded, and recurring infrastructure <= USD 30/month.
10. Every integration remains: isolated branch -> regression tests where applicable -> exact-head Security and Reliability -> current-main compatibility -> expected-head merge -> AI_STATE.md synchronization -> post-deploy health verification when applicable.
