"""Composite candidate: equal-weighted daily cross-sectional ranks of factors that were
consistent in >=5/6 cells of the 10-year scan. No tuned weights.

Deliberately EXCLUDES pure volatility/beta proxies (atr_pct, maxret20, vol20/60, corr_mkt) even
though they scanned well - selecting on them makes the strategy a leverage bet, which is the
failure mode this repo has flagged before and which the matched control exists to catch.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from lab10 import build, cells, fmt_cells, dayt, CELLS

flat = build()
ms = flat[flat["mid_small"]].copy()
ms["ram"] = ms["change_252d"] / ms["vol60"].replace(0, np.nan)

def r(col):
    return ms.groupby("date")[col].rank(pct=True)

ms["r_ram"] = r("ram")
ms["r_slope"] = r("sma50_slope")
ms["r_skew"] = r("skew60")
ms["r_rng"] = r("rng_pos5")
ms["r_mom"] = r("change_252d")

COMPOSITES = {
    "C0 ram alone (=022)":            ms["r_ram"],
    "C1 ram+slope":                   ms["r_ram"] + ms["r_slope"],
    "C2 ram+slope+skew":              ms["r_ram"] + ms["r_slope"] + ms["r_skew"],
    "C3 ram+slope+skew-rng":          ms["r_ram"] + ms["r_slope"] + ms["r_skew"] - ms["r_rng"],
    "C4 ram-rng":                     ms["r_ram"] - ms["r_rng"],
    "C5 ram+skew":                    ms["r_ram"] + ms["r_skew"],
    "C6 mom+slope+skew-rng":          ms["r_mom"] + ms["r_slope"] + ms["r_skew"] - ms["r_rng"],
}

print("=== composite top-decile, 6 cells, h=8 ===", flush=True)
for name, sc in COMPOSITES.items():
    ms["_c"] = sc
    sub = ms.dropna(subset=["_c"]).copy()
    sub["q"] = sub.groupby("date")["_c"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 10, labels=False) if s.notna().sum() >= 10 else np.nan)
    sel = sub[sub.q == 9]
    c = cells(sel)
    _, tB, _ = dayt(sel[sel.half == "B"])
    print(f"  {name:26s} {fmt_cells(c)}  | halfB t{tB:+5.2f}  {sel.groupby('date').size().mean():.1f}/day",
          flush=True)

print("\n=== best composite: yearly stability ===", flush=True)
ms["_c"] = COMPOSITES["C3 ram+slope+skew-rng"]
sub = ms.dropna(subset=["_c"]).copy()
sub["q"] = sub.groupby("date")["_c"].transform(
    lambda s: pd.qcut(s.rank(method="first"), 10, labels=False) if s.notna().sum() >= 10 else np.nan)
sel = sub[sub.q == 9]
for y, g in sel.groupby(sel.date.dt.year):
    mm, tt, nn = dayt(g)
    print(f"  {y}: {mm:+.3f}%  t={tt:+5.2f}  days={nn}", flush=True)
