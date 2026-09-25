"""Offline descriptive comparison of the already collected, bounded snapshot."""
import json, pathlib, datetime
R=pathlib.Path(__file__).parent
def read(name): return json.loads((R/name).read_text())
quotes={}
for filename in ['quotes.json','quotes2.json']:
 data=json.loads(read(filename)['response']['content'][0]['text'])
 for row in data['rows']:
  q=dict(zip(data['headers'],row)); quotes[q['symbol']]=q
metrics=read('descriptive_metrics.json')
funding={x['coin']:x for x in read('funding_summary.json')}
reasons={
 'AVA':'New discretionary buyback, but three repeated monthly matches barely exceed scheduled November issuance; available float and executable depth unverified; prior listing spike already happened.',
 'AAVE':'Verified business growth is insufficient evidence for a new doubling; executed current buyback rate and incremental value capture require reconciliation.',
 'HYPE':'Strongest measured fee-to-token mechanism, but $23.03bn incremental valuation and uncertain float/unlocks overwhelm a mechanical 90-day buyback-only explanation.',
 'ENA':'USDe supply is below proposed fee-switch activation; unlock disclosures conflict; price has already more than doubled over 90 days.',
 'ONDO':'New portfolio product buys underlying securities; required direct ONDO token demand is not established; launch rally already occurred.',
 'ETHFI':'Smaller valuation and growing revenue, but fee routing, actual buybacks and circulation/vesting disclosures conflict.',
 'TAO':'AI narrative and momentum lack verified incremental paid-usage-to-token-demand evidence; no upcoming halving established in this horizon.',
 'SUI':'Large remaining supply, discretionary releases and a documented wallet distribution headwind; no verified exceptional paid-usage catalyst.',
 'AVAX':'Extreme recent volume acceleration with rising volatility; network adoption does not translate one-for-one into AVAX demand.',
 'NEAR':'Already more than doubled over 30 days; new integration has no quantified incremental token demand sufficient for another doubling.'}
records=[]
for symbol in reasons:
 m=metrics[symbol]
 if symbol=='AVA':
  price=float(read('AVA_cutoff_reference.json')['last_pre_cutoff_bar'][4])
  supply=74373863; cap=None; proxy=price*supply
  ref={'provider':'Kraken AVAUSD five-minute completed candle close', 'source_as_of_utc':'2026-09-25T05:20:00Z','usd':price}
  valuation={'reported_market_cap_usd':None,'scheduled_gross_supply_tokens':supply,'scheduled_supply_value_proxy_usd':proxy,'same_supply_2x_incremental_value_proxy_usd':proxy,'circulating_supply_tokens':None,'max_supply_tokens':100000000,'fdv_usd':price*100000000}
 else:
  q=quotes[symbol]; price=q['price']; cap=q['market_cap'];proxy=None
  ref={'provider':'CoinMarketCap quote tool', 'source_as_of_utc':q['last_updated_time'],'usd':price}
  valuation={'reported_market_cap_usd':cap,'same_supply_2x_incremental_market_value_usd':cap,'circulating_supply_tokens':q['circulating_supply'],'total_supply_tokens':q['total_supply'],'max_supply_tokens':q['max_supply'],'fdv_usd':q['fully_diluted_market_cap'],'reported_aggregate_volume24h_usd':q['volume_24h']}
 records.append({'asset':symbol,'information_cutoff_utc':read('cutoff.json')['information_cutoff_utc'],'reference':ref,'reference_target_2x_usd':2*price,'tier':'DISCOVERY_POOL','calibrated_probability':None,'probability_status':'CALIBRATED PROBABILITY UNAVAILABLE','valuation':valuation,'market_structure':m,'hyperliquid_funding':funding.get(symbol),'rejection_reason':reasons[symbol],'authority':read('cutoff.json')['authority']})
