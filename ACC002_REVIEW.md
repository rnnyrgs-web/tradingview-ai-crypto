# ACC-002 review checklist

Before merge:
- exact-head Security and Reliability workflow succeeds;
- timestamp monotonicity and minimum-universe tests pass;
- cross-asset evidence stays research-only with live_approved=false and trade_authority=false;
- no paid service/data dependency is added;
- Render heavy concurrency remains bounded by WORKER_ARMY_MAX_CONCURRENT (target 2).

After merge:
- verify coordinator deploy live;
- verify worker health exposes the cross-asset-rank loop and no repeated failures/timeouts;
- inspect first real research output before making any profitability claim;
- record integration/evidence in AI_STATE.md.
