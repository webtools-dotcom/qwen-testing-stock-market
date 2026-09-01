import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from xsec import build, deciles
from hunt import IS_END

df = build()
df = df[(df["date"] <= IS_END) & df["mid_small"]].copy()
df["turn_ratio"] = df["turnover"] / df["turnover_60d"]
df["turn_ratio20"] = df.groupby("ticker")["turn_ratio"].transform(lambda s: s.rolling(20).mean())

def dayt(sub):
    daily = sub.groupby("date")["fwd_dm"].mean()
    return daily.mean(), daily.mean()/(daily.std(ddof=1)/np.sqrt(len(daily))), len(daily)

print("--- per-year t for amihud_z bottom decile (mid/small) ---")
df["q_am"] = df.groupby("date")["amihud_z"].transform(lambda s: pd.qcut(s.rank(method="first"),10,labels=False) if s.notna().sum()>=10 else np.nan)
for y, g in df[df.q_am==0].groupby(df["date"].dt.year):
    m,t,n = dayt(g); print(f"  {y}: mean_dm {m:+.3f}%  t {t:+.2f}  days {n}")
print("  all:", dayt(df[df.q_am==0]))

print("\n--- double sort: amihud decile within momentum_60d tercile ---")
df["q_mom"] = df.groupby("date")["momentum_60d"].transform(lambda s: pd.qcut(s.rank(method="first"),3,labels=False) if s.notna().sum()>=3 else np.nan)
for mq in [0,1,2]:
    sub = df[df.q_mom==mq]
    lo = sub[sub.q_am==0]; hi = sub[sub.q_am==9]
    print(f"  mom tercile {mq}: amihudD1 {dayt(lo)[0]:+.3f}% t={dayt(lo)[1]:+.2f} | amihudD10 {dayt(hi)[0]:+.3f}% t={dayt(hi)[1]:+.2f}")

print("\n--- double sort: amihud decile within atr_pct tercile (vol control) ---")
df["q_vol"] = df.groupby("date")["atr_pct"].transform(lambda s: pd.qcut(s.rank(method="first"),3,labels=False) if s.notna().sum()>=3 else np.nan)
for vq in [0,1,2]:
    sub = df[df.q_vol==vq]; lo = sub[sub.q_am==0]
    print(f"  vol tercile {vq}: amihudD1 {dayt(lo)[0]:+.3f}% t={dayt(lo)[1]:+.2f} n_days={dayt(lo)[2]}")

print("\n--- double sort: amihud decile within beta tercile ---")
df["q_beta"] = df.groupby("date")["beta"].transform(lambda s: pd.qcut(s.rank(method="first"),3,labels=False) if s.notna().sum()>=3 else np.nan)
for bq in [0,1,2]:
    sub = df[df.q_beta==bq]; lo = sub[sub.q_am==0]
    print(f"  beta tercile {bq}: amihudD1 {dayt(lo)[0]:+.3f}% t={dayt(lo)[1]:+.2f}")

print("\n--- simpler cousins (is it just turnover?) ---")
for f in ["turn_ratio20","turn_ratio","amihud"]:
    print(deciles(df, f, label="mid/small"))