rev={}
for p in ['aave','hyperliquid','ether.fi']:
 x=read(p+'_dailyRevenue.json')['eligible_series'];y=read(p+'_dailyHoldersRevenue.json')['eligible_series']
 last=sum(a[1] for a in x[-30:]);prior=sum(a[1] for a in x[:30])
 rev[p]={'last30_revenue_usd':last,'prior30_revenue_usd':prior,'change_pct':100*(last/prior-1),'last30_holders_revenue_as_reported_usd':sum(a[1] for a in y[-30:]),'last_day_start_utc':datetime.datetime.fromtimestamp(x[-1][0],datetime.timezone.utc).isoformat()}
usde=read('USDe_history.json')['eligible_series'];new=usde[-1]['circulating']['peggedUSD'];old=next(x['circulating']['peggedUSD'] for x in usde if int(x['date'])==int(usde[-1]['date'])-30*86400)
ava={'monthly_incremental_tokens_if_initial_pace_repeats':369881.04,'three_month_scenario_tokens':369881.04*3,'november_1_scheduled_issuance_tokens':1083073,'scenario_excess_buybacks_over_issuance_tokens':369881.04*3-1083073,'scenario_excess_as_gross_supply_pct':100*(369881.04*3-1083073)/74373863,'warning':'Scenario, not committed demand or verified free-float contraction; issuer-controlled release schedule and custody promises are not cryptographic locks.'}
out={'research_id':read('cutoff.json')['research_id'],'status':'NON_AUTHORITATIVE_RESEARCH_ONLY','counts':{'investigated':10,'discovery_pool':10,'potential_2x':0,'strong_candidate':0,'promotion_grade':0,'validated_prediction':0},'candidates':records,'revenue_comparison':rev,'USDe':{'latest_supply_usd':new,'source_as_of_unix':usde[-1]['date'],'thirty_day_growth_pct':100*(new/old-1),'growth_required_to_7_5bn_pct':100*(7500000000/new-1)},'AVA_scenario':ava}
(R/'comparison.json').write_text(json.dumps(out,indent=2)+'\n')
lines=['All returns end 2026-09-25 00:00 UTC; returns are percent, excess is percentage points.','', '|Asset|7d|30d|60d|90d|30d excess BTC / ETH|90d correlation BTC / ETH|Kraken ADV30 / median $m|7d/prior23 volume|RV30 annual % / RV7:RV30|ATR14 %|Prior20 low / high|','|---|---:|---:|---:|---:|---|---|---|---:|---|---:|---|']
for x in records:
 m=x['market_structure'];r=m['returns_pct'];e=m['excess_return_percentage_points'];c=m['ninety_day_daily_log_return_correlation']
 lines.append(f"|{x['asset']}|{r['7']:.1f}|{r['30']:.1f}|{r['60']:.1f}|{r['90']:.1f}|{e['XBT']['30']:+.1f} / {e['ETH']['30']:+.1f}|{c['XBT']:.2f} / {c['ETH']:.2f}|{m['kraken_adv30_usd']/1e6:.3f} / {m['kraken_median_dv30_usd']/1e6:.3f}|{m['kraken_mean_volume7_over_prior23']:.2f}|{m['rv30_annualized_pct']:.1f} / {m['rv7_over_rv30']:.2f}|{m['atr14_pct']:.1f}|{m['prior20_day_low_excluding_latest_day']:.4f} / {m['prior20_day_high_excluding_latest_day']:.4f}|")
(R/'MARKET_COMPARISON.md').write_text('\n'.join(lines)+'\n\nPrior20 excludes the latest complete day. Levels describe this sample; they are not fitted trade triggers. ADV is VWAP times base volume, not order-book depth. Correlations use 90 daily log returns and establish no causal lead/lag. Raw CMC rolling returns use different endpoints and are not substituted here.\n')
print(json.dumps({'counts':out['counts'],'revenue':rev,'USDe':out['USDe'],'AVA':ava},indent=2))
