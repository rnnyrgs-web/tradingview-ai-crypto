"""Reproduce descriptive economics from already-consumed #815 evidence only.

No archive acquisition, model fitting, new variant, admission, or OOS access.
Run from a checkout containing the pinned PR815 commit (fetch that PR if absent).
"""
import gzip
import hashlib
import json
import statistics
import subprocess
from datetime import datetime, timezone

SOURCE_SHA = '07a7912344a97e7e6369f3df9c78f5e0e65a2ace'
EVENTS_SHA256 = 'a5c3ebe8e5799af419bb2f95411ad29c8fde406887680ee55ed2b3ec90d6ee91'
raw = gzip.decompress(subprocess.check_output([
    'git', 'show', SOURCE_SHA + ':research_data/btc_candle_2024/evidence/events.json.gz'
]))
if hashlib.sha256(raw).hexdigest() != EVENTS_SHA256:
    raise ValueError('Consumed evidence identity mismatch')
events = json.loads(raw)
split = int(datetime(2024, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
report = {'source_commit': SOURCE_SHA, 'events_sha256': EVENTS_SHA256,
          'classification': 'REPRODUCED_UNADMITTED_EMPIRICAL_NEGATIVE_EVIDENCE',
          'new_outcomes_opened': False, 'admission_or_promotion_authority': False,
          'fingerprint': 'EXT-BTC-CANDLE-CLOCK-001-v1', 'halves': {}}
for name, subset in [('training', [e for e in events if e['t'] < split]),
                     ('validation', [e for e in events if e['t'] >= split])]:
    gross = [e['target'] for e in subset]
    costs = {}
    for cost in (24, 48, 72):
        net = [x-cost for x in gross]
        positive, negative = sum(max(x, 0) for x in net), -sum(min(x, 0) for x in net)
        costs[str(cost)] = {'mean_net_bps': statistics.mean(net),
            'profit_factor': positive / negative if negative else None,
            'wins': sum(x > 0 for x in net), 'losses': sum(x < 0 for x in net),
            'worst_trade_bps': min(net), 'best_trade_bps': max(net),
            'max_positive_return_share': max(net) / positive if positive else None}
    report['halves'][name] = {'opportunities': len(subset),
        'utc_days': len({e['t']//86400000 for e in subset}),
        'mean_gross_bps': statistics.mean(gross), 'costs_bps': costs,
        'gross_target_minus_clock_bps': statistics.mean(e['target']-e['clock'] for e in subset)}
print(json.dumps(report, indent=2, allow_nan=False))
