"""One-shot public funding history and cutoff AVA reference; no current OI proxy."""
import urllib.request,json,datetime,pathlib,hashlib,concurrent.futures
R=pathlib.Path(__file__).parent
END=int(datetime.datetime.fromisoformat('2026-09-25T05:20:00+00:00').timestamp()*1000)
def fetch(coin):
 body={'type':'fundingHistory','coin':coin,'startTime':END-14*86400000,'endTime':END}
 meta={'provider_url':'https://api.hyperliquid.xyz/info','request':body,'retrieval_started_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(meta['provider_url'],data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=25) as resp: raw=resp.read(2000000);meta.update(status=resp.status,server_date=resp.headers.get('Date'))
  meta.update(retrieval_completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),sha256=hashlib.sha256(raw).hexdigest())
  rows=json.loads(raw);assert isinstance(rows,list)
  assert all(x['coin']==coin and END-14*86400000<=x['time']<=END for x in rows)
  (R/(coin+'_funding.json')).write_text(json.dumps({'receipt':meta,'rows':rows},indent=2))
  current=[float(x['fundingRate']) for x in rows if x['time']>END-7*86400000]
  prior=[float(x['fundingRate']) for x in rows if x['time']<=END-7*86400000]
  return {'coin':coin,'n':len(rows),'last_time':rows[-1]['time'] if rows else None,'last_rate_decimal':rows[-1]['fundingRate'] if rows else None,'last_premium_decimal':rows[-1].get('premium') if rows else None,'last7_sum_pct':sum(current)*100,'prior7_sum_pct':sum(prior)*100}
 except Exception as e:
  meta['error']=str(e);(R/(coin+'_funding.json')).write_text(json.dumps(meta,indent=2));return {'coin':coin,'error':str(e)}
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex: results=list(ex.map(fetch,['AAVE','ENA','HYPE','ONDO','TAO','SUI','AVAX','NEAR','ETHFI']))
 (R/'funding_summary.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
 u='https://api.kraken.com/0/public/OHLC?pair=AVAUSD&interval=5'
 with urllib.request.urlopen(u,timeout=25) as resp: data=json.loads(resp.read(2000000))
 rows=[x for k,v in data.get('result',{}).items() if k!='last' for x in v if x[0]+300<=END/1000]
 result={'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'last_pre_cutoff_bar':rows[-1] if rows else None}
 (R/'AVA_cutoff_reference.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
