"""Deterministic analysis of the eight frozen responses. No network or execution API."""
import datetime as dt
from decimal import Decimal, getcontext
import hashlib
import json
from pathlib import Path

getcontext().prec = 40
D = Decimal
ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
NAMES = ['kraken_book', 'binance_book', 'bithumb_book', 'total_supply',
         'circulating_supply', 'reserve_transfers', 'reserve_balances', 'token_info']
AVA_CONTRACT_ADDRESS = '0xa6c0c097741d55ecd9a3a7def3a8253fd022ceb9'
RESERVE = '0x7bed1889c21d9eb3560463c14cd74fe29f2d03b6'

def iso(seconds):
    return dt.datetime.fromtimestamp(float(seconds), dt.timezone.utc).isoformat()

def sweep(levels, target, quote_target=False):
    remaining, base, quote, used, worst = target, D(0), D(0), 0, None
    for price, quantity in levels:
        if remaining <= D('1e-25'):
            break
        take = min(quantity, remaining / price) if quote_target else min(quantity, remaining)
        base += take
        quote += take * price
        remaining -= take * price if quote_target else take
        used += 1
        worst = price
    # Decimal division can leave a sub-1e-30 residual, far below any venue precision.
    full = remaining <= D('1e-25')
    return dict(full_visible_coverage=full, remaining=max(D(0), remaining), base=base,
                quote=quote, vwap=quote/base if base else None, levels_used=used, worst_price=worst)

