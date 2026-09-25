# Completed AVA evidence milestone — draft review handoff

This publication preserves the completed offline analysis of eight responses collected on September 25, 2026, at 07:10 UTC. It adds no market observations. Read [FINDINGS.md](FINDINGS.md) for the reserve reconciliation, source limitations, nine predeclared liquidity scenarios and research-only conclusion.

Milestone: **COMPLETED_SAVED_EVIDENCE_ANALYSIS / DRAFT_REVIEW**. Scientific questions: **UNRESOLVED**. Conclusion: **RESEARCH_ONLY**. Independent review and exact-head Security and Reliability remain required before any Lead integration. This is not scientific completion, a purchase verification, a strategy admission or permission to trade. No provider-review call is part of this publication.

Role: Current 2x evidence investigator. Task: `AVA-DEMAND-SUPPLY-LIQUIDITY-001`. Existing isolated branch: `auto/current-2x-evidence/AVA-DEMAND-SUPPLY-LIQUIDITY-001`. Refreshed publication base remains `1860f917c829ee5db4f4cd36404bf9702b6b680a`; it is already an ancestor of this branch. Parent: [#856](https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/856), especially [assignment](https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/856#issuecomment-5828094356) and [claim](https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/856#issuecomment-5828293500). No canonical ownership/queue file is changed. The actual publication commit, PR number and CI status are provided by Git/GitHub, not prefilled into historical acquisition receipts.

The identified reserve holds 369,881.04 AVA according to the saved indexer, reconciled to two exchange-labeled withdrawals. New market buying is not established. Both issuer supply endpoints report 74,373,863 AVA, leaving the claimed reserve exclusion unreconciled. The three venue books support bounded gross-friction measurements; fee-adjusted execution, durable capacity and future fills remain unknown.

The single scientific next observation remains an independently attestable reconciliation tying the inaugural deposits to separately funded purchases, starting exchange inventory and distinct Foundation replenishment. It is a handoff suggestion, not a newly launched investigation or scheduled collection. Wider supply/distribution/recycling and locked-balance evidence remain unresolved. The next publication step is independent review of this frozen milestone.

**Preservation.**

- `raw/*.body`: eight byte-original API responses; all original hashes and timestamps retained.
- `public_receipts/*.receipt.json`: publication copies of the acquisition receipts. Only Kraken's two case-variant `Set-Cookie` header values are redacted. Body hashes, event/provider/collection/write clocks and all other acquisition fields are unchanged. The original receipts remain locally preserved under `raw/` and are deliberately not committed. The [receipt manifest](receipt_publication_manifest.json) binds both originals and public copies by hash. Redaction never changes the original body hash.
- `analysis_verified.json`, `verification.json`, `inventory.csv`, `CHECKPOINT.json`: unchanged recovery outputs with original analysis/verification times. Absolute inventory paths document the collection workspace; reproduction resolves body basenames relative to this directory.
- `FINDINGS_RECOVERY.md`: byte-identical report covered by the original checkpoint hash. Its references to local original receipts and pre-publication status are historical. Use the public receipt directory when reviewing remotely.
- `FINDINGS.md`: same research conclusions with a publication annotation and public-receipt link. `analysis.json` remains the preserved, superseded preliminary derived result; use `analysis_verified.json`.
- The original acquisition helper remains locally preserved and uncommitted. No data acquisition is needed or performed for reproduction.

**Reproduction requires only Python's standard library.** From the repository root:

```text
python -B docs/research/ava-evidence-20260925/analyze_offline.py
python -B docs/research/ava-evidence-20260925/verify_offline.py
```

The first command recomputes every saved supply/transfer/book result and compares it with the frozen analysis, ignoring only the new calculation time and checkout prefix. It does not rewrite results. The second independently uses exact rational arithmetic for the original 192 checks and verifies recovery hashes. Both are read-only, offline and fail explicitly if a check fails, including under Python optimization. No installation, network access, collection or provider credential is required. Publication preparation adds no application dependency, runtime hook or workflow.

Original #856 evidence, protected admission contracts, strategy/forward outcomes, canonical state, prediction ledgers, trading/broker state and billing remain untouched. The worktree is retained for review. This bounded publication ends after reporting the actual commit, draft PR and outstanding review status.
