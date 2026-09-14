"""Research-only non-crypto market study. No trade authority or broker actions."""
import math, statistics, uuid
from urllib.parse import quote
import httpx
from config import SUPABASE_URL, SUPABASE_SECRET_KEY

H=5
ASSETS=[
("SPY","SPY","EQUITY_INDEX"),("QQQ","QQQ","EQUITY_INDEX"),("IWM","IWM","EQUITY_INDEX"),("DIA","DIA","EQUITY_INDEX"),
("SMH","SMH","SECTOR_ETF"),("XLE","XLE","SECTOR_ETF"),("XLF","XLF","SECTOR_ETF"),("TLT","TLT","RATES"),("HYG","HYG","CREDIT"),
("NVDA","NVDA","STOCK"),("AAPL","AAPL","STOCK"),("MSFT","MSFT","STOCK"),("AMZN","AMZN","STOCK"),("META","META","STOCK"),("GOOGL","GOOGL","STOCK"),("TSLA","TSLA","STOCK"),("AMD","AMD","STOCK"),("AVGO","AVGO","STOCK"),
("GOLD","GC=F","COMMODITY"),("SILVER","SI=F","COMMODITY"),("OIL","CL=F","COMMODITY"),("NATGAS","NG=F","COMMODITY"),("COPPER","HG=F","COMMODITY"),
("EURUSD","EURUSD=X","FX"),("GBPUSD","GBPUSD=X","FX"),("USDJPY","JPY=X","FX"),("AUDUSD","AUDUSD=X","FX"),("VIX","^VIX","VOLATILITY")]
http=httpx.Client(timeout=30.0,follow_redirects=True)

def _hdr(prefer=None):
 h={"apikey":SUPABASE_SECRET_KEY,"Authorization":f"Bearer {SUPABASE_SECRET_KEY}","Content-Type":"application/json"}
 if prefer:h["Prefer"]=prefer
 return h

def _history(ticker):
 u=f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker,safe='')}"
 r=http.get(u,params={"range":"5y","interval":"1d","events":"history"});r.raise_for_status();j=r.json()
 x=(((j.get("chart") or {}).get("result") or [None])[0]) or {};q=(((x.get("indicators") or {}).get("quote") or [{}])[0])
 out=[]
 for c in q.get("close") or []:
  try:v=float(c)
  except (TypeError,ValueError):continue
  if math.isfinite(v) and v>0:out.append(v)
 return out

def _sig(c,i):
 if i<60:return None
 return .2*(c[i]/c[i-5]-1)*100+.45*(c[i]/c[i-20]-1)*100+.35*(c[i]/c[i-60]-1)*100

def _study(c):
 if len(c)<200:return None
 s=_sig(c,len(c)-1)
 if s is None:return None
 xs=[]
 for i in range(max(60,len(c)-750-H),len(c)-H):
  z=_sig(c,i)
  if not z:continue
  f=(c[i+H]/c[i]-1)*100;xs.append((abs(z),abs(f),(f>0)==(z>0),f if z>0 else -f))
 if len(xs)<60:return None
 acc=sum(1 for x in xs if x[2])/len(xs);hist=statistics.median(x[1] for x in xs)
 rets=[c[i]/c[i-1]-1 for i in range(max(1,len(c)-30),len(c))]
 vol=statistics.pstdev(rets)*math.sqrt(H)*100 if len(rets)>10 else 0
 move=max(.1,.55*hist+.45*vol);score=move*max(.25,min(1.5,.5+(acc-.5)*3))*(1+min(1,abs(s)/10))
 return {"direction":"LONG" if s>=0 else "SHORT","entry_price":c[-1],"expected_move_pct":move,"research_score":score,"backtest_accuracy":acc,"backtest_samples":len(xs),"mean_directional_return_pct":statistics.mean(x[3] for x in xs),"signal_strength":s}

def run_cross_asset_research():
 scan=str(uuid.uuid4());rows=[];fail=[]
 for symbol,ticker,cls in ASSETS:
  try:
   x=_study(_history(ticker))
   if x:rows.append({"scan_id":scan,"symbol":symbol,"provider_symbol":ticker,"asset_class":cls,"horizon_days":H,"source":"Yahoo public chart API","research_only":True,**x,"details":{"trade_authority":False,"method":"5d momentum + realized-vol forward study"}})
   else:fail.append(symbol)
  except Exception:fail.append(symbol)
 rows.sort(key=lambda x:x["research_score"],reverse=True)
 if rows and SUPABASE_URL and SUPABASE_SECRET_KEY:
  r=http.post(f"{SUPABASE_URL}/rest/v1/cross_asset_research",headers=_hdr("return=minimal"),json=rows)
  if r.status_code>=300:raise RuntimeError(f"cross-asset persist failed {r.status_code}")
 return {"ok":bool(rows),"scan_id":scan,"research_only":True,"trade_authority":False,"researched":len(rows),"failures":fail,"leaders":rows[:10]}

def fetch_cross_asset_leaders(limit=20):
 if not (SUPABASE_URL and SUPABASE_SECRET_KEY):return []
 a=http.get(f"{SUPABASE_URL}/rest/v1/cross_asset_research",headers=_hdr(),params={"select":"scan_id","order":"generated_at.desc","limit":"1"})
 if a.status_code>=300 or not a.json():return []
 sid=a.json()[0]["scan_id"]
 r=http.get(f"{SUPABASE_URL}/rest/v1/cross_asset_research",headers=_hdr(),params={"select":"*","scan_id":f"eq.{sid}","order":"research_score.desc","limit":str(min(100,max(1,int(limit))))})
 return r.json() if r.status_code<300 else []
