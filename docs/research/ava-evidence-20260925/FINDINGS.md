# AVA: reserve custody verified; incremental market buying remains unverified

Publication note: this completed evidence milestone is submitted for draft-PR review. Research conclusion remains RESEARCH_ONLY; unresolved scientific questions remain IN_PROGRESS. See [PUBLICATION.md](PUBLICATION.md). The byte-identical recovery report is preserved in [FINDINGS_RECOVERY.md](FINDINGS_RECOVERY.md); published receipt copies redact cookie values and preserve acquisition fields.

Offline evidence checkpoint, written September 25, 2026. Research status: **RESEARCH_ONLY; broader task IN_PROGRESS**. The saved-data analysis is finished and independently checked; the missing execution and supply observations below remain unresolved. This is not a refreshed market snapshot or a forecast admission.

The strongest new finding is a precise custody reconciliation: two indexed Ethereum transfers total **369,881.04 AVA**, exactly matching the published reserve's indexed balance. Both senders carry Binance labels supplied by Blockscout/OLI. This supports exchange-to-reserve custody movement. It does **not** establish when, whether, at what price, or for whose account those tokens were purchased.

The strongest concrete counterevidence is a reporting inconsistency: the Foundation's total-supply and circulating-supply APIs returned the **same 74,373,863 AVA**, despite the earlier announcement saying reserve tokens are excluded from official circulation. That is an inconsistency requiring reconciliation, not proof that the tokens were sold or that the issuer deliberately misreported them.

**Evidence boundary and identity.** Eight original HTTP response bodies and their receipts were collected September 25 between **07:10:45.417390 and 07:10:55.364371 UTC**. Recovery made no network calls. All eight hashes match the acquisition receipts. Analysis occurred later; the calculation check passed at **07:52:43.977639 UTC**. These observations were not available at #856's earlier frozen cutoff and must not be backdated into it.

The earlier primary-source review established the travel token: AVA Foundation/Travala, Ethereum contract **0xa6c0c097741d55ecd9a3a7def3a8253fd022ceb9**. The saved token response confirms that identity and 18 decimals. Published strategic reserve: **0x7bed1889c21d9eb3560463c14cd74fe29f2d03b6**. Other same-ticker assets are excluded. BNB and Solana versions also exist; their supplies are not added together. Exchange books identify AVA pairs, not deposit contracts; current venue contract mappings were not reacquired in this offline recovery.

