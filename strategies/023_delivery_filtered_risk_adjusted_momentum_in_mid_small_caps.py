"""Strategy 023 - Delivery-Filtered Risk-Adjusted Momentum in Mid/Small Caps.

022's signal, minus the names whose NSE delivery percentage has fallen materially below their own
recent norm (dp_z < -1.0). Delivery data comes from NSE's own bhavcopy/MTO archives and is LAGGED
ONE SESSION, because NSE publishes it only after the session settles.

Rules and kill criteria pre-registered in the .md.

Run:  python strategies/023_delivery_filtered_risk_adjusted_momentum_in_mid_small_caps.py
"""

import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch"))

import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z, walk_forward_splits,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_TURNOVER = 25e7
HORIZON = 8
TOP_PCT = 0.90
DP_Z_FLOOR = -1.0                 # pre-committed: one sigma below the stock's own delivery norm
P1_END = pd.Timestamp("2020-12-31")
P2_END = pd.Timestamp("2023-12-31")
LO, HI = pd.Timestamp("2000-01-01"), pd.Timestamp("2026-08-21")
EXIT = dict(stop_atr_mult=99.0, target_atr_mult=99.0)      # time exit, control gets the same
BRACKET = dict()

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}


def build_panel():
    """Per-ticker frames carrying the score, its daily cross-sectional rank, the LAGGED delivery
    z-score, and vol/beta terciles for the matched control."""
    from deliv_lab import build as build_merged
    flat = build_merged()
    flat = flat.sort_values(["ticker", "date"])
    flat["mid_small"] = ~flat["ticker"].isin(NIFTY_50)
    flat["ram"] = flat["change_252d"] / flat["vol60"].replace(0, np.nan)

    elig = flat[flat["liq"] & flat["mid_small"]]
    flat.loc[elig.index, "rank"] = elig.groupby("date")["ram"].rank(pct=True)
    for c, n in (("atr_pct", "vol_t"), ("beta", "beta_t")):
        if c not in flat.columns:
            continue
        flat.loc[elig.index, n] = elig.groupby("date")[c].transform(
            lambda s: pd.qcut(s.rank(method="first"), 3, labels=False) if s.notna().sum() >= 3 else np.nan)

    panel = {}
    for t, g in flat.groupby("ticker", sort=False):
        g = g.reset_index(drop=True)
        panel[t] = g
    return panel


def slice_panel(panel, lo=LO, hi=HI, names=None, group="mid_small"):
    out = {}
    for t, d in panel.items():
        if group == "mid_small" and t in NIFTY_50:
            continue
        if group == "large" and t not in NIFTY_50:
            continue
        if names is not None and t not in names:
            continue
        dd = d[(d["date"] >= lo) & (d["date"] <= hi)]
        dd = dd.dropna(subset=["close", "atr"]).reset_index(drop=True)
        if len(dd) >= 40:
            out[t] = dd
    return out


def signal_mask(d, top_pct=TOP_PCT, dp_floor=DP_Z_FLOOR, use_filter=True):
    m = (d["rank"] >= top_pct).fillna(False).values & d["liq"].values
    if use_filter and dp_floor is not None:
        # exclude only names KNOWN to be below their delivery norm; missing delivery is not a reason
        # to exclude (that would silently drop the pre-2019 history)
        bad = (d["dp_z"] < dp_floor).fillna(False).values
        m = m & ~bad
    return m


def run_set(sub, horizon=HORIZON, next_open=False, matched=False, exit_kw=None, **kw):
    exit_kw = EXIT if exit_kw is None else exit_kw
    strat, stocks = [], []
    for t, d in sub.items():
        sig = signal_mask(d, **kw)
        if next_open:
            sig = np.roll(sig, 1)
            sig[0] = False
        strat += simulate_trades(d, sig, horizon_days=horizon, charge_costs=True, **exit_kw)
        stocks.append(d)

    if matched:
        cells = pd.concat([d.loc[signal_mask(d, **kw), ["date", "vol_t", "beta_t"]]
                           for d in stocks], ignore_index=True).dropna().drop_duplicates()
        cells["_ok"] = True
        stocks = [d.merge(cells, on=["date", "vol_t", "beta_t"], how="left")
                   .assign(_ok=lambda x: x["_ok"].fillna(False)) for d in stocks]

    def control_factory(seed):
        rng = np.random.default_rng(1000 + seed)
        ctrl = []
        for d in stocks:
            liq = d["liq"].values
            if matched:
                rnd = liq & d["_ok"].values & ~signal_mask(d, **kw) & (rng.random(len(d)) < 0.5)
            else:
                rnd = liq & (rng.random(len(d)) < 0.10)
            ctrl += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True, **exit_kw)
        return ctrl

    return strat, control_factory


