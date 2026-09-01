import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yfinance as yf, pandas as pd
TICKS = {"usdinr":"USDINR=X","brent":"BZ=F","wti":"CL=F","gold":"GC=F","spx":"^GSPC",
         "ndx":"^IXIC","dxy":"DX-Y.NYB","vix":"^VIX","copper":"HG=F","nifty":"^NSEI",
         "niftybank":"^NSEBANK","niftyit":"^CNXIT","niftymid":"^NSEMDCP50","india_vix":"^INDIAVIX"}
out={}
for k,t in TICKS.items():
    try:
        raw = yf.download(t, period="10y", interval="1d", auto_adjust=True, progress=False)
        if raw is None or len(raw)<200: print("skip",k,len(raw) if raw is not None else 0); continue
        if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)
        out[k]=pd.Series(raw["Close"].values, index=pd.to_datetime(raw.index)).sort_index()
        print(f"{k:10s} {len(out[k])} bars {out[k].index.min().date()}..{out[k].index.max().date()}")
    except Exception as e: print("fail",k,e)
pickle.dump(out, open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"cache","macro.pkl"),"wb"))
print("saved", len(out))
