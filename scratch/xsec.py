"""Cheap pre-screen: day-demeaned forward 8d return by decile of a feature.

The paired day-clustered test measures cross-sectional SELECTION skill (market move is netted
out). So a feature with no day-demeaned forward-return spread can never pass it. This scans many
features fast; only survivors go to the real engine.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from hunt import load, enrich, IS_END, MIN_TURNOVER, NIFTY_50

H = 8

def build(cache="sector_leadlag_5y", horizon=H):
    panel = enrich(load(cache))
    rows = []
    for t, d in panel.items():
        d = d.copy()
        d["fwd"] = (d["close"].shift(-horizon) / d["close"] - 1) * 100
        d["liq"] = d["turnover_60d"] >= MIN_TURNOVER
        d["mid_small"] = t not in NIFTY_50
        rows.append(d)
    df = pd.concat(rows, ignore_index=True)
    df = df[df["liq"] & df["fwd"].notna()]
    df["fwd_dm"] = df["fwd"] - df.groupby("date")["fwd"].transform("mean")
    return df

def deciles(df, col, n=10, label=""):
    sub = df[df[col].notna()].copy()
    if len(sub) < 2000:
        return f"{col:22s} {label:9s} too few rows ({len(sub)})"
    sub["q"] = sub.groupby("date")[col].transform(lambda s: pd.qcut(s.rank(method="first"), n, labels=False)
                                                  if s.notna().sum() >= n else np.nan)
    g = sub.groupby("q")["fwd_dm"].agg(["mean", "count"])
    # per-day mean of the top/bottom bucket -> t-stat over days (this IS the paired concept)
    def tstat(qv):
        daily = sub[sub["q"] == qv].groupby("date")["fwd_dm"].mean()
        return daily.mean() / (daily.std(ddof=1) / np.sqrt(len(daily))) if len(daily) > 5 else np.nan
    cells = " ".join(f"{g['mean'].get(i, np.nan):+.2f}" for i in range(n))
    return (f"{col:22s} {label:9s} D1..D{n}: {cells}  | t(D1)={tstat(0):+.2f} t(D{n})={tstat(n-1):+.2f}")
