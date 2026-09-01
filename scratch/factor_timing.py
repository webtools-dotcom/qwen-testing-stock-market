"""Does conditioning on the factor's own trailing performance fix the weak folds?

Factor return series f_t = (equal-weight next-day return of today's D10) - (universe mean), which
is known daily with no forward information. Then ask whether D10's forward 8d day-demeaned edge is
larger when the factor's trailing 60-day return is positive. Evaluated in the 6-cell frame.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from master_lab import build, report, dayt, CELLS

flat = build()
d = flat[flat["mid_small"]].copy()
d["ram"] = d["change_252d"] / d["vol60"].replace(0, np.nan)
d["q"] = d.groupby("date")["ram"].transform(
    lambda s: pd.qcut(s.rank(method="first"), 10, labels=False) if s.notna().sum() >= 10 else np.nan)

# next-day return, so the factor return uses only information available at t
d = d.sort_values(["ticker", "date"])
d["ret1_next"] = d.groupby("ticker")["ret1"].shift(-1)
uni = d.groupby("date")["ret1_next"].mean()
top = d[d.q == 9].groupby("date")["ret1_next"].mean()
fac = (top - uni).dropna().sort_index()
print(f"factor return series: {len(fac)} days, mean {fac.mean():+.4f}%/day", flush=True)

# trailing sums, shifted so day t uses only returns realised strictly before t
for w in (20, 60, 120):
    s = fac.rolling(w).sum().shift(1)
    d[f"fac{w}"] = s.reindex(pd.Index(d["date"].values)).values

sel = d[d.q == 9].copy()
print("\n=== D10 unconditional ===", flush=True)
print(report("D10 all", sel), flush=True)

for w in (20, 60, 120):
    print(f"\n=== conditioned on trailing {w}d factor return ===", flush=True)
    print(report(f"D10 & fac{w}>0", sel[sel[f"fac{w}"] > 0]), flush=True)
    print(report(f"D10 & fac{w}<=0", sel[sel[f"fac{w}"] <= 0]), flush=True)

print("\n=== fraction of days the gate is on ===", flush=True)
for w in (20, 60, 120):
    g = sel.groupby("date")[f"fac{w}"].first()
    print(f"  fac{w}>0 on {100*(g>0).mean():.0f}% of days", flush=True)

print("\n=== per-year, D10 & fac60>0 ===", flush=True)
g = sel[sel["fac60"] > 0]
for y, gg in g.groupby(g.date.dt.year):
    m, t, n = dayt(gg)
    print(f"  {y}: {m:+.3f}% t={t:+5.2f} days={n}", flush=True)