**What the reserve history establishes.** Source: [saved Blockscout transfer query](raw/reserve_transfers.body), [receipt](public_receipts/reserve_transfers.receipt.json); [public query URL](https://eth.blockscout.com/api/v2/addresses/0x7bed1889c21d9eb3560463c14cd74fe29f2d03b6/token-transfers?token=0xa6c0c097741d55ecd9a3a7def3a8253fd022ceb9).

| Provider event time, UTC | AVA received | Sender and provider attribution | Block / log | Transaction |
|---|---:|---|---|---|
| 2026-09-21 13:42:11 | 100.00 | 0x21a31ee1afc51d94c2efccaa2092ad1028285549; Binance 15 / hot wallet | 26,026,251 / 37 | [0x5f77…8957](https://eth.blockscout.com/tx/0x5f77bdb6e97efba766014cee7fd07c53cff6243053eaa75da0d2010ac63b8957) |
| 2026-09-21 13:54:35 | 369,781.04 | 0x28c6c06298d514db089934071355e5743bf21d60; Binance 14 / hot wallet | 26,026,313 / 382 | [0xbd2b…a799](https://eth.blockscout.com/tx/0xbd2bc6f038e74e1b5b5f3d60c23ba367e95dbe5da689dd16151fb90efdf1a799) |

Deduplication uses chain ID, token contract, transaction hash and log index. The response contains two unique events, no outgoing event, and `next_page_params: null`. Their net amount equals the independently requested [reserve balance response](raw/reserve_balances.body). This is consistency within one indexer, not two independent chain verifications. The indexer's ingestion head/finality and account-history completeness are UNKNOWN. No full-node receipt or raw log was acquired.

The 100-AVA leg could be a test transfer, but purpose is UNKNOWN. Exchange labels come from the provider, not independently supplied Binance account records. The underlying customer, beneficial ownership before withdrawal, acquisition timing, consideration paid, fee treatment and off-exchange execution are UNKNOWN. Neither transfer is a demonstrated market trade. No reserve-to-exchange transfer appears in the returned history; wider treasury-to-exchange activity was not captured.

Blockscout identifies the recipient as a verified EIP-1167 proxy with implementation **WalletSimple**, address **0xe5DcdC13B628c2df813DB1080367E929c1507Ca0**. This is custody-contract metadata, not a verified irreversible lock. Source code, signer powers and any timelock were not inspected. The observed receipt of existing tokens is not a mint or burn.

**Announcement versus observation.** In the [September 23 announcement](https://www.travala.com/blog/travala-launches-ava-strategic-reserve/), Travala claims a separate 369,881.04-AVA market purchase matching the Foundation's rewards replenishment. It promises not to transfer or sell reserve holdings, says the circulation API excludes them, and reserves discretion to suspend future purchases. The observed deposit amount matches that claim; execution itself remains unverified. Both recorded transfers predate publication. Their economic effect cannot automatically be assigned to announcement day or treated as a future catalyst.

The [primary overview](https://www.avafoundation.org/ava-2-0-overview/) describes stablecoin-funded, USD-equivalent replenishment of incentives wallet **0x75536c6bb2331809ed462896855414e04e4835f4**; token-for-token matching remains an unresolved semantic difference. Incentives fund rewards and liquidity; Smart balances are unlockable. Foundation reserve **0x2054280fde37d9fdcb80003fc0a7fa7bd7f81619** is separate. Current balances and distributions are UNKNOWN.

Neither article's raw HTML was retained among these eight files. Their statements were reviewed earlier in this task; exact browser collection times are not independently preserved. They are attributed context, not newly reacquired evidence. No missing web-click result is relied upon.

**Supply reconciliation, in AVA.** [Total API](https://api.avafoundation.org/ava/total-supply), [circulating API](https://api.avafoundation.org/ava/circulating-supply), [indexed token API](https://eth.blockscout.com/api/v2/tokens/0xa6c0c097741d55ecd9a3a7def3a8253fd022ceb9); exact bytes and URLs are retained in `raw/`.

| Item | Amount | Interpretation |
|---|---:|---|
| Issuer total supply | 74,373,863 | API observation; no native as-of block or timestamp |
| Indexed ERC-20 total | 74,373,863 | Agrees numerically with issuer; not a cross-chain bridge audit |
| Issuer circulating supply | 74,373,863 | Same bytes and ETag as total API; not independent float validation |
| Reserve receipts minus returned outflows | 369,881.04 − 0 | Matches indexed reserve balance |
| Reserve / reported total | 0.49733% | Stock ratio, not demand elasticity or forecast |
| Total minus reserve | 74,003,981.96 | Conditional arithmetic only; not measured circulating supply |
| Reported circulation minus that conditional figure | 369,881.04 | Unreconciled exclusion gap; other adjustments or API lag are UNKNOWN |
| New market buying consistent with these deposits alone | 0 to 369,881.04 | Identification range for the deposited tokens, not a probability interval or bound on all purchases |
| Incremental float reduction attributable to these deposits | 0 to 369,881.04 | Conditional on prior availability and custody restrictions; neither endpoint is established |
| Other treasury, reward and Smart-lock balances; freely tradable float | UNKNOWN | Reported circulation cannot substitute for available inventory |

The purchase range includes zero because existing exchange-held inventory could have been withdrawn. It does not assert that zero was purchased. A net deposit is counted once: the two transfers and the balance are three observations of the same 369,881.04 tokens, not additive demand. The Foundation's claimed matching replenishment is neither independently observed here nor permanently removed; summing both claimed programs as a 739,762.08-AVA permanent sink would be unsupported. Subsequent reserve balance growth alone would still not close the execution gap.

The overview describes a 100-million cap, quarterly issuance through 2033 and annual fourth-year issuance of 4,332,292, allocated 50% incentives / 10% growth / 20% community / 20% Foundation reserve. Its year-three total is one token above the saved APIs, an unresolved rounding/reporting difference. The prior November 1 figure of 1,083,073 is consistent with one quarter of that annual amount; this recovery does not independently verify the dated schedule row or observe future issuance.

If that scheduled tranche occurs, incremental minted supply would be 1,083,073; the portion sold could range from zero to the tranche amount, conditional on distribution and holder actions. Actual sales are UNKNOWN. Existing holders could sell additional inventory, so this is not an upper bound on all selling. The 25,626,137 difference between the stated cap and current API total is long-term headroom, not a 90-day sell forecast. No future buybacks, November mint or reward distribution is simulated as an observation. Market-cap changes do not require equal cash inflows.

**Visible liquidity at the original collection times.** Sizes were declared before acquisition in [PLAN.md](PLAN.md). Buy scenarios sweep asks for a fixed quote budget; sell scenarios sweep bids for `budget / midpoint` AVA. Costs below are basis points relative to the same book's midpoint (100 bp = 1%). They include spread and visible depth, exclude fees, and do not assume USDT equals USD or convert KRW to USD. Venue fees and lot-size/minimum-order rules are UNKNOWN in the saved evidence, so these are continuous-quantity book calculations rather than ready-to-submit orders.

| Venue | Best bid / ask | Spread, bp | Collected UTC, 2026-09-25 | Native book clock |
|---|---|---:|---|---|
| Kraken AVA/USD | 0.2579 / 0.2586 | 27.11 | 07:10:45.417390–46.535757 | No snapshot time; latest level update 07:10:44 |
| Binance AVA/USDT | 0.2583 / 0.2585 | 7.74 | 07:10:46.539388–48.887558 | No snapshot time; update ID 1334117217 |
| Bithumb AVA/KRW | 347 / 349 | 57.47 | 07:10:48.907417–50.457985 | 07:10:47.710; 2.748 seconds before collection end |

| Venue / quote size | Buy cost, bp | Sell cost, bp | Static round-trip friction, bp |
|---|---:|---:|---:|
| Kraken / USD 1,000 | 30.87 | 16.90 | 47.61 |
| Kraken / USD 5,000 | 95.82 | 21.12 | 115.58 |
| Kraken / USD 10,000 | 170.67 | 66.72 | 231.85 |
| Binance / USDT 1,000 | 9.46 | 19.10 | 28.52 |
| Binance / USDT 5,000 | 37.31 | 32.26 | 69.26 |
| Binance / USDT 10,000 | 52.04 | 43.60 | 95.03 |
| Bithumb / KRW 1,000,000 | 28.74 | 28.74 | 57.31 |
| Bithumb / KRW 5,000,000 | 28.74 | 28.74 | 57.31 |
| Bithumb / KRW 10,000,000 | 28.74 | 29.13 | 57.62 |

All nine sizes have full coverage in the returned books. This is not an assertion of actual fills. Round-trip friction hypothetically sells the *bought quantity* against the unchanged bid side, whereas the standalone sell uses midpoint-sized inventory; therefore the two cost columns need not sum exactly to round-trip cost. It is a two-sided friction measure, not a forecast of a later exit. Detailed VWAPs, consumed levels and quantities are in [analysis_verified.json](analysis_verified.json).

| Venue | Returned bid / ask levels | Bid quote value within 1% below midpoint | Ask quote value within 1% above midpoint |
|---|---:|---:|---:|
| Kraken | 44 / 32 | USD 6,254.72 | USD 3,083.95 |
| Binance | 333 / 1,000 | USDT 21,108.71 | USDT 11,712.72 |
| Bithumb | 30 / 30 | KRW 23,984,720.37 | KRW 40,859,401.93 |

Kraken's USD 10,000 buy VWAP is 0.2626575731, versus midpoint 0.25825; visible liquidity is limited relative to that scenario. Bithumb's first ask alone exceeds KRW 10 million, but the first bid is smaller than the midpoint-sized 10-million-KRW sell. No venue was missing from the three planned book requests; other markets were not sampled. Binance's ask response reaches its requested 1,000-level limit; no completeness beyond that is inferred.

Kraken includes order-level updates as old as May 14, while its freshest update is September 25. An old resting level is not proof the entire returned book is stale. Conversely, missing exchange snapshot clocks for Kraken/Binance prevent precise age certification. Some HTTP Date values are slightly ahead of the local collection clock; clocks are retained separately, not silently corrected. All books are now historical observations. No durable capacity, historical September 21 liquidity, buyback execution price, cross-venue arbitrage or future fill is inferred.

**Causal assessment and strongest objections.**

| Link | Status | Reason |
|---|---|---|
| Published reserve received the claimed token amount | SUPPORTED at indexer level | Two transfers reconcile with balance |
| Tokens came from exchange custody | SUPPORTED with attribution caveat | Provider labels both source wallets Binance; customer identity is unknown |
| Deposits prove fresh, incremental Travala-funded purchases | STILL UNKNOWN | No trades, funding/account records or prior inventory reconciliation |
| Observed reserve deposit is a burn | CONTRADICTED for these events | Transfer of existing supply into a custody contract, not a burn event |
| Official circulation API already reflects a distinct reserve exclusion | CONTRADICTED by captured outputs / unreconciled | Total and circulating endpoints are identical; no adjustment ledger supplied |
| Reserve is technically irreversible; rewards replenish without recycling | STILL UNKNOWN | No lock-code audit or rewards-wallet flow history |
| Future buybacks dominate potentially sellable issuance | STILL UNKNOWN | Future quantities and actual selling are not observations |
| Modest orders have negligible friction everywhere | CONTRADICTED in sampled books | Kraken's larger scenarios show material depth cost before fees |
| This mechanism establishes a prospective 2x outcome | STILL UNKNOWN | Neither execution attribution, causal price response nor forward proof exists |

The most damaging thesis evidence is the circulation-accounting inconsistency, followed by the small identified reserve stock (about 0.5% of reported total), absent proof of incremental buying, and material liquidity cost on one venue. The small ratio does not mathematically rule out a large price move; marginal prices, attention and speculative repricing can change without proportional cash flows. The reserve transfer predates the announcement, so the narrative may already have influenced price. Its degree of incorporation, speculative-demand share and counterfactual price effect are UNKNOWN in these saved responses. No new price-event study is claimed and no matched-control result is admitted.

**Updated conclusion and one decisive next observation.** The evidence improves confidence that the advertised reserve actually holds the stated amount. It does not yet improve confidence in an independently demonstrated *incremental buying* mechanism enough to support a current 90-day 2x thesis. Keep AVA **RESEARCH_ONLY**; no invented probability, promotion or trade.

The single highest-information next observation is an **independently attestable reconciliation of the inaugural reserve deposit to new, separately funded purchases**: execution timestamps, AVA quantity and consideration, tied to the two withdrawal transactions, with starting exchange inventory and the Foundation replenishment identified separately. One such reconciled record would distinguish fresh incremental demand from withdrawal of pre-existing inventory or double-counted rewards flows. It could strengthen the mechanism assessment without requiring a future monthly report; it would not by itself establish a 2x forecast or irreversible supply removal.

**Preservation and handoff.** All eight `.body` files and original `.receipt.json` files remain unchanged. Receipts retain HTTP/provider headers, local collection brackets and original write times. Transfer event times are September 21; API responses were acquired September 25; analysis and persistence are later. Supply/balance as-of blocks are absent and remain UNKNOWN. An indexer's reconstructed past is not contemporaneous September 21 capture. The initial derived `analysis.json` is retained but superseded by `analysis_verified.json`: console Decimal formatting was fixed, and an insignificant division remainder no longer counts an extra book level. Independent exact-fraction checks validate nine scenarios and eight hashes: **192 checks passed** in [verification.json](verification.json). No repository-wide or exact-head CI claim is made.

Role: Current 2x evidence investigator. Task: **AVA-DEMAND-SUPPLY-LIQUIDITY-001**. Branch: **auto/current-2x-evidence/AVA-DEMAND-SUPPLY-LIQUIDITY-001**. Last previously fetched main: **1860f917c829ee5db4f4cd36404bf9702b6b680a**, not refreshed during offline recovery. Existing plan commit: **c7fb4e16a0b9a9d19c9e4a9b304720887068e2ce**, Git committer time **2026-09-25T06:59:13Z**. Analysis artifacts are locally persisted, not newly committed, pushed or put in a new PR. Parent [#856](https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/856) and its frozen files are untouched; original [claim comment](https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/856#issuecomment-5828293500) remains the last external handoff. No scheduled owner was displaced; its live runtime was not exposed during the original ownership checks.

The broader investigation remains **IN_PROGRESS as an evidence checkpoint**, because execution verification, wider issuance/distribution/recycling history, locked balances and executable fee-adjusted liquidity are incomplete. This offline response completes analysis of what was saved, not those missing observations. No model-service call or duplicate worker was launched; exact runtime model identity is not independently certified here. No canonical state, queue priorities, protected strategies/outcomes, forward ledger, admission gates, broker state or billing changed. Next task is the single execution reconciliation above; no automatic continuation or future collection has been scheduled.
