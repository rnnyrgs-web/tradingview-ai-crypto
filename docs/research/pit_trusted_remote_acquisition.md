# PIT trusted remote-acquisition boundary

## Purpose

Historical 2x research currently has two useful but scientifically incomplete source paths: Common Crawl index/WARC evidence for primary-document chronology (#516) and Binance S3 ListObjectsV2 evidence for a survivorship-safe historical symbol universe (#536). In both cases, local bytes + a local SHA-256 + an official-looking URL prove self-consistency, not that the upstream provider actually served those exact bytes.

`PIT-TRUSTED-REMOTE-ACQUISITION-001-v1` closes only that provider-origin boundary. It does not grant label, candidate, strategy, promotion, broker, or trading authority.

## Trusted acquisition model

The workflow is `workflow_dispatch` only and the implementation refuses execution unless GitHub identifies the canonical repository, `refs/heads/main`, and the exact signer workflow `rnnyrgs-web/tradingview-ai-crypto/.github/workflows/pit-trusted-remote-acquisition.yml@refs/heads/main`. A sibling workflow in the same repository is not trusted merely because it runs on `main`. Request URLs are built from frozen source-specific inputs rather than accepting arbitrary fetch URLs. HTTPS uses the Python default verified TLS context and redirects are not followed.

Every successful fetch emits `response.bin`, `receipt.json`, and a deterministic `trusted-acquisition.tar`. The receipt binds the frozen source-contract identity, exact request URL/method/range, response status/hash/byte count, acquisition timestamps, canonical repository/ref/SHA/exact-workflow/run identity, and pagination predecessor receipt when applicable.

The tar subject is then signed through GitHub Artifact Attestations. Provider bytes are not authoritative merely because the local receipt exists; downstream research must verify the GitHub attestation for the exact tar subject and then verify the receipt against the extracted response bytes. GitHub's artifact-attestation provenance is the independent execution/signing boundary that a caller-authored local file cannot reproduce.

Downstream verification must bind the repository, exact signer workflow, and source ref. The canonical CLI form is:

```bash
gh attestation verify trusted-acquisition.tar \
  --repo rnnyrgs-web/tradingview-ai-crypto \
  --signer-workflow rnnyrgs-web/tradingview-ai-crypto/.github/workflows/pit-trusted-remote-acquisition.yml \
  --source-ref refs/heads/main
```

Repo/ref-only attestation verification is insufficient for this contract because it would grant sibling workflows signing authority.

## Frozen source shapes

- `BINANCE_LISTOBJECTS_V2`: only the Binance public-data S3 bucket listing path and only prefixes below `data/spot/monthly/klines/`. Paginated requests require a predecessor receipt hash so #536 can verify the complete authenticated page chain.
- `COMMONCRAWL_INDEX`: only `index.commoncrawl.org/<CC-MAIN-...>-index`, `output=json`, and an exact HTTPS document URL.
- `COMMONCRAWL_WARC_RANGE`: only `data.commoncrawl.org/crawl-data/<same collection>/.../warc/*.warc.gz` with an exact bounded byte range.

## Common Crawl digest compatibility

Common Crawl CDXJ `digest` values and WARC `WARC-Payload-Digest` values represent the same SHA-1 payload differently: CDXJ uses bare Base32 while WARC uses `sha1:<Base32>`. `commoncrawl_digest_normalization.py` normalizes only these algorithm-equivalent forms and rejects unsupported algorithms/malformed values. #516 must consume this normalization when it is rebased onto the trusted acquisition boundary; raw string comparison is not provider-compatible.

## Required integration sequence

1. Exact-head Security & Reliability and independent provenance/security review of this PR.
2. Integrate through the trusted Lead path; do not run the new workflow from an untrusted branch.
3. On canonical main, acquire one positive-control Binance listing page and one Common Crawl index/range pair through the workflow.
4. Verify each `trusted-acquisition.tar` using the exact repository + signer-workflow + source-ref identity above, then preserve the exact bundle/receipt identities.
5. Rebase/repair #536 so every ListObjectsV2 page must have a valid attested receipt and the continuation chain is complete.
6. Rebase/repair #516 so both the CDXJ response and WARC range must have valid attested receipts, the real-provider digest forms are normalized, and the existing WARC chronology/content binding remains fail-closed.
7. Only after those gates pass may #514 count this evidence toward PIT coverage. Historical outcomes remain sealed until the full cohort coverage/tradability gate clears.

If the trusted provider request cannot be acquired or attestation cannot be verified, the result is `DATA_BLOCKED`, never local-file fallback, today's-survivor substitution, or an analyst-authored historical timestamp.
