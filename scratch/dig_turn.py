import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from xsec import build, deciles
from hunt import IS_END

df = build()
df = df[(df["date"] <= IS_END)].copy()
df["turn_ratio20"] = df.groupby("ticker")["turnover"].transform(
    lambda s: s.rolling(20).mean()) / df["turnover_60d"]

def dayt(sub):
    d = sub.groupby("date")["fwd_dm"].mean()
    return (d.mean(), d.mean()/(d.std(ddof=1)/np.sqrt(len(d))) if len(d)>5 else np.nan, len(d))

for lbl, sel in [("ALL", df), ("mid/small", df[df.mid_small]), ("large", df[~df.mid_small])]:
    s = sel.copy()
    s["q"] = s.groupby("date")["turn_ratio20"].transform(lambda x: pd.qcut(x.rank(method="first"),10,labels=False) if x.notna().sum()>=10 else np.nan)
    m,t,n = dayt(s[s.q==9]); print(f"{lbl:10s} D10: {m:+.3f}% t={t:+.2f} days={n}")
    m,t,n = dayt(s[s.q==0]); print(f"{lbl:10s}  D1: {m:+.3f}% t={t:+.2f} days={n}")

ms = df[df.mid_small].copy()
ms["q"] = ms.groupby("date")["turn_ratio20"].transform(lambda x: pd.qcut(x.rank(method="first"),10,labels=False) if x.notna().sum()>=10 else np.nan)
print("\n--- per-year, mid/small D10 ---")
for y,g in ms[ms.q==9].groupby(ms["date"].dt.year):
    m,t,n = dayt(g); print(f"  {y}: {m:+.3f}%  t={t:+.2f}  days={n}")

print("\n--- D10 within momentum tercile / vol tercile / beta tercile ---")
for var in ["momentum_60d","atr_pct","beta","ret20","rsi"]:
    ms["qq"] = ms.groupby("date")[var].transform(lambda x: pd.qcut(x.rank(method="first"),3,labels=False) if x.notna().sum()>=3 else np.nan)
    out=[]
    for k in [0,1,2]:
        m,t,n = dayt(ms[(ms.q==9)&(ms.qq==k)]); out.append(f"T{k} {m:+.3f}%/t{t:+.2f}")
    print(f"  {var:14s} " + " | ".join(out))

print("\n--- horizon sensitivity of D10 (mid/small) ---")
from xsec import build as b2
for h in (4,6,8,10,15,20):
    d2 = b2(horizon=h); d2 = d2[(d2.date<=IS_END)&d2.mid_small].copy()
    d2["turn_ratio20"] = d2.groupby("ticker")["turnover"].transform(lambda s: s.rolling(20).mean())/d2["turnover_60d"]
    d2["q"] = d2.groupby("date")["turn_ratio20"].transform(lambda x: pd.qcut(x.rank(method="first"),10,labels=False) if x.notna().sum()>=10 else np.nan)
    m,t,n = dayt(d2[d2.q==9]); print(f"  h={h:2d}: {m:+.3f}% t={t:+.2f}")
