"""Reproduce descriptive economics from already-consumed #815 evidence only.

No archive acquisition, model fitting, new variant, admission, or OOS access.
Supply the retained events.json.gz from the pinned PR815 commit.
"""
import gzip
import argparse
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

SOURCE_SHA = '07a7912344a97e7e6369f3df9c78f5e0e65a2ace'
EVENTS_SHA256 = 'a5c3ebe8e5799af419bb2f95411ad29c8fde406887680ee55ed2b3ec90d6ee91'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('events_archive', type=Path)
args = parser.parse_args()
raw = gzip.decompress(args.events_archive.read_bytes())
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
