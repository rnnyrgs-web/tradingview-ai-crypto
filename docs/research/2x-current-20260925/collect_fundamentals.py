import urllib.request,json,datetime,pathlib,hashlib,concurrent.futures
R=pathlib.Path(__file__).parent
END=int(datetime.datetime.fromisoformat('2026-09-25T00:00:00+00:00').timestamp())
jobs=[('USDe_history','https://stablecoins.llama.fi/stablecoin/146')]+[(p+'_'+t,'https://api.llama.fi/summary/fees/'+p+'?dataType='+t) for p in ['aave','hyperliquid','ether.fi'] for t in ['dailyRevenue','dailyHoldersRevenue']]
def get(job):
 name,url=job;meta={'url':url,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(url,timeout=25) as r: raw=r.read(8000000);meta.update(status=r.status,server_date=r.headers.get('Date'))
  data=json.loads(raw);meta['sha256']=hashlib.sha256(raw).hexdigest()
  if name=='USDe_history':
   rows=[x for x in data.get('tokens',[]) if int(x['date'])<=END];selected=rows[-40:];summary={'name':data.get('name'),'symbol':data.get('symbol'),'rows':selected[-3:]}
  else:
   rows=[x for x in data.get('totalDataChart',[]) if int(x[0])+86400<=END];selected=rows[-60:]
   summary={'name':data.get('name'),'days':len(selected),'last':selected[-1:]}
   if len(selected)==60: summary.update(last30_sum=sum(float(x[1]) for x in selected[-30:]),prior30_sum=sum(float(x[1]) for x in selected[:30]))
  (R/(name+'.json')).write_text(json.dumps({'receipt':meta,'name':data.get('name'),'symbol':data.get('symbol'),'methodology':data.get('methodology'),'eligible_series':selected},indent=2))
  return {'job':name,**summary}
 except Exception as e:
  meta['error']=str(e);(R/(name+'.json')).write_text(json.dumps(meta,indent=2));return {'job':name,'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
 for x in ex.map(get,jobs): print(json.dumps(x))
