"""Strategy 021, time-exit specification: decisive kills first, everything printed as it runs.

Exit spec is pre-declared before looking at the numbers: hold to the horizon, no ATR bracket.
Both strategy and control get the identical exit rule, so the comparison stays fair.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategies"))
import importlib
import numpy as np, pandas as pd
from backtest_engine import simulate_trades, walk_forward_splits

m = importlib.import_module("021_intermediate_momentum_top_decile_swing_in_mid_small_caps")
LO, FWD_END = pd.Timestamp("2000-01-01"), pd.Timestamp("2026-08-21")
IS_END, FWD_START = m.IS_END, m.FWD_START

panel = m.prepare(m.load())
A = m.half_split(panel)
B = set(panel) - A
print(f"universe {len(panel)} names; half A {len(A)}, half B {len(B)}", flush=True)

def go(label, sub, seeds=20, **kw):
    s, cf = m.run_set(sub, exit_spec="time", **kw)
    return m.summarize(label, s, cf, seeds=seeds)

print("\n== A. bracket vs time exit, search half A in-sample (sanity on the spec change) ==", flush=True)
sa = m.slice_panel(panel, LO, IS_END, names=A)
s, cf = m.run_set(sa, exit_spec="bracket"); m.summarize("half A, BRACKET exit", s, cf, seeds=10)
go("half A, TIME exit", sa, seeds=10)

print("\n== B. KILL #1: hold-out half of NAMES (B), in-sample, time exit ==", flush=True)
go("half B (never searched), h=8", m.slice_panel(panel, LO, IS_END, names=B))

print("\n== C. KILL #2: held-out forward window, time exit ==", flush=True)
for h in (6, 8, 10):
    go(f"forward all names h={h}", m.slice_panel(panel, FWD_START, FWD_END), horizon=h, seeds=10)
go("forward, half B only, h=8", m.slice_panel(panel, FWD_START, FWD_END, names=B))

print("\n== D. full sample, time exit ==", flush=True)
for h in (6, 8, 10):
    go(f"full sample h={h}", m.slice_panel(panel, LO, FWD_END), horizon=h, seeds=10)

print("\n== E. KILL #4: vol/beta-matched control (full sample) ==", flush=True)
go("MATCHED control h=8", m.slice_panel(panel, LO, FWD_END), matched=True)

print("\n== F. KILL #5: decile gradient (full sample, time exit) ==", flush=True)
full = m.slice_panel(panel, LO, FWD_END)
for lo_p, hi_p, name in ((0.90, 1.01, "D10"), (0.80, 0.90, "D9"), (0.70, 0.80, "D8"),
                         (0.45, 0.55, "D5"), (0.0, 0.10, "D1")):
    strat, stocks = [], []
    for t, d in full.items():
        msk = ((d["mom_rank"] >= lo_p) & (d["mom_rank"] < hi_p)).fillna(False).values & d["liq"].values
        strat += simulate_trades(d, msk, horizon_days=8, charge_costs=True, **m.EXITS["time"])
        stocks.append(d)
    def cf2(seed, stocks=stocks):
        rng = np.random.default_rng(1000 + seed)
        out = []
        for d in stocks:
            out += simulate_trades(d, d["liq"].values & (rng.random(len(d)) < 0.10),
                                   horizon_days=8, charge_costs=True, **m.EXITS["time"])
        return out
    m.summarize(name, strat, cf2, seeds=10)

print("\n== G. KILL #6: next-session entry ==", flush=True)
go("next-session entry h=8", m.slice_panel(panel, LO, FWD_END), next_open=True)

print("\n== H. KILL #7: walk-forward ==", flush=True)
dates = sorted({d for dd in full.values() for d in dd["date"]})
for k, (tr, te) in enumerate(walk_forward_splits(len(dates), n_splits=4, horizon_days=8)):
    f_lo, f_hi = dates[te[0]], dates[te[-1]]
    go(f"fold {k+1} {f_lo.date()}..{f_hi.date()}", m.slice_panel(panel, f_lo, f_hi), seeds=10)

print("\n== I. large-cap placebo ==", flush=True)
lg = {t: d for t, d in panel.items() if t in m.NIFTY_50}
flat = pd.concat([d[["date", "ticker", "mom", "liq"]] for d in lg.values()], ignore_index=True)
elig = flat[flat["liq"]]
flat.loc[elig.index, "r"] = elig.groupby("date")["mom"].rank(pct=True)
key = flat.set_index(["ticker", "date"])["r"]
lg2 = {}
for t, d in lg.items():
    d = d.copy()
    d["mom_rank"] = key.loc[t].reindex(pd.Index(d["date"].values)).values
    d = d[(d["date"] >= LO) & (d["date"] <= FWD_END)].dropna(subset=["close", "atr"]).reset_index(drop=True)
    if len(d) >= 40:
        lg2[t] = d
go("large caps h=8", lg2, seeds=10)
