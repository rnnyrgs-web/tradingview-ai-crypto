# Sources, timestamps and limitations

Research cutoff: **2026-09-25T05:20:00Z**. Every external source was acquired after the local cutoff was fixed. Native event/as-of dates at or before cutoff are required for cutoff claims. This is retrospective acquisition for a current research snapshot, not trusted point-in-time capture. The source pages below were accessed on September 25, 2026 during this run; precise per-page retrieval seconds were not retained by the web tool. An access date or a page's publication label is not a historical revision attestation.

## Retained numeric sources

|Source|Data retained|Timestamp convention / limitation|
|---|---|---|
|CoinMarketCap connector quote responses|`quotes.json`, `quotes2.json`: full tool payloads, including headers, source-as-of times, quotes, circulation, reported cap/FDV/24h volume|Selected references have source times 05:19–05:20 UTC. Exact retrieval seconds were not retained; retrieval occurred after cutoff. Provider numbers are not independently audited. [Provider definitions](https://coinmarketcap.com/api/documentation/v1/)|
|CoinMarketCap global/narrative responses|`global.json`, `narratives.json`|Global response retained for audit but excluded from decisions because volume/range/derivatives fields conflict. Narrative response used only for discovery; no inference of fund flows from a narrative rank|
|Kraken public OHLC API|12 `*_daily.json` files, for ten investigated assets plus BTC/XBT and ETH|Receipt URL, actual retrieval times, server date and hash retained. Only candles ending by cutoff retained; last complete day ends 00:00 UTC. Up to 720 recent bars available; not a survivor-safe universe. [OHLC documentation](https://docs.kraken.com/api-reference/market-data/get-ohlc-data)|
|Kraken AVAUSD five-minute API|`AVA_cutoff_reference.json`|05:15–05:20 candle, retrieved 05:26:22.894590 UTC; only four trades. Source URL and bar retained; no whole-response hash was recorded for this one reference|
|Hyperliquid public fundingHistory API|Nine `*_funding.json` files and `funding_summary.json`|Cutoff-bounded request body, timestamps and response hash retained. 336 observations per asset; latest at 05:00:00.040 UTC. Single venue; premium is not dated futures basis. [API documentation](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals)|
|DefiLlama fee summaries|Six daily revenue/holder-revenue files, 60 completed days each|Receipt URL/time, server date and original-response hash retained; only pre-cutoff completed-day subsets saved. Daily label is interpreted as UTC day start. Zero holder revenue may be an adapter/coverage limitation. [Aave](https://defillama.com/protocol/aave), [Hyperliquid](https://defillama.com/protocol/hyperliquid), [ether.fi](https://defillama.com/protocol/ether.fi)|
|DefiLlama stablecoin history, ID 146|`USDe_history.json`, latest 40 eligible dated points|Latest point labeled September 25 00:00 UTC, retrieved 05:27:14.528040 UTC. Supply changes are not necessarily external net fiat inflow. [USDe](https://defillama.com/stablecoin/ethena-usde)|

Collector receipts contain the available actual retrieval clock; this file does not invent missing clocks. Retained subsets are not raw full-provider archives. A SHA of an omitted full response can identify bytes if recovered, but cannot recreate or independently validate them. The final file hashes in `VALIDATION.json` identify exactly the retained evidence used. CoinMarketCap AVA/USDe quotes arriving with source times later than cutoff and undated technical-analysis outputs were not used in the comparison.

## Primary and economic sources used

The report links each material claim directly. Dates below are source publication/event labels where available; undated documentation is mechanism context with unknown historical revision state.

|Asset/context|Source and date|Use / limitation|
|---|---|---|
|AVA|[Travala reserve announcement](https://www.travala.com/blog/travala-launches-ava-strategic-reserve/), Sep 23, 2026|Issuer claim of inaugural match and future discretion, not independently audited wallet balances|
|AVA|[AVA 2.0 overview](https://www.avafoundation.org/ava-2-0-overview/) and [linked detailed release sheet](https://docs.google.com/spreadsheets/d/1JYZKAV9FHRRAWlnwfAjqg6InSX5jiABFfKGkM2ItaaU/edit), undated/mutable|Detailed sheet: Aug 1, 2026 gross supply 74,373,863; Nov 1, 2026 planned issuance 1,083,073. Overview's annual total differs by one token. Category subtotals may round. Not a verified circulating-float measure|
|AVA|[Kraken listing](https://blog.kraken.com/product/asset-listings/ava-is-available-for-trading), May 15, 2026|Credible venue and asset identity; not a new September catalyst|
|ENA|[Governance proposal and Risk Committee analysis](https://gov.ethenafoundation.com/t/ena-fee-switch-activation/830), Aug 27, 2026|Threshold/routing and contrary economics. Independent vote/transaction execution not verified. Revenue backtest is not a 2x event/control study|
|ONDO|[Intelligent Portfolios](https://ondo.finance/blog/introducing-ondo-intelligent-portfolios), Sep 24, 2026; [announcement archive](https://ondo.finance/blog), Sep 22 NEAR integration|Actual product exposure differs from ONDO-token value capture; archive is mutable|
|AAVE|[Arc deployment thread](https://governance.aave.com/t/arfc-deploy-aave-v4-on-arc/25170), Sep 16 activation post; [V4 cap update](https://governance.aave.com/t/arfc-aave-v4-activation-on-ethereum-mainnet/24293/51), Sep 16|Activation and deposit/cap observations; proposal is not executed future growth|
|AAVE|[Buyback budget adjustment](https://governance.aave.com/t/arfc-buyback-program-budget-adjustment/24229), Mar 4, 2026|Historical caution only; does not establish current exact executed buyback budget|
|HYPE|[Fees documentation](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees), undated|Mechanism and fee recipients, not guarantee of future cash flow|
|HYPE|[SEC-filed holder annual report](https://www.sec.gov/Archives/edgar/data/1682639/000110465926055729/tm2612201d2_ars.pdf), 2026 filing|Contributor ownership/vesting risk; exact forward unlock amounts not verified here|
|ETHFI|[Official buyback documentation](https://etherfi.gitbook.io/gov/ethfi-buyback-program), undated|Routing/distribution; not all repurchases are burns|
|ETHFI|[Economic review](https://alearesearch.io/newsletters/ethfis-buyback-vote), Sep 1, 2026|Card spending versus actual revenue and market growth; proposal illustrations are not realized purchases|
|ETHFI|[Project-submitted vesting filing](https://blockworks.com/token-transparency/filing/ether-fi), dated schedules through Feb 18, 2027|Conflict requiring reconciliation with quote circulation; not independent custody verification|
|SUI|[Token schedule](https://www.sui.io/token-schedule), undated; [Phantom notice](https://help.phantom.com/articles/ending-support-for-sui-in-phantom-53868478441491), Sep 24 end-of-support event|Release discretion and distribution headwind, not proof of token demand collapsing|
|TAO|[Emissions](https://www.bittensor.com/docs/concepts/emissions), undated|Halving/rate context, not verified current paid demand|
|AVAX|[Architecture docs](https://build.avax.network/), undated; [Aave V4 launch](https://aave.com/blog/aave-v4-live-avalanche), Jul 15, 2026|Gas/value-capture caveat and already-known integration|
|Macro|[Federal Reserve statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm), Sep 16, 2026|Restrictive rate context; no forecast of future policy|

No wholesale third-party articles were copied. Sources support specific facts; scenario arithmetic, comparison and tier judgments are this report's reasoning. Mechanism documentation without authenticated revision history cannot satisfy strict PIT evidence requirements. Unresolved unlock disagreement is retained as missing evidence rather than resolved by picking the most bullish number.

## Project-state sources and ownership

Startup used current GitHub `main` and then synchronized the isolated branch to `1860f917c829ee5db4f4cd36404bf9702b6b680a`. Read `AI_STATE.md`, `AGENTS.md`, `docs/CHATGPT_SPECIALISTS.md`, `docs/MULTI_ENGINE_PROTOCOL.md`, specialist coordination plus overrides, and validated the quant-research queue through the module entry point. Main's summary is supplemented by newer issue comments, not silently replaced with memory.

Read [#505](https://github.com/rnnyrgs-web/tradingview-ai-crypto/issues/505), [#506](https://github.com/rnnyrgs-web/tradingview-ai-crypto/issues/506), [#514](https://github.com/rnnyrgs-web/tradingview-ai-crypto/issues/514), [#519](https://github.com/rnnyrgs-web/tradingview-ai-crypto/issues/519), [#694](https://github.com/rnnyrgs-web/tradingview-ai-crypto/issues/694), newer metadata work [#812](https://github.com/rnnyrgs-web/tradingview-ai-crypto/issues/812)/[#813](https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/813), and relevant active PRs including [#553](https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/553) (prospective research framework), [#433](https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/433) (historical lab) and [#786](https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/786) (September 24 Money Intelligence). #813 was inspected at head `db5a2e7d5a8cb844b857408980abd1e2c45a420b` as a draft; its diagnostics are neither independently reproduced nor admitted event/control evidence in this run.

This user-directed sprint owns only its timestamped research folder. It does not claim `COORD-DISC-QUANT-003`, duplicate the historical cohort builder, create another prospective framework or edit canonical coordination/state. No automatic escalation of tiers or task priority follows from this report.

The pre-publication refresh also inspected open [#852](https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/852), head `a0c72b1dc7e92fd2be6b3ebb1e41ff38a75e6bc1`: its squeeze inventory repair explicitly separates structural readiness from trusted source authority. It adds no admitted outcomes or current candidate evidence and does not overlap this folder. Refreshed main remained at the base SHA above.
