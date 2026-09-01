import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from lab10 import build, cells, fmt_cells, dayt, CELLS

flat = build()
ms = flat[flat["mid_small"]].copy()
ms["sharpe120"] = (ms["ret120"] - ms["ret20"]) / ms["vol60"].replace(0, np.nan)
ms["sharpe252"] = ms["change_252d"] / ms["vol60"].replace(0, np.nan)

def dec(df, col, n=10):
    return df.groupby("date")[col].transform(
        lambda s: pd.qcut(s.rank(method="first"), n, labels=False) if s.notna().sum() >= n else np.nan)

CAND = ["sharpe60", "sharpe120", "sharpe252", "change_252d", "ret120", "ret60"]
print("=== candidate D10, all 6 cells, h=8 ===")
store = {}
for c in CAND:
    sub = ms.dropna(subset=[c]).copy()
    sub["q"] = dec(sub, c)
    store[c] = sub
    print(f"  {c:12s} {fmt_cells(cells(sub[sub.q == 9]))}")

print("\n=== horizon sensitivity (pooled + hold-out half B only) ===")
for c in CAND:
    sub = store[c]; sel = sub[sub.q == 9]
    line = []
    for h in (6, 8, 10):
        _, t_all, _ = dayt(sel, f"fwd{h}_dm")
        _, t_b, _ = dayt(sel[sel.half == "B"], f"fwd{h}_dm")
        line.append(f"h{h}: all t{t_all:+5.2f} / B t{t_b:+5.2f}")
    print(f"  {c:12s} " + "  ".join(line))

print("\n=== decile ladder, sharpe60 (monotone?) ===")
sub = store["sharpe60"]
for d in range(10):
    c = cells(sub[sub.q == d])
    print(f"  D{d+1:<3d} {c['ALL'][0]:+.3f}%/t{c['ALL'][1]:+5.2f}   cells " +
          " ".join(f"{h}{p}{c[f'{h}{p}'][1]:+5.2f}" for h, p in CELLS))

print("\n=== breadth: names selected per day (drives engine z) ===")
for c in CAND:
    sub = store[c]; sel = sub[sub.q == 9]
    print(f"  {c:12s} {sel.groupby('date').size().mean():.1f} names/day, {sel.date.nunique()} days")

print("\n=== large caps (should be weaker/dead if the thesis is mid/small) ===")
lg = flat[~flat["mid_small"]].copy()
lg["sharpe252"] = lg["change_252d"] / lg["vol60"].replace(0, np.nan)
for c in ["sharpe60", "change_252d"]:
    s = lg.dropna(subset=[c]).copy()
    s["q"] = dec(s, c)
    print(f"  large {c:12s} {fmt_cells(cells(s[s.q == 9]))}")

print("\n=== per-year, sharpe60 D10 (mid/small) ===")
sel = store["sharpe60"]; sel = sel[sel.q == 9]
for y, g in sel.groupby(sel.date.dt.year):
    m, t, n = dayt(g)
    print(f"  {y}: {m:+.3f}%  t={t:+5.2f}  days={n}")
