# Results-first research audit — 2026-09-25

Scope: user-directed quant-research diagnostic, [issue #824](https://github.com/rnnyrgs-web/tradingview-ai-crypto/issues/824), on main `1860f917c829ee5db4f4cd36404bf9702b6b680a`. This report audits repository code, durable research artifacts and current GitHub work. It does not claim a fresh production/database audit. Canonical `AI_STATE.md` is dated September 20; newer queue/PR evidence was checked separately. No canonical state was rewritten.

## 1. MOST IMPORTANT DEFICIENCIES FOUND

**The scarce output is completed, scientifically admissible economic comparisons, not hypotheses or workers.** New strategy/cohort contracts exist, but current work still depends on exact scientific admission and trusted source qualification. A superficially favorable difference between two losing strategies is also too easily mistaken for a reusable component. This run directly measures that last problem.

| Area audited | Evidence and deficiency | Priority / consequence |
|---|---|---|
| Hypothesis generation, discovery breadth, economic rationale | `strategy_discovery_queue.json`, the Cohort-001 baseline plan and external-replication PRs contain distinct carry, residual reversion, auction, flow and calendar mechanisms. The older quant-science factory mostly enriches resolved-error hypotheses with design metadata; queue breadth is not completed discovery. | High: finish admitted simple screens; extra parameter grids or hypothesis prose have low marginal value. |
| Historical data and point-in-time correctness | Residual momentum is evidence-limited by survivor membership; squeeze retention is blocked on the exact historical forced-flow contract. Current listings cannot repair either. | High: source qualification, including inactive assets, precedes broader cross-sectional discovery. |
| Costs, slippage, order execution, microstructure and liquidity | Archived liquidity-reversal economics use completed-hour signal, next-open entry and fixed six-hour exit with uniform 20/40/60-bps screening costs. They are not observed fills or capital-normalized NAV. | High for any survivor; do not spend on finer execution to rescue a strategy already negative before costs in training. |
| Chronology, walk-forward and untouched OOS | Frozen negative screens stop pre-OOS. No validated survivor is evidenced here. The old `strategy_families.py` evaluates holdout and sensitivity variants; its exploratory machinery must not substitute for current admission/selection rules. | Preserve locks; do not execute legacy holdout paths to manufacture throughput. Full walk-forward remains necessary after legitimate survival. |
| Multiple testing, overlap and false-alpha defense | Project identity/multiplicity protections exist. Raw cross-asset trade counts still are not independent evidence; a baseline comparison can differ on very few actual opportunities. | **Selected diagnostic:** identify marginal evidence support before learning from a component. No fresh p-value or significance allowance. |
| Robustness, regime and cross-asset validation | Frozen screens include assets, regimes and chronological halves, but the relevant comparison may be concentrated in one date despite large total sample counts. | High: apply influence/ablation checks to the difference itself, not just headline strategy performance. |
| Cross-engine replication | Engine adapters and an open evidence-integrity repair (#394) exist. No new independently replicated profitable result was established by this audit. | Validate exact survivor identity/data/fills; translating one losing hypothesis through more engines does not create alpha. |
| Feature selection, ML and statistical modeling | No authenticated positive incremental baseline or qualified 2x training denominator is established in inspected evidence. | Defer complex ML/feature search until simple frozen baselines and sufficient valid independent data exist. |
| Funding, OI, basis and liquidations | Basis/funding fingerprints are terminally rejected; the historical liquidation contract is genuinely blocked. Delta-carry has a separate data-qualified path in active work. | Test materially different carry economics only through its exact data contract; do not recycle rejected directional funding/basis signals. |
| Whale/on-chain/exchange flows | Current precursor/source designs acknowledge missing timestamp-defensible flow and denominator fields; no validated incremental 2x lift is reported. | Exact historical publication and asset/venue identity matter more than adding current flow feeds. |
| Macro liquidity, rates/USD, fiat/stablecoin flows | Money Intelligence records mechanisms, alternatives and source narratives. These generate hypotheses; they are not historical 2x predictive validation. | Freeze measurable surprises/transmission variables and controls before using them as predictors. |
| Tokenomics/unlocks, cap/float, usage/revenue | Supply/cap census #813 has useful coverage observations, but its unsigned Git timestamps do not prove historical public availability and omissions are not delistings. | Finish trusted PIT denominators and missingness semantics; more stories cannot replace them. No new paid-data recommendation yet. |
| Catalysts/news, attention/narrative and manipulation | `big_move_lab.json` and precursor hypotheses distinguish facts/inference/unknowns and require controls. They do not provide an admitted winner/non-winner denominator. | Keep as hypothesis sources until frozen historical comparisons exist; no retrospective explanation becomes an early prediction. |
| Historical 2x events, matched controls and rare events | Cohort preflight requires 12 assets / 624 snapshots / 52 decisions per asset plus trusted membership, age, price, cap/float, liquidity and classification. #813 reports zero admitted snapshots/events/controls. | The high-value 2x bottleneck is an authentic, survivor-safe denominator. Case studies alone cannot estimate base rate. |
| Calibration, PR-AUC, top-k precision, false positives and current ranking | There is no qualified event/control cohort in inspected artifacts; inferential floor is 20 independent 2x events. | These metrics are **unavailable**, not zero. No calibrated current 2x candidate can be defended. |
| Throughput, compute/data and prioritization | Frozen ETH #790 and Cohort #515/#602 are waiting on their owned review/admission paths. #820 already owns the bounded reviewer-provider repair; #813 owns the supply census. | Avoid duplicate work. Do not add workers, orchestration or spending to a scientific-admission bottleneck. |
| Failed-hypothesis learning | Rejected fingerprints are preserved. The liquidity filter's favorable validation average lacked a reconciliation of shared and differing executions. | **Implemented:** expose composition and episode dependence so unsupported component reuse is less likely. |

Action ranking uses ordinal information gain/readiness/cost judgments, not invented probabilities: (1) complete the already-owned review/admission path to #790; (2) finish already-owned historical cohort source qualification; (3) implement this small, immediately executable baseline-evidence diagnostic; (4) defer ML, new feeds, dashboards and extra workers. The first two have other active owners; this run takes the highest-value clean independent action.

## 2. UPGRADES ACTUALLY IMPLEMENTED

`research_baseline_composition.py` adds an offline, reusable comparison of already-consumed trade records:

- Exact instrument/direction/signal/entry/exit matching, duplicate rejection and strict finite-number/chronology checks. Shared identities with different gross returns fail closed.
- Candidate/common/baseline-only decomposition of both mean trade-label return and additive label sums. Unequal sample sizes explicitly retain the shared-trade reweighting term.
- Conservative transitive overlap components across every asset, including shared endpoints. Components are **not asserted statistically independent**.
- Leave-one-differing-component-out arithmetic with both arms removed together; empty-arm means remain unknown. This diagnoses influence, not a permitted exclusion rule.
- A loader restricted to canonical `evidence.json.gz` before any read, with exact compressed-byte hash validation before decompression and original payload hash validation afterward. It never opens `dataset.json.gz`, recomputes signals, searches thresholds, analyzes sensitivity outcomes or accesses fresh/OOS/forward outcomes. The retained evidence JSON is decoded in full for its original payload hash verification; analysis consumes primary/baseline trade lists only. Independent review caught the initial check-after-read flaw; three synthetic boundary attacks failed before repair and pass afterward.
- Deterministic JSON output and exclusive output creation to prevent accidental overwriting.

No production behavior, strategy fingerprint, paper ledger, canonical gate, infrastructure or budget changes. This is implemented research machinery awaiting separate PR integration, not a deployed research policy change.

## 3. MEASURED EFFECT ON RESEARCH CAPABILITY

Previously the available summary compared 425 versus 443 training labels and 123 versus 124 validation labels. The diagnostic reconciles all **1,115 arm-label references into 575 unique executed-label identities**, making the actual sources of the difference visible.

| Diagnostic | Training | Validation |
|---|---:|---:|
| Candidate labels | 425 | 123 |
| Baseline labels | 443 | 124 |
| Identical shared labels | 418 | 122 |
| Candidate-only labels | 7 | 1 |
| Baseline-only labels | 25 | 2 |
| Union temporal components | 234 | 66 |
| Components containing a difference | 18 | 2 |

This is a measurable improvement in evidence attribution. It is **not** a measured increase in profitability, predictive accuracy, admitted experiments/day, or independent sample size. New market acquisitions: zero. New historical outcome windows: zero. New strategy tests: zero. Two retrospective segment comparisons were completed.

## 4. NEW SCIENTIFIC RESULTS PRODUCED

The frozen liquidity filter's apparent validation benefit is fragile composition evidence:

| Mean trade-label economics, bps | Training | Validation |
|---|---:|---:|
| Candidate gross | -28.870176 | +14.524374 |
| Candidate net, 20-bps cost | -48.870176 | -5.475626 |
| Baseline net, 20-bps cost | -47.642119 | -7.074560 |
| Candidate minus baseline mean | **-1.228057** | **+1.598934** |
| Shared-trade payoff difference | 0 | 0 |
| Minimum difference after deleting one differing component | -2.598114 | **-0.378795** |

All 122 shared validation trades have exactly the same gross returns. The three differing labels occupy two components, **both on March 4, 2026**. Removing the 08:00–15:00 UTC component from both arms changes the validation difference from +1.598934 to -0.378795 bps. Removing the other differing component (16:00–22:00) gives +2.001651 bps. The training difference remains negative under all 18 analogous deletions.

The code explains why this is not simply a subset filter: each arm independently advances to `exit_index + 1` after a trade. Rejecting one early signal can admit a later signal in the candidate arm that the baseline skips due to its occupied holding window. The retained evidence contains exactly such a validation timing displacement. No missing counterfactual return was reconstructed.

At 20-bps costs the validation mean difference decomposes into -0.039703 bps shared-trade reweighting, -0.552425 bps candidate-only contribution, and +2.191062 bps from subtracting baseline-only outcomes. A constant cost cancels from the two **means**, so the relative +1.598934 bps remains at 40/60-bps scenarios while both strategies become more negative. Lower costs cannot cure the negative training gross mean.

These are retrospective arithmetic falsifiers on consumed evidence, not an additional OOS result, p-value, confidence interval or proof of the filter's true causal effect. Two same-day components certainly do not demonstrate regime-robust incremental alpha. Deletion results must not become a rule that excludes March 4 or any other date.

## 5. CURRENT BEST STRATEGY EVIDENCE

**No validated profitable strategy is established.** Canonical rejected lead/lag validation is -113.69 bps at 3x costs with PF 0.097. The liquidity candidate above fails at base costs in both segments. Other rejected mechanisms remain rejected. Open #815 reports BTC candle-clock validation gross +0.0558 bps versus 24-bps assumed costs; that is explicitly unadmitted negative evidence and was not recomputed here.

The closest inspected path to a fresh authorized answer is the separately owned frozen ETH Tuesday screen #790. Its absence of a completed admitted result cannot be called a promising strategy. OOS/forward stay locked and broker/trading authority stays off.

## 6. CURRENT BEST 2X EVIDENCE

**No qualified current 2x candidate.** The strongest recent data progress inspected is #813's supply/cap coverage census and 52 weekly source inventories, explicitly quarantined rather than admitted PIT evidence. Its March 1 four-file source snapshot versus a 100-file parent also demonstrates why missing publication rows cannot be treated as delistings/non-winners. That work remains with its existing owner.

This run produced zero admitted cohort snapshots, 2x labels, matched controls, precursor tests or calibrated probabilities. No raw base rate, OOS lift, PR-AUC or top-k precision can be truthfully reported for a qualified process yet. The next 2x dependency is authentic membership/age/publication-qualified features followed by frozen outcome-blind controls and only then labels.

## 7. WHAT WAS FALSIFIED/REJECTED

- The reading that +1.60-bps validation improvement is supported by 123 distinct marginal trade opportunities: only three labels differ, in two same-day episodes.
- Robustness of that observed improvement to removal of either differing holding component: one removal reverses its sign.
- The reading that fewer trades necessarily mean a higher average return: training additive label sums improve while mean return worsens. Additive label sums are not NAV.
- A lower-cost rescue of this exact strategy: training gross expectancy is already negative; the frozen rejection remains unchanged.

This diagnostic does not terminally reject a broad economic family, create a new canonical rejection, or prove the unknown population effect is zero. New successors still require materially different frozen hypotheses and fresh valid evidence.

## 8. THE SINGLE HIGHEST-VALUE NEXT EXPERIMENT

**Execute the already-frozen, separately owned ETH Tuesday #790 Stage-1 screen once its legitimate exact-identity review/admission gates clear.** Its fixed schedule and 68 planned sessions make it closer to a genuine new falsifiable economic result than adding another strategy framework. Reject on its frozen cost/tail/power gates; run the predeclared baseline gauntlet only for a legitimate survivor. Do not take over its owner, tune it, or open it early.

### Reproduction and verification

From this repository, using its existing dependencies:

```text
python -B -m pytest tests/test_research_baseline_composition.py -q -p no:cacheprovider
python -B research_baseline_composition.py --evidence orchestration/evidence/liquidity_meanrev_001_cache/evidence.json.gz --output NEW_RESULT_PATH.json
```

Output must parse identically to `results.json`. The source payload remains `8630b22e7c2a8e0ef0e44fad2ea0fcd30395c9e2b2ef99bc08c98afb6e968f4e`; contract and dataset-reference identities are retained in the result. Synthetic tests were observed failing before implementation; 28 focused tests plus 27 existing profitability-learning tests passed. Full Windows collection stopped with 71 errors because existing modules import Linux-only `fcntl`; no shim or skipped replacement suite is offered as equivalent full verification. Exact-head Linux Security and Reliability and separate review are reported in the PR.

Role: quant-research, user-directed diagnostic. Task: #824. Branch: `codex/research-baseline-composition`; the existing `agent/quant-research` branch was left untouched. Status: PR_OPEN after publication, never self-merged. The named next experiment above remains independently owned. Canonical coordination and rejected memory are unchanged.