def summarize(label, strat, cf, seeds=20):
    if len(strat) < 20:
        print(f"{label:44s} n={len(strat)} - too few trades", flush=True)
        return None
    st = stable_day_clustered_z(strat, cf, n_seeds=seeds)
    ctrl = cf(0)
    dc = day_clustered_edge(strat, ctrl)
    nets = np.array([t["net_pct"] for t in strat])
    cnets = np.array([t["net_pct"] for t in ctrl])
    print(f"{label:44s} n={len(strat):5d} days={dc['n_paired_days']:4d} "
          f"mean_z={st['mean_z']:+5.2f} pass={st['pass_rate']*100:3.0f}% "
          f"[{st['min_z']:+.2f},{st['max_z']:+.2f}] day_edge={dc['day_edge']:+.3f}% "
          f"net={nets.mean():+.3f}% (ctrl {cnets.mean():+.3f}%) win={100*(nets>0).mean():.0f}%",
          flush=True)
    return {"stable": st, "dc": dc, "net": float(nets.mean()), "n": len(strat)}


def main():
    panel = build_panel()
    names = sorted(panel)
    rng = np.random.default_rng(31)                     # same split the delivery search used
    A = set(rng.permutation(names)[: len(names) // 2])
    B = set(names) - A
    full = slice_panel(panel)
    print(f"universe {len(panel)} names, {len(full)} liquid mid/small\n", flush=True)

    print("== 1. head to head: filter off vs on (pooled) ==", flush=True)
    s, cf = run_set(full, use_filter=False)
    summarize("022 baseline (filter OFF)", s, cf)
    for h in (6, 8, 10):
        s, cf = run_set(full, horizon=h)
        summarize(f"023 filter ON h={h}", s, cf)

    print("\n== 2. hold-out half of names ==", flush=True)
    s, cf = run_set(slice_panel(panel, names=B))
    summarize("half B", s, cf)

    print("\n== 3. regime blocks ==", flush=True)
    for lbl, lo, hi in (("P1 2016-2020", LO, P1_END), ("P2 2021-2023", P1_END, P2_END),
                        ("P3 2024-2026", P2_END, HI)):
        s, cf = run_set(slice_panel(panel, lo, hi))
        summarize(lbl, s, cf)

    print("\n== 4. matched control / next-session / bracket ==", flush=True)
    s, cf = run_set(full, matched=True)
    summarize("vol-beta MATCHED control", s, cf)
    s, cf = run_set(full, next_open=True)
    summarize("next-session entry", s, cf)
    s, cf = run_set(full, exit_kw=BRACKET)
    summarize("engine-default ATR bracket", s, cf, seeds=10)

    print("\n== 5. filter-threshold gradient (fitted spike or plateau?) ==", flush=True)
    for f in (None, -1.5, -1.0, -0.5, 0.0):
        s, cf = run_set(full, dp_floor=f, use_filter=f is not None)
        summarize(f"dp_z floor {f}", s, cf, seeds=10)

    print("\n== 6. walk-forward ==", flush=True)
    dates = sorted({d for dd in full.values() for d in dd["date"]})
    zs = []
    for k, (tr, te) in enumerate(walk_forward_splits(len(dates), n_splits=5, horizon_days=HORIZON)):
        if len(te) == 0:
            continue
        f_lo, f_hi = dates[te[0]], dates[te[-1]]
        s, cf = run_set(slice_panel(panel, f_lo, f_hi))
        r = summarize(f"fold {k+1} {f_lo.date()}..{f_hi.date()}", s, cf, seeds=10)
        if r:
            zs.append(r["stable"]["mean_z"])
    print(f"   folds clearing 2.0: {sum(1 for z in zs if z >= 2.0)}/{len(zs)}", flush=True)


if __name__ == "__main__":
    main()
