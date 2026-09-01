"""Interrogate the intermediate-momentum cluster under the 3-way split."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from lab import build_flat, dayt, IS_END, FWD_START

flat = build_flat()
ms = flat[flat["mid_small"]].copy()

def tri(sel, col="fwd8_dm"):
    out = []
    for name, s2 in (("S", sel[(sel.half == "A") & (sel.date <= IS_END)]),
                     ("U", sel[(sel.half == "B") & (sel.date <= IS_END)]),
                     ("T", sel[sel.date >= FWD_START])):
        m, t, n = dayt(s2, col)
        out.append(f"{name} {m:+.3f}%/t{t:+5.2f}")
    return "  ".join(out)

def decile(df, col, n=10):
    return df.groupby("date")[col].transform(
        lambda s: pd.qcut(s.rank(method="first"), n, labels=False) if s.notna().sum() >= n else np.nan)

print("=== full decile ladder of ret_ex20_120 (intermediate momentum, 120d ex last 20d) ===")
sub = ms.dropna(subset=["ret_ex20_120"]).copy()
sub["q"] = decile(sub, "ret_ex20_120")
for d in range(10):
    print(f"  D{d+1:<2d} {tri(sub[sub.q == d])}")

print("\n=== full decile ladder of ret_ex5_20 (1-month momentum ex last week) ===")
s2 = ms.dropna(subset=["ret_ex5_20"]).copy()
s2["q"] = decile(s2, "ret_ex5_20")
for d in range(10):
    print(f"  D{d+1:<2d} {tri(s2[s2.q == d])}")

print("\n=== D10 of ret_ex20_120 within vol / beta / turnover terciles (hold-out sets matter) ===")
top = sub[sub.q == 9]
for var in ["atr_pct", "beta", "turnover_60d", "corr_mkt", "rsi", "close_sma20"]:
    s3 = sub.dropna(subset=[var]).copy()
    s3["tq"] = s3.groupby("date")[var].transform(
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=False) if s.notna().sum() >= 3 else np.nan)
    line = []
    for k in (0, 1, 2):
        cell = s3[(s3.q == 9) & (s3.tq == k)]
        line.append(f"T{k}[{tri(cell)}]")
    print(f"  {var:14s} " + " ".join(line))

print("\n=== combinations ===")
COMBOS = {
    "mom D10 only":                  lambda d: d.q == 9,
    "mom D10 + sma20_slope>0":       lambda d: (d.q == 9) & (d.sma20_slope > 0),
    "mom D10 + sma50_slope>0":       lambda d: (d.q == 9) & (d.sma50_slope > 0),
    "mom D10 + close>sma50":         lambda d: (d.q == 9) & (d.close_sma50 > 0),
    "mom D10 + both slopes>0":       lambda d: (d.q == 9) & (d.sma20_slope > 0) & (d.sma50_slope > 0),
    "mom D10 + rsi<60 (not extended)": lambda d: (d.q == 9) & (d.rsi < 60),
    "mom D10 + rsi>60":              lambda d: (d.q == 9) & (d.rsi > 60),
    "mom D10 + below sma20 (dip)":   lambda d: (d.q == 9) & (d.close_sma20 < 0),
    "mom D10 + above sma20":         lambda d: (d.q == 9) & (d.close_sma20 > 0),
    "mom D10 + low atr_pct half":    lambda d: (d.q == 9) & (d.atr_pct < d.groupby("date").atr_pct.transform("median")),
    "mom D10 + high atr_pct half":   lambda d: (d.q == 9) & (d.atr_pct > d.groupby("date").atr_pct.transform("median")),
    "mom D9+D10":                    lambda d: d.q >= 8,
    "mom D8-D10":                    lambda d: d.q >= 7,
}
for name, fn in COMBOS.items():
    sel = sub[fn(sub)]
    print(f"  {name:32s} n={len(sel):6d}  {tri(sel)}")

print("\n=== horizon check on 'mom D10 + both slopes>0' ===")
sel = sub[(sub.q == 9) & (sub.sma20_slope > 0) & (sub.sma50_slope > 0)]
for h in (6, 8, 10):
    print(f"  h={h:2d}: {tri(sel, col=f'fwd{h}_dm')}")

print("\n=== per-year (all names, mom D10 + both slopes) ===")
for y, g in sel.groupby(sel.date.dt.year):
    m, t, n = dayt(g)
    print(f"  {y}: {m:+.3f}%  t={t:+.2f}  days={n}")

print("\n=== large caps placebo (same rule, ranked within large caps) ===")
lg = flat[~flat["mid_small"]].dropna(subset=["ret_ex20_120"]).copy()
lg["q"] = decile(lg, "ret_ex20_120")
sel_l = lg[(lg.q == 9) & (lg.sma20_slope > 0) & (lg.sma50_slope > 0)]
print(f"  large n={len(sel_l)}  {tri(sel_l)}")
