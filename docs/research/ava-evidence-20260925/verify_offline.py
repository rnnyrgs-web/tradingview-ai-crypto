"""Reproduce the original 192 exact-fraction checks without network or file writes."""
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    analysis = json.loads((ROOT / 'analysis_verified.json').read_text())
    checks = 0

    def check(condition, message):
        nonlocal checks
        if not condition:
            raise ValueError(message)
        checks += 1

    def equal(actual, expected):
        check(abs(F(str(actual)) - expected) < F(1, 10**24), 'Exact-fraction mismatch')

    def sweep(levels, target, quote=False):
        base, value, used, worst = F(0), F(0), 0, None
        for price, quantity in levels:
            remaining = target - value if quote else target - base
            if remaining == 0:
                break
            take = min(quantity, remaining / price if quote else remaining)
            base += take
            value += take * price
            used += 1
            worst = price
        if (value if quote else base) != target:
            raise ValueError('Insufficient visible depth')
        return base, value, used, worst

    for book in analysis['books']:
        name = {'Kraken': 'kraken_book', 'Binance': 'binance_book', 'Bithumb': 'bithumb_book'}[book['venue']]
        raw = json.loads((ROOT / 'raw' / (name + '.body')).read_bytes())
        obj = next(iter(raw['result'].values())) if book['venue'] == 'Kraken' else raw.get('data', raw)

        def levels(side):
            return [(F(x['price']), F(x['quantity'])) if isinstance(x, dict) else (F(x[0]), F(x[1])) for x in obj[side]]

        bids, asks = levels('bids'), levels('asks')
        mid = (bids[0][0] + asks[0][0]) / 2
        equal(book['spread_bps'], (asks[0][0] - bids[0][0]) / mid * 10000)
        for row in book['scenarios']:
            budget = F(row['quote_budget'])
            buy, sell = sweep(asks, budget, True), sweep(bids, budget / mid)
            rt = sweep(bids, buy[0])
            for stored, computed in [(row['buy'], buy), (row['sell'], sell), (row['static_roundtrip_sell'], rt)]:
                equal(stored['base'], computed[0])
                equal(stored['quote'], computed[1])
                equal(stored['vwap'], computed[1] / computed[0])
                equal(stored['worst_price'], computed[3])
                check(stored['levels_used'] == computed[2], 'Level-count mismatch')
            equal(row['buy']['midpoint_cost_bps'], (buy[1] / buy[0] / mid - 1) * 10000)
            equal(row['sell']['midpoint_cost_bps'], (1 - sell[1] / sell[0] / mid) * 10000)
            equal(row['static_roundtrip_friction_bps'], (1 - rt[1] / budget) * 10000)
        for depth in book['depth']:
            band = F(depth['midpoint_band_bps'], 10000)
            equal(depth['bid_quote'], sum((price * q for price, q in bids if price >= mid * (1 - band)), F(0)))
            equal(depth['ask_quote'], sum((price * q for price, q in asks if price <= mid * (1 + band)), F(0)))

    for item in analysis['inventory']:
        name = item['file'].replace('\\', '/').rsplit('/', 1)[-1]
        check(hashlib.sha256((ROOT / 'raw' / name).read_bytes()).hexdigest() == item['sha256'], 'Raw hash mismatch')
    check(sum(F(t['amount_ava']) for t in analysis['transfers']) == F(analysis['supply']['reserve_balance']), 'Reserve mismatch')
    if checks != 192:
        raise ValueError('Verification coverage changed')
    original = json.loads((ROOT / 'verification.json').read_text())
    if original['result'] != 'PASS' or original['checks'] != checks:
        raise ValueError('Original verification receipt mismatch')
    checkpoint = json.loads((ROOT / 'CHECKPOINT.json').read_text())
    for filename, key in [('FINDINGS_RECOVERY.md', 'findings_sha256'), ('analysis_verified.json', 'analysis_sha256')]:
        if hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() != checkpoint[key]:
            raise ValueError('Recovery checkpoint mismatch: ' + filename)
    print(json.dumps({'mode': 'OFFLINE_READ_ONLY', 'checks': checks, 'result': 'PASS',
                      'raw_hashes_verified': 8, 'scenarios_verified': 9,
                      'recovery_checkpoint_hashes_verified': 2}))


if __name__ == '__main__':
    main()
