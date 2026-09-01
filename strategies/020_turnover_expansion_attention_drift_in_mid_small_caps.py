"""Strategy 020 - Turnover Expansion Attention Drift in Mid/Small Caps.

Buys liquid NSE mid/small caps whose 20-day average rupee turnover is in the top cross-sectional
decile relative to their own 60-day baseline, holds 8 sessions. Rules and kill criteria are
pre-registered in the .md - in particular the momentum/vol-matched control (kill #4) and the
held-out forward window (kill #7).

Run:  python strategies/020_turnover_expansion_attention_drift_in_mid_small_caps.py
"""

import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z, walk_forward_splits,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_END = pd.Timestamp("2025-06-30")       # search window; everything after is held out
MIN_TURNOVER = 25e7
HORIZON = 8
TOP_PCT = 0.90                            # top decile of turn_ratio20

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}


# ---------------------------------------------------------------- data prep
def load(cache):
    obj = pickle.load(open(os.path.join(BASE, "cache", cache + ".pkl"), "rb"))
    return obj["data"] if isinstance(obj, dict) and "data" in obj else obj


def prepare(panel, rank_universe="mid_small"):
    """Add turn_ratio20 and its cross-sectional daily rank, plus momentum/vol tercile labels
    (used by the matched control). Every input is known at that bar's close."""
    prepped = {}
    for t, df in panel.items():
        d = df.copy().reset_index(drop=True)
        d["ticker"] = t
        d["mid_small"] = t not in NIFTY_50
        d["turn20"] = d["turnover"].rolling(20).mean()
        d["turn_ratio20"] = d["turn20"] / d["turnover_60d"]
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        prepped[t] = d

    flat = pd.concat([d[["date", "ticker", "turn_ratio20", "momentum_60d", "atr_pct", "liq",
                         "mid_small"]] for d in prepped.values()], ignore_index=True)
    mask = flat["liq"] if rank_universe == "all" else (flat["liq"] & flat["mid_small"])
    elig = flat[mask]
    flat.loc[elig.index, "tr_rank"] = elig.groupby("date")["turn_ratio20"].rank(pct=True)
    for c, n in (("momentum_60d", "mom_t"), ("atr_pct", "vol_t")):
        flat.loc[elig.index, n] = elig.groupby("date")[c].transform(
            lambda s: pd.qcut(s.rank(method="first"), 3, labels=False) if s.notna().sum() >= 3 else np.nan)
    key = flat.set_index(["ticker", "date"])[["tr_rank", "mom_t", "vol_t"]]
    for t, d in prepped.items():
        sub = key.loc[t]
        idx = pd.Index(d["date"].values)
        for c in ("tr_rank", "mom_t", "vol_t"):
            d[c] = sub[c].reindex(idx).values
    return prepped


def slice_panel(panel, lo, hi, group="mid_small"):
    out = {}
    for t, d in panel.items():
        if group == "mid_small" and t in NIFTY_50:
            continue
        if group == "large" and t not in NIFTY_50:
            continue
        dd = d[(d["date"] >= lo) & (d["date"] <= hi)]
        dd = dd.dropna(subset=["close", "atr"]).reset_index(drop=True)
        if len(dd) >= 60:
            out[t] = dd
    return out


# ---------------------------------------------------------------- signal + runners
def signal_mask(d, top_pct=TOP_PCT):
    return (d["tr_rank"] >= top_pct).fillna(False).values & d["liq"].values


def run_set(sub, top_pct=TOP_PCT, horizon=HORIZON, next_open=False, matched=False):
    """Simulate the strategy and build a control factory. matched=True draws the control from the
    SAME days and the same momentum/vol tercile cells the strategy traded (kill #4)."""
    strat, stocks = [], []
    for t, d in sub.items():
        sig = signal_mask(d, top_pct)
        if next_open:                      # entry delayed one bar (fills at the next session)
            sig = np.roll(sig, 1)
            sig[0] = False
        strat += simulate_trades(d, sig, horizon_days=horizon, charge_costs=True)
        stocks.append(d)

    cells = None
    if matched:
        cells = set()
        for d in stocks:
            m = signal_mask(d, top_pct)
            for i in np.where(m)[0]:
                mt, vt = d["mom_t"].iat[i], d["vol_t"].iat[i]
                if np.isfinite(mt) and np.isfinite(vt):
                    cells.add((d["date"].iat[i], mt, vt))

    def control_factory(seed):
        rng = np.random.default_rng(1000 + seed)
        ctrl = []
        for d in stocks:
            liq = d["liq"].values
            if matched:
                ok = np.array([(d["date"].iat[i], d["mom_t"].iat[i], d["vol_t"].iat[i]) in cells
                               for i in range(len(d))])
                pool = liq & ok & ~signal_mask(d, top_pct)
                rnd = pool & (rng.random(len(d)) < 0.5)
            else:
                rnd = liq & (rng.random(len(d)) < 0.10)
            ctrl += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        return ctrl

    return strat, control_factory


def summarize(label, strat, cf, seeds=20):
    if len(strat) < 20:
        print(f"{label:44s} n={len(strat)} - too few trades")
        return None
    st = stable_day_clustered_z(strat, cf, n_seeds=seeds)
    dc = day_clustered_edge(strat, cf(0))
    nets = np.array([t["net_pct"] for t in strat])
    print(f"{label:44s} n={len(strat):5d} days={dc['n_paired_days']:4d} "
          f"mean_z={st['mean_z']:+5.2f} pass={st['pass_rate']*100:3.0f}% "
          f"[{st['min_z']:+.2f},{st['max_z']:+.2f}] day_edge={dc['day_edge']:+.3f}% "
          f"net/trade={nets.mean():+.3f}% win={100*(nets>0).mean():.0f}%")
    return {"stable": st, "dc": dc, "net": float(nets.mean())}


def main():
    panel = prepare(load("sector_leadlag_5y"))
    lo = pd.Timestamp("2000-01-01")
    ms = slice_panel(panel, lo, IS_END)
    print(f"IN-SAMPLE (to {IS_END.date()}), mid/small names: {len(ms)}\n")

    print("== headline ==")
    s, cf = run_set(ms)
    summarize("mid/small, h=8, random control", s, cf)

    print("\n== kill #4: momentum/vol-matched control ==")
    s2, cf2 = run_set(ms, matched=True)
    summarize("mid/small, h=8, MATCHED control", s2, cf2)

    print("\n== kill #5: threshold robustness ==")
    for tp in (0.80, 0.85, 0.90, 0.95):
        s3, cf3 = run_set(ms, top_pct=tp)
        summarize(f"top {100*(1-tp):.0f}%", s3, cf3, seeds=10)

    print("\n== horizon band 6-10 ==")
    for h in (6, 8, 10):
        s4, cf4 = run_set(ms, horizon=h)
        summarize(f"h={h}", s4, cf4, seeds=10)

    print("\n== execution fragility: next-session entry ==")
    s5, cf5 = run_set(ms, next_open=True)
    summarize("mid/small, next-session", s5, cf5)

    print("\n== walk-forward (mid/small, h=8) ==")
    dates = sorted({d for dd in ms.values() for d in dd["date"]})
    for k, (tr, te) in enumerate(walk_forward_splits(len(dates), n_splits=4, horizon_days=HORIZON)):
        f_lo, f_hi = dates[te[0]], dates[te[-1]]
        fold = slice_panel(panel, f_lo, f_hi)
        sf, cff = run_set(fold)
        summarize(f"fold {k+1} {f_lo.date()}..{f_hi.date()}", sf, cff, seeds=10)


if __name__ == "__main__":
    main()
