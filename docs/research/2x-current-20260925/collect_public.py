"""Bounded one-off research collection; no credentials, outcomes or trading."""
import json, urllib.request, hashlib, datetime, pathlib, concurrent.futures
ROOT = pathlib.Path(__file__).parent
CUTOFF = datetime.datetime.fromisoformat('2026-09-25T05:20:00+00:00').timestamp()
SYMBOLS = ['XBT','ETH','AAVE','ENA','HYPE','ONDO','TAO','SUI','AVAX','NEAR','ETHFI','AVA']
def fetch(symbol):
    url = 'https://api.kraken.com/0/public/OHLC?pair='+symbol+'USD&interval=1440'
    meta = {'url':url, 'retrieval_started_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            raw=r.read(2000000); meta.update(status=r.status,server_date=r.headers.get('Date'))
        meta.update(retrieval_completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),sha256=hashlib.sha256(raw).hexdigest())
        data=json.loads(raw)
        # Exclude incomplete/post-cutoff bars before any analysis or output.
        rows=[x for k,v in data.get('result',{}).items() if k!='last' for x in v if x[0]+86400<=CUTOFF]
        result={'receipt':meta,'provider_errors':data.get('error'),'eligible_completed_bars':rows,
                'raw_response_hash_only_note':'Original response includes the unfinished current candle; only completed pre-cutoff rows retained, with whole-response SHA for audit.'}
        (ROOT/(symbol+'_daily.json')).write_text(json.dumps(result,indent=2))
        return {'symbol':symbol,'n':len(rows),'last_end':datetime.datetime.fromtimestamp(rows[-1][0]+86400,datetime.timezone.utc).isoformat() if rows else None,'errors':data.get('error')}
    except Exception as e:
        meta['error']=str(e); (ROOT/(symbol+'_daily.json')).write_text(json.dumps(meta,indent=2)); return {'symbol':symbol,'error':str(e)}
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for result in ex.map(fetch,SYMBOLS): print(json.dumps(result))
