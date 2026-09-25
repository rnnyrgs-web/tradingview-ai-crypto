# Weekly historical source census — 2026-09-25

**Decision: retain this source as a candidate input, but do not treat a latest Git
snapshot as a complete historical asset universe.** The frozen 52-week census
found a severe source-file gap. This is a useful data falsification, not a strategy
result or permission to open 2x labels.

## Scope and provenance

Existing task #812 / PR #813, supporting #505/#514/#519. Main base:
`1860f917c829ee5db4f4cd36404bf9702b6b680a`. The complete Monday grid, source-selection
rule and no-replacement policy were frozen in issue comment `5825179094` before
weekly acquisition. A single December commit lookup was an earlier feasibility
probe, disclosed in the freeze; no inventory or outcome was selected from it.

For each Monday from 2021-01-04 through 2021-12-27, the preserved fork was used
only to discover a commit ID. Every exact ID resolved in original upstream
`coinmetrics/data`. Original root and csv trees were retained and their Git
object hashes independently recomputed. All direct asset CSVs were retained;
only the metric dictionary was excluded. Source CSV values were not downloaded.

Unsigned committer times are **not authenticated historical public availability**.
Tree identity is not a trusted remote-acquisition attestation. These observations
remain quarantined and cannot enter canonical Cohort 001 without its existing
source, chronology, identity, membership and tradability gates.

## Actual measurements

| Quantity | Result |
|---|---:|
| Frozen weekly cutoffs | 52 |
| Upstream-resolved, hash-verified tree pairs | 52 |
| Acquisition / tree-validation failures | 0 |
| Source-symbol/week metadata rows | 5,436 |
| Unique observed source symbols | 115 |
| Source symbols present in all 52 selected snapshots | 4 |
| Minimum / maximum weekly asset files | 4 / 112 |
| First / last weekly asset files | 100 / 106 |
| Distinct source CSV blob identities declared by trees | 5,125 |
| Adjacent-week source-file appearance occurrences | 112 |
| Adjacent-week source-file disappearance occurrences | 106 |
| Maximum selected commit age at cutoff | 105.580556 hours |
| Admitted cohort snapshots / 2x events / controls | 0 / 0 / 0 |
| Precursor tests / qualified current candidates | 0 / 0 |

Blob counts and sizes describe metadata, not acquired CSV bytes. The 5,436 rows
are source-presence observations, not independent market observations or events.

**FACT:** the 2021-03-01 selection is upstream commit
`4b17801899969c45566c232650c61865373af6c5`, whose csv tree contains only `aave`,
`ada`, `ant` and `bal`. The prior frozen week has 100 files; the next has 104.
The same four source symbols are the full 52-week intersection.

A separate post-census metadata diagnostic checked the selected commit's direct
parent, `f6af41f37561712a62aa1d33d01be76a64c7c166` (2021-02-27): its csv tree has
100 asset files. The retained `gap_parent_probe.json` records this probe. The
parent does **not** replace the frozen selected snapshot or supply missing values.

**INFERENCE:** the four-file snapshot is consistent with an incomplete source
publication. Its precise cause is unknown. A naive snapshot-presence rule would
wrongly turn a source gap into 96 asset removals. Conversely, silently carrying
forward prior values would conceal the gap and potentially violate freshness.

**FACT:** other transitions include `bnb_mainnet` disappearing and reappearing,
new `bnb_bc` / `bnb_eth` / `usdt_omni` source names, and later removal of several
legacy files. None is authenticated venue listing/delisting or canonical identity
continuity. The April 12 selection is over four days old; no value freshness is
established by the presence of its tree.

## What this changes about the research decision

The earlier one-date result (91 fresh positive supply/cap pairs) cannot be
extrapolated into 52 complete weekly PIT feature panels. We now have concrete
longitudinal evidence against that assumption. The frozen requirement of at
least 12 assets with 52 decisions each is not satisfied by this source inventory
alone. It is not legitimate to remove the bad week or count the four surviving
files as the historical trading universe.

The next source decision is to predeclare and independently review whether
asset-specific prior published versions can be used, with explicit source/value
freshness, omission semantics and historical-publication evidence. Only then
acquire the required cap/supply values. Keep original failures and missingness;
no future snapshot replacement or current-ticker splice. Binance historical
membership, failed/delisted coverage, identity and quote-native liquidity remain
separate prerequisites owned by the existing cohort work.

## Strategy factory and current candidates

This cycle opened **zero new strategy outcomes**. ETH Tuesday
`EXT-ETH-TUESDAY-DRIFT-001-v1` remains untested: review attempts #817, #819 and #822
all returned WAIT_RETRYABLE. The three-attempt allowance for this exact request
is exhausted; no duplicate request or retry-budget increase was made. PR #820's
provider repair has green exact-head CI but is not integrated. A local read-only
review cannot substitute for the canonical independent-review/admission boundary.

No base rate, lift, precision@K, PR-AUC or prospective return is estimable from
this source inventory. **NO QUALIFIED CURRENT 2X CANDIDATE.**

The single highest-value strategy action remains separate review/integration of
the existing reviewer repair, followed by an explicitly authorized recovery of
the exhausted review request and exact-identity admission of the frozen ETH
screen. Provider capacity remains unproven; do not claim the patch guarantees
successful review or a profitable result. Broker/live trading remains OFF.

## Reproduction

The default calculation is entirely offline:

```sh
python research_data/coinmetrics_2021_census/weekly/reproduce.py
PYTHONPATH=. python -m pytest -q tests/test_coinmetrics_weekly_inventory.py
```

`acquisition.json.gz` retains exact request URLs and source JSON for all 52 decisions.
`freeze.json` preserves the complete grid. `results.json.gz` retains per-week files,
identities, transitions, failures and aggregate counts. Each result records the
SHA-256 of its freeze, input and reproducer. Reacquisition must use those exact
URLs/objects and stay separate from the retained evidence; it grants no new
historical-publication authority. No production code, schema, workflow, research
gate or rejected fingerprint was changed.

The large source/result documents use deterministic gzip packaging to keep the
review diff readable; decompress to inspect every retained row. `summary.json`
exposes the full numerical summary directly on GitHub. Packaging changes no input
JSON bytes, source identity, numerical observation or scientific authority.
