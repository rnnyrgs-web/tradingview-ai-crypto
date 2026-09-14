"""Research-only non-crypto market study. No trade authority or broker actions."""
import csv, io, math, statistics, uuid
import httpx
from config import SUPABASE_URL, SUPABASE_SECRET_KEY

H=5
ASSETS=[
("SPY","spy.us","EQUITY_INDEX"),("QQQ","qqq.us","EQUITY_INDEX"),("IWM","iwm.us","EQUITY_INDEX"),("DIA","dia.us","EQUITY_INDEX"),
("SMH","smh.us","SECTOR_ETF"),("XLE","xle.us","SECTOR_ETF"),("XLF","xlf.us","SECTOR_ETF"),("TLT","tlt.us","RATES"),("HYG","hyg.us","CREDIT"),
("NVDA","nvda.us","STOCK"),("AAPL","aapl.us","STOCK"),("MSFT","msft.us","STOCK"),("AMZN","amzn.us","STOCK"),("META","meta.us","STOCK"),("GOOGL","googl.us","STOCK"),("TSLA","tsla.us","STOCK"),("AMD","amd.us","STOCK"),("AVGO","avgo.us","STOCK"),
("GOLD","gld.us","COMMODITY_ETF"),("SILVER","slv.us","COMMODITY_ETF"),("OIL","uso.us","COMMODITY_ETF"),("NATGAS","ung.us","COMMODITY_ETF"),("COPPER","cper.us","COMMODITY_ETF"),
("EURUSD","eurusd","FX"),("GBPUSD","gbpusd","FX"),("USDJPY","usdjpy","FX"),("AUDUSD","audusd","FX"),("VXX","vxx.us","VOLATILITY_ETP")]
http=httpx.Client(timeout=30.0,follow_redirects=True,headers={"User-Agent":"Mozilla/5.0 research-only market study"})

def _hdr(prefer=None):
 h={"apikey":SUPABASE_SECRET_KEY,"Authorization":f"Bearer {SUPABASE_SECRET_KEY}","Content-Type":"application/json"}
 if prefer:h["Prefer"]=prefer
 return h

def _history(ticker):
 r=http.get("https://stooq.com/q/d/l/",params={"s":ticker,"i":"d"});r.raise_for_status()
 out=[]
 for row in csv.DictReader(io.StringIO(r.text)):
  try:v=float(row.get("Close") or 0)
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
   if x:rows.append({"scan_id":scan,"symbol":symbol,"provider_symbol":ticker,"asset_class":cls,"horizon_days":H,"source":"Stooq public daily history","research_only":True,**x,"details":{"trade_authority":False,"method":"5d momentum + realized-vol forward study","underlying_or_proxy":"tradable ETF/equity/FX"}})
   else:fail.append({"symbol":symbol,"reason":"insufficient_history"})
  except Exception as exc:fail.append({"symbol":symbol,"reason":type(exc).__name__})
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
