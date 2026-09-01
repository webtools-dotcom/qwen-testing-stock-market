"""Where does the 022 signal actually decay? Measure the day-demeaned edge as a function of
holding period, free of portfolio machinery, in the 6-cell frame.

If the edge accumulates roughly linearly with horizon, there is no 'optimal' hold - only a
trade-off against cost drag, and the CAGR peak from the portfolio sweep is a noise crest on a
plateau. That distinction decides whether '40 sessions' means anything.
"""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from master_lab import load_panel, dayt, CELLS, P1_END, P2_END
from lab import features, NIFTY_50, MIN_TURNOVER

HZ = [5, 8, 10, 15, 21, 30, 40, 60, 90, 120]
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "cache", "_horizon_flat.pkl")

if os.path.exists(CACHE):
    flat = pickle.load(open(CACHE, "rb"))
else:
    panel = load_panel()
    rets = {}
    for t, df in panel.items():
        s = pd.Series(df["close"].pct_change().values, index=df["date"].values)
        rets[t] = s[~s.index.duplicated()]
    mkt = pd.DataFrame(rets).mean(axis=1).sort_index()
    rows = []
    for t, df in panel.items():
        d = features(df.copy().reset_index(drop=True), mkt)
        for h in HZ:
            d[f"fwd{h}"] = (d["close"].shift(-h) / d["close"] - 1) * 100
        d["ticker"] = t; d["mid_small"] = t not in NIFTY_50
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        rows.append(d)
    flat = pd.concat(rows, ignore_index=True)
    flat = flat[flat["liq"]].copy()
    for h in HZ:
        flat[f"fwd{h}_dm"] = flat[f"fwd{h}"] - flat.groupby("date")[f"fwd{h}"].transform("mean")
    names = sorted(flat["ticker"].unique())
    rng = np.random.default_rng(31)
    a = set(rng.permutation(names)[: len(names)//2])
    flat["half"] = np.where(flat["ticker"].isin(a), "A", "B")
    flat["period"] = np.where(flat["date"] <= P1_END, "P1",
                       np.where(flat["date"] <= P2_END, "P2", "P3"))
    pickle.dump(flat, open(CACHE, "wb"))

d = flat[flat["mid_small"]].copy()
d["ram"] = d["change_252d"] / d["vol60"].replace(0, np.nan)
d["q"] = d.groupby("date")["ram"].transform(
    lambda s: pd.qcut(s.rank(method="first"), 10, labels=False) if s.notna().sum() >= 10 else np.nan)
sel = d[d.q == 9]
print(f"top-decile name-days: {len(sel)}\n", flush=True)

COST = 0.45   # round-trip %, the engine's liquidity-tiered model averages near this
print(f"{'hold':>5s} {'edge%':>8s} {'t':>7s} {'edge/session':>13s} {'net of cost':>12s} "
      f"{'net/session':>12s}  cells>=1.5", flush=True)
for h in HZ:
    m, t, nd = dayt(sel, f"fwd{h}_dm")
    cs = [dayt(sel[(sel.half == hh) & (sel.period == p)], f"fwd{h}_dm")[1] for hh, p in CELLS]
    ok = sum(1 for x in cs if np.isfinite(x) and x >= 1.5)
    net = m - COST
    print(f"{h:5d} {m:+8.3f} {t:+7.2f} {m/h:+13.4f} {net:+12.3f} {net/h:+12.4f}  {ok}/6", flush=True)

print("\n=== is the edge linear in horizon? (a constant edge/session means no decay yet) ===",
      flush=True)
xs = np.array(HZ, float)
ys = np.array([dayt(sel, f"fwd{h}_dm")[0] for h in HZ])
slope, icept = np.polyfit(xs, ys, 1)
print(f"  fitted edge% = {slope:.4f} * hold {icept:+.3f}   (R^2 "
      f"{np.corrcoef(xs, ys)[0,1]**2:.3f})", flush=True)
print(f"  implied break-even hold at {COST}% round trip: {COST/slope:.0f} sessions", flush=True)
