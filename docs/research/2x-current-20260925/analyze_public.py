"""Descriptive pre-cutoff metrics; no outcome label or inferential fit."""
import json, math, statistics, pathlib
R=pathlib.Path(__file__).parent
out={}; log_returns={}
for p in R.glob('*_daily.json'):
 d=json.loads(p.read_text()); rows=d.get('eligible_completed_bars',[])[-91:]
 if len(rows)<91: continue
 assert all(rows[i][0]-rows[i-1][0]==86400 for i in range(1,len(rows)))
 c=[float(x[4]) for x in rows]; h=[float(x[2]) for x in rows]; lo=[float(x[3]) for x in rows]
 q=[float(x[5])*float(x[6]) for x in rows]
 lr=[math.log(c[i]/c[i-1]) for i in range(1,len(c))]
 log_returns[p.stem.replace('_daily','')]=lr
 tr=[max(h[i]-lo[i],abs(h[i]-c[i-1]),abs(lo[i]-c[i-1])) for i in range(1,len(c))]
 out[p.stem.replace('_daily','')]={'reference_completed_day_close':c[-1],
  'returns_pct':{str(n):100*(c[-1]/c[-1-n]-1) for n in [7,30,60,90]},
  'rv30_annualized_pct':statistics.stdev(lr[-30:])*math.sqrt(365)*100,
  'rv7_over_rv30':statistics.stdev(lr[-7:])/statistics.stdev(lr[-30:]),
  'atr14_pct':statistics.mean(tr[-14:])/c[-1]*100,
  'kraken_adv30_usd':statistics.mean(q[-30:]),'kraken_median_dv30_usd':statistics.median(q[-30:]),
  'kraken_mean_volume7_over_prior23':statistics.mean(q[-7:])/statistics.mean(q[-30:-7]),
  'prior20_day_high_excluding_latest_day':max(h[-21:-1]),'prior20_day_low_excluding_latest_day':min(lo[-21:-1]),
  'latest_day_high':h[-1],'latest_day_low':lo[-1],
  'range7_pct':100*(max(h[-7:])-min(lo[-7:]))/c[-1],
  'range30_pct':100*(max(h[-30:])-min(lo[-30:]))/c[-1],
  'distance_from_90d_low_pct':100*(c[-1]/min(lo)-1)}
for k,v in out.items():
 v['excess_return_percentage_points']={b:{n:v['returns_pct'][n]-out[b]['returns_pct'][n] for n in ['7','30','60','90']} for b in ['XBT','ETH']}
 v['ninety_day_daily_log_return_correlation']={b:statistics.correlation(log_returns[k],log_returns[b]) for b in ['XBT','ETH']}
(R/'descriptive_metrics.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