def main():
    data, receipts, inventory = {}, {}, []
    for name in NAMES:
        path = RAW / (name + '.body')
        body = path.read_bytes()
        receipt = json.loads((ROOT / 'public_receipts' / (name + '.receipt.json')).read_text())
        if not (len(body) == receipt['bytes']):
            raise ValueError('Invalid frozen evidence at original check line 42')
        if not (hashlib.sha256(body).hexdigest() == receipt['sha256']):
            raise ValueError('Invalid frozen evidence at original check line 43')
        if not (receipt['status'] == 200):
            raise ValueError('Invalid frozen evidence at original check line 44')
        data[name], receipts[name] = json.loads(body), receipt
        inventory.append(dict(file=str(path), bytes=len(body), readable=True, sha256=receipt['sha256'],
                              collection_start=receipt['collection_start'], collection_end=receipt['collection_end'],
                              local_write_time=receipt['local_write_time'], http_date=receipt['headers'].get('Date'),
                              source_url=receipt['url']))

    transfers = data['reserve_transfers']
    seen, rows, inflow, outflow = set(), [], D(0), D(0)
    for item in sorted(transfers['items'], key=lambda t: (t['block_number'], t['log_index'])):
        if not (item['token']['address_hash'].lower() == AVA_CONTRACT_ADDRESS):
            raise ValueError('Invalid frozen evidence at original check line 54')
        key = (1, AVA_CONTRACT_ADDRESS, item['transaction_hash'], item['log_index'])
        if not (key not in seen):
            raise ValueError('Invalid frozen evidence at original check line 56')
        seen.add(key)
        amount = D(item['total']['value']) / D(10)**int(item['total']['decimals'])
        sender, recipient = item['from']['hash'].lower(), item['to']['hash'].lower()
        if not (RESERVE in (sender, recipient)):
            raise ValueError('Invalid frozen evidence at original check line 60')
        if recipient == RESERVE:
            inflow += amount
        if sender == RESERVE:
            outflow += amount
        rows.append(dict(chain_id=1, transaction_hash=item['transaction_hash'], log_index=item['log_index'],
                         block_number=item['block_number'], block_hash=item['block_hash'], event_time=item['timestamp'],
                         sender=sender, recipient=recipient, amount_ava=amount,
                         sender_labels=[t['name'] for t in (item['from'].get('metadata') or {}).get('tags', [])],
                         method=item.get('method'), reserve_contract_metadata=item['to'].get('implementations')))
    matching = [x for x in data['reserve_balances'] if x['token']['address_hash'].lower() == AVA_CONTRACT_ADDRESS]
    if not (len(matching) == 1):
        raise ValueError('Invalid frozen evidence at original check line 71')
    reserve = D(matching[0]['value']) / D(10)**int(matching[0]['token']['decimals'])
    if not (data['token_info']['address_hash'].lower() == AVA_CONTRACT_ADDRESS):
        raise ValueError('Invalid frozen evidence at original check line 73')
    token_supply = D(data['token_info']['total_supply']) / D(10)**int(data['token_info']['decimals'])
    total, circulating = D(data['total_supply']), D(data['circulating_supply'])
    if not (inflow - outflow == reserve):
        raise ValueError('Invalid frozen evidence at original check line 76')
    if not (token_supply == total):
        raise ValueError('Invalid frozen evidence at original check line 77')
    supply = dict(issuer_total=total, issuer_circulating=circulating, indexed_erc20_total=token_supply,
                  reserve_balance=reserve, reserve_inflow=inflow, reserve_outflow_in_returned_history=outflow,
                  pagination_end_reported=transfers['next_page_params'] is None,
                  reserve_pct_of_total=reserve/total*100,
                  total_less_reserve_conditional=total-reserve,
                  supply_api_exclusion_gap=circulating-(total-reserve),
                  inferred_verified_market_purchase_quantity=None,
                  quantity_of_new_buying_compatible_with_reserve_deposits_only=[D(0), reserve],
                  conditional_reserve_float_reduction_range=[D(0), reserve],
                  maximum_less_issued_if_100m_cap=D('100000000')-total,
                  other_wallet_balances=None, circulating_float=None, actual_future_sales=None)

    books = []
    if not (data['kraken_book']['error'] == []):
        raise ValueError('Invalid frozen evidence at original check line 91')
    if not (list(data['kraken_book']['result']) == ['AVAUSD']):
        raise ValueError('Invalid frozen evidence at original check line 92')
    if not (data['bithumb_book']['status'] == '0000'):
        raise ValueError('Invalid frozen evidence at original check line 93')
    for venue, name, unit, sizes in [('Kraken','kraken_book','USD',[1000,5000,10000]),
                                     ('Binance','binance_book','USDT',[1000,5000,10000]),
                                     ('Bithumb','bithumb_book','KRW',[1000000,5000000,10000000])]:
        book = next(iter(data[name]['result'].values())) if venue == 'Kraken' else data[name].get('data', data[name])
        def levels(side):
            return [(D(x['price']),D(x['quantity'])) if isinstance(x,dict) else (D(x[0]),D(x[1])) for x in book[side]]
        bids, asks = levels('bids'), levels('asks')
        if not (bids and asks and all(p>0 and q>0 for p,q in bids+asks)):
            raise ValueError('Invalid frozen evidence at original check line 101')
        if not (all(bids[i][0] > bids[i+1][0] for i in range(len(bids)-1))):
            raise ValueError('Invalid frozen evidence at original check line 102')
        if not (all(asks[i][0] < asks[i+1][0] for i in range(len(asks)-1))):
            raise ValueError('Invalid frozen evidence at original check line 103')
        if not (bids[0][0] < asks[0][0]):
            raise ValueError('Invalid frozen evidence at original check line 104')
        mid = (bids[0][0] + asks[0][0]) / 2
        end = D(str(dt.datetime.fromisoformat(receipts[name]['collection_end']).timestamp()))
        times = {}
        if venue == 'Kraken':
            timestamps = [D(str(x[2])) for side in ('bids','asks') for x in book[side]]
            if not (max(timestamps) <= end):
                raise ValueError('Future order update timestamp')
            times = dict(provider_snapshot_time=None, oldest_level_update=iso(min(timestamps)),
                         newest_level_update=iso(max(timestamps)), newest_update_age_seconds=end-max(timestamps))
        elif venue == 'Bithumb':
            if not (book['order_currency']=='AVA' and book['payment_currency']=='KRW'):
                raise ValueError('Invalid frozen evidence at original check line 114')
            stamp = D(book['timestamp']) / 1000
            if not (stamp <= end):
                raise ValueError('Future book timestamp')
            times = dict(provider_timestamp=iso(stamp), provider_timestamp_age_seconds=end-stamp)
        else:
            times = dict(provider_snapshot_time=None, last_update_id=book['lastUpdateId'])
        rows_for_book = []
        for n in sizes:
            budget = D(n)
            buy = sweep(asks, budget, quote_target=True)
            sell = sweep(bids, budget/mid)
            roundtrip_sell = sweep(bids, buy['base'])
            buy['midpoint_cost_bps'] = (buy['vwap']/mid-1)*10000
            buy['depth_beyond_best_ask_bps'] = (buy['vwap']-asks[0][0])/mid*10000
            sell['midpoint_cost_bps'] = (1-sell['vwap']/mid)*10000
            sell['depth_beyond_best_bid_bps'] = (bids[0][0]-sell['vwap'])/mid*10000
            # This is static two-sided friction for the bought quantity; not two actual successive fills.
            rt = (1-roundtrip_sell['quote']/buy['quote'])*10000 if buy['full_visible_coverage'] and roundtrip_sell['full_visible_coverage'] else None
            rows_for_book.append(dict(quote_budget=budget, buy=buy, sell=sell,
                                      sell_target_base=budget/mid, static_roundtrip_sell=roundtrip_sell,
                                      static_roundtrip_friction_bps=rt))
        depth = []
        for bps in [50,100,200]:
            frac=D(bps)/10000
            depth.append(dict(midpoint_band_bps=bps,
                              bid_base=sum((q for p,q in bids if p>=mid*(1-frac)),D(0)),
                              bid_quote=sum((p*q for p,q in bids if p>=mid*(1-frac)),D(0)),
                              ask_base=sum((q for p,q in asks if p<=mid*(1+frac)),D(0)),
                              ask_quote=sum((p*q for p,q in asks if p<=mid*(1+frac)),D(0))))
        books.append(dict(venue=venue, quote_unit=unit, pair='AVA/'+unit,
                          collection_start=receipts[name]['collection_start'], collection_end=receipts[name]['collection_end'],
                          http_date=receipts[name]['headers'].get('Date'), **times,
                          best_bid=bids[0][0], best_ask=asks[0][0], midpoint=mid,
                          spread_bps=(asks[0][0]-bids[0][0])/mid*10000,
                          bid_levels=len(bids), ask_levels=len(asks),
                          visible_bid_quote=sum((p*q for p,q in bids),D(0)),
                          visible_ask_quote=sum((p*q for p,q in asks),D(0)), depth=depth, scenarios=rows_for_book,
                          fees='UNKNOWN; excluded, not assumed zero', venue_contract_mapping_in_book=False))
    result=dict(analysis_time=dt.datetime.now(dt.timezone.utc).isoformat(), mode='OFFLINE', inventory=inventory,
                transfers=rows, supply=supply, books=books)
    target=ROOT/'analysis_verified.json'
    expected = json.loads(target.read_text())
    actual = json.loads(json.dumps(result, default=str))
    # Reproduction time and checkout location are not acquisition observations.
    for obj in (expected, actual):
        obj.pop('analysis_time')
        for item in obj['inventory']:
            item['file'] = item['file'].replace('\\', '/').rsplit('/', 1)[-1]
    if expected != actual:
        raise ValueError('Recomputed evidence differs from frozen analysis')
    print('Frozen analysis reproduced without modifying evidence or results.')
    print('Eight raw hashes verified; two unique transfer events reconcile with reserve balance; three valid books analyzed.')
    print('SUPPLY',json.dumps(supply,default=str))
    for b in books:
        print('BOOK',b['venue'],'spread_bps',str(b['spread_bps']),'clocks',json.dumps({k:b.get(k) for k in ['oldest_level_update','newest_level_update','provider_timestamp','provider_timestamp_age_seconds']}, default=str))
        print('DEPTH',json.dumps(b['depth'],default=str))
        for r in b['scenarios']:
            print('SCENARIO',b['venue'],str(r['quote_budget']), 'buy_bps',str(r['buy']['midpoint_cost_bps']),
                  'sell_bps',str(r['sell']['midpoint_cost_bps']),'roundtrip_bps',str(r['static_roundtrip_friction_bps']),
                  'coverage',r['buy']['full_visible_coverage'],r['sell']['full_visible_coverage'])

if __name__ == '__main__':
    main()
