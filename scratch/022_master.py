"""022 on the 629-name master universe (union of the curated panel and the full NSE EQ list).

Prediction stated in 022's .md BEFORE this ran: if the effect is real, day_edge stays near +0.4%
while per-fold z rises with breadth; if day_edge collapses, the effect was panel-specific.

Also runs the two things 022 still owed: per-fold evidence on the least survivorship-contaminated
subgroup (names listed before 2017), and the search deflation (§9).
"""
import sys, os, importlib, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategies"))
import numpy as np, pandas as pd
from backtest_engine import walk_forward_splits, sharpe, deflated_sharpe

m = importlib.import_module("022_risk_adjusted_12_month_momentum_swing_in_mid_small_caps")
LO, HI = m.LO, m.HI
P1_END, P2_END = m.P1_END, m.P2_END

panel = m.prepare(m.load("master_10y"))
print(f"master universe: {len(panel)} names", flush=True)

# names that were never in the 487-name panel the search used
old_obj = pickle.load(open(os.path.join(m.BASE, "cache", "broad_nse_10y.pkl"), "rb"))
searched = set(old_obj["data"].keys())
fresh = set(panel) - searched
print(f"names never used in any search here: {len(fresh)}", flush=True)

full = m.slice_panel(panel)
print(f"liquid mid/small with history: {len(full)}\n", flush=True)

print("== breadth check (the whole point) ==", flush=True)
s, cf = m.run_set(full)
r = m.summarize("master pooled h=8", s, cf)
days = r["dc"]["n_paired_days"]
print(f"   entries/day = {r['n']/days:.2f}   (487-name panel gave 2.78/day)", flush=True)

print("\n== hold-out slices ==", flush=True)
s, cf = m.run_set(m.slice_panel(panel, names=fresh))
m.summarize(f"fresh names only ({len(fresh)})", s, cf)

print("\n== regime blocks ==", flush=True)
for lbl, lo, hi in (("P1 2016-2020", LO, P1_END), ("P2 2021-2023", P1_END, P2_END),
                    ("P3 2024-2026", P2_END, HI)):
    s, cf = m.run_set(m.slice_panel(panel, lo, hi))
    m.summarize(lbl, s, cf)

print("\n== walk-forward, 5 folds (the criterion 022 failed) ==", flush=True)
dates = sorted({d for dd in full.values() for d in dd["date"]})
fold_z = []
for k, (tr, te) in enumerate(walk_forward_splits(len(dates), n_splits=5, horizon_days=8)):
    if len(te) == 0:
        continue
    f_lo, f_hi = dates[te[0]], dates[te[-1]]
    s, cf = m.run_set(m.slice_panel(panel, f_lo, f_hi))
    rr = m.summarize(f"fold {k+1} {f_lo.date()}..{f_hi.date()}", s, cf, seeds=10)
    if rr:
        fold_z.append(rr["stable"]["mean_z"])
print(f"   folds clearing 2.0: {sum(1 for z in fold_z if z >= 2.0)}/{len(fold_z)}", flush=True)

print("\n== survivorship: names listed before 2017 only, incl. per fold ==", flush=True)
first = {t: d["date"].min() for t, d in panel.items()}
old = {t for t, dt in first.items() if dt <= pd.Timestamp("2017-01-01")}
print(f"   {len(old)} old names", flush=True)
s, cf = m.run_set(m.slice_panel(panel, names=old))
m.summarize("old names, pooled", s, cf)
for k, (tr, te) in enumerate(walk_forward_splits(len(dates), n_splits=5, horizon_days=8)):
    if len(te) == 0:
        continue
    f_lo, f_hi = dates[te[0]], dates[te[-1]]
    s, cf = m.run_set(m.slice_panel(panel, f_lo, f_hi, names=old))
    m.summarize(f"  old fold {k+1}", s, cf, seeds=10)

print("\n== search deflation (METHODOLOGY 6/9) ==", flush=True)
s, cf = m.run_set(full)
obs = sharpe([t["net_pct"] for t in s], holding_days=8)
trial_srs = []
for tp in (0.95, 0.90, 0.85, 0.80, 0.70, 0.60, 0.50):
    ss, _ = m.run_set(full, top_pct=tp)
    trial_srs.append(sharpe([t["net_pct"] for t in ss], holding_days=8))
print(f"   observed SR {obs:.3f}; trial SRs {[round(x,3) for x in trial_srs]}", flush=True)
ds = deflated_sharpe(obs, trial_srs, n_obs=len(s))
print(f"   deflated: {ds}", flush=True)
