"""Offline data-quality checks; never queries outcomes or changes research authority."""
import datetime, hashlib, json, math, pathlib
R=pathlib.Path(__file__).parent
def read(name): return json.loads((R/name).read_text())
cutoff=read('cutoff.json');end=datetime.datetime.fromisoformat(cutoff['information_cutoff_utc'].replace('Z','+00:00')).timestamp()
assert datetime.datetime.fromisoformat(cutoff['reference_horizon_end_utc'].replace('Z','+00:00')).timestamp()-end==90*86400
assert cutoff['status']=='NON_AUTHORITATIVE_RESEARCH_ONLY' and not any(cutoff['authority'].values())
checks=['cutoff/horizon and all authority flags']
daily_counts={}
for p in R.glob('*_daily.json'):
 d=read(p.name);rows=d['eligible_completed_bars'];assert len(rows)>=91 and not d['provider_errors']
 assert all(rows[i][0]-rows[i-1][0]==86400 for i in range(1,len(rows)))
 assert all(r[0]+86400<=end for r in rows)
 for r in rows:
  o,h,l,c,vwap,vol=map(float,r[1:7]);assert all(math.isfinite(v) for v in [o,h,l,c,vwap,vol])
  assert 0<l<=min(o,c)<=max(o,c)<=h and vol>=0
 assert rows[-1][0]+86400==1790294400
 daily_counts[p.stem.replace('_daily','')]=len(rows)
assert len(daily_counts)==12
checks.append('12 spot series: positive finite OHLC, nonnegative volume, unique contiguous days, completed before cutoff')
funding_counts={}
for p in R.glob('*_funding.json'):
 d=read(p.name);rows=d['rows'];coin=p.stem.replace('_funding','')
 assert len(rows)==336 and all(x['coin']==coin and (end-14*86400)*1000<=x['time']<=end*1000 for x in rows)
 hours=[x['time']//3600000 for x in rows];assert len(set(hours))==336 and all(b-a==1 for a,b in zip(hours,hours[1:]))
 assert all(math.isfinite(float(x['fundingRate'])) for x in rows)
 summary=next(x for x in read('funding_summary.json') if x['coin']==coin)
 for label,part in [('last7_sum_pct',[x for x in rows if x['time']>(end-7*86400)*1000]),('prior7_sum_pct',[x for x in rows if x['time']<=(end-7*86400)*1000])]:
  assert len(part)==168 and math.isclose(summary[label],sum(float(x['fundingRate']) for x in part)*100,abs_tol=1e-12)
 funding_counts[coin]=len(rows)
assert len(funding_counts)==9
checks.append('9 funding series: 336 distinct contiguous hourly buckets; both weekly sums independently reconciled')
for prefix in ['aave','hyperliquid','ether.fi']:
 for kind in ['dailyRevenue','dailyHoldersRevenue']:
  rows=read(prefix+'_'+kind+'.json')['eligible_series'];assert len(rows)==60
  assert all(b[0]-a[0]==86400 for a,b in zip(rows,rows[1:]))
  assert all(x[0]+86400<=end and math.isfinite(x[1]) and x[1]>=0 for x in rows)
usde=read('USDe_history.json')['eligible_series'];assert len(usde)==40 and all(int(x['date'])<=end for x in usde)
assert all(int(b['date'])-int(a['date'])==86400 for a,b in zip(usde,usde[1:]))
checks.append('six 60-day revenue series and 40-point stablecoin series: complete pre-cutoff date coverage')
ref=read('AVA_cutoff_reference.json')['last_pre_cutoff_bar'];assert ref[0]+300==end and float(ref[4])==0.2596
comparison=read('comparison.json');assert comparison['counts']=={'investigated':10,'discovery_pool':10,'potential_2x':0,'strong_candidate':0,'promotion_grade':0,'validated_prediction':0}
assert len({x['asset'] for x in comparison['candidates']})==10
for x in comparison['candidates']:
 assert x['tier']=='DISCOVERY_POOL' and x['calibrated_probability'] is None and not any(x['authority'].values())
 assert x['reference_target_2x_usd']==2*x['reference']['usd']
 assert datetime.datetime.fromisoformat(x['reference']['source_as_of_utc'].replace('Z','+00:00')).timestamp()<=end
 v=x['valuation']
 if x['asset']!='AVA': assert math.isclose(v['reported_market_cap_usd'],v['circulating_supply_tokens']*x['reference']['usd'],rel_tol=1e-7)
checks.append('ten exact reference targets and source times; all tiers discovery; null calibrated probabilities; no trading authority')
metrics=read('descriptive_metrics.json')
for symbol in metrics:
 rows=read(symbol+'_daily.json')['eligible_completed_bars'];m=metrics[symbol]
 for n in [7,30,60,90]: assert math.isclose(m['returns_pct'][str(n)],100*(float(rows[-1][4])/float(rows[-1-n][4])-1),abs_tol=1e-10)
checks.append('48 return calculations independently reconciled to retained closes')
report=(R/'RESULTS_AND_DECISIONS.md').read_text(encoding='utf-8')
for phrase in ['CURRENT QUALIFIED PROMOTION-GRADE 2X CANDIDATES: 0','CURRENT STRONG_CANDIDATES: 0','CURRENT POTENTIAL_2X RESEARCH CANDIDATES: 0','CALIBRATED PROBABILITY UNAVAILABLE']:
 assert phrase in report
checks.append('report and machine-readable conclusions agree')
hashes={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted(R.iterdir()) if p.is_file() and p.name!='VALIDATION.json'}
result={'validated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS','checks':checks,'daily_rows':daily_counts,'funding_rows':funding_counts,'file_hash_convention':'SHA256 of UTF-8 text with CRLF normalized to LF, matching committed Git blobs','file_sha256':hashes,'limitations':['Data-quality checks do not authenticate historical capture or provider truth.','No matched-control/outcome tests or trading execution tests were possible.','GitHub exact-head CI is separate and must be checked on the published commit.']}
(R/'VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'checks':len(checks),'hashed_files':len(hashes),'daily_rows':sum(daily_counts.values()),'funding_rows':sum(funding_counts.values())}))
