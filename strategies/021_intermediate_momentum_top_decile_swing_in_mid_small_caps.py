"""Strategy 021 - Intermediate Momentum Top Decile Swing in Mid/Small Caps.

Buys liquid NSE mid/small caps in the top cross-sectional decile of intermediate momentum
(120-session return excluding the last 20 sessions), holds 8 sessions, no other filter.
Rules and kill criteria pre-registered in the .md. The decisive checks are the hold-out HALF OF
NAMES (kill 1) and the held-out forward window (kill 2) - the pair that killed strategy 020.

Run:  python strategies/021_intermediate_momentum_top_decile_swing_in_mid_small_caps.py
"""

import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z, walk_forward_splits,
    edge_vs_control, sharpe,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_END = pd.Timestamp("2025-06-30")
FWD_START = pd.Timestamp("2025-07-01")
MIN_TURNOVER = 25e7
HORIZON = 8
TOP_PCT = 0.90

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}


def load(cache="broad_nse_5y"):
    obj = pickle.load(open(os.path.join(BASE, "cache", cache + ".pkl"), "rb"))
    return obj["data"] if isinstance(obj, dict) and "data" in obj else obj


def prepare(panel):
    """Add the momentum signal, its daily cross-sectional rank among liquid mid/smalls, and the
    vol/beta tercile labels the matched control needs. Everything is known at that bar's close."""
    mkt = {}
    for t, df in panel.items():
        s = pd.Series(df["close"].pct_change().values, index=df["date"].values)
        mkt[t] = s[~s.index.duplicated()]
    mkt = pd.DataFrame(mkt).mean(axis=1).sort_index()

    prepped = {}
    for t, df in panel.items():
        d = df.copy().reset_index(drop=True)
        c = d["close"]
        d["ticker"] = t
        d["mid_small"] = t not in NIFTY_50
        d["mom"] = (c.pct_change(120) - c.pct_change(20)) * 100     # 120d return ex last 20d
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        m1 = mkt.reindex(pd.Index(d["date"].values)).values * 100
        d["beta"] = (pd.Series(d["close"].pct_change().values * 100).rolling(120).cov(pd.Series(m1))
                     / pd.Series(m1).rolling(120).var())
        prepped[t] = d

    flat = pd.concat([d[["date", "ticker", "mom", "atr_pct", "beta", "liq", "mid_small"]]
                      for d in prepped.values()], ignore_index=True)
    elig = flat[flat["liq"] & flat["mid_small"]]
    flat.loc[elig.index, "mom_rank"] = elig.groupby("date")["mom"].rank(pct=True)
    for c, n in (("atr_pct", "vol_t"), ("beta", "beta_t")):
        flat.loc[elig.index, n] = elig.groupby("date")[c].transform(
            lambda s: pd.qcut(s.rank(method="first"), 3, labels=False) if s.notna().sum() >= 3 else np.nan)
    key = flat.set_index(["ticker", "date"])[["mom_rank", "vol_t", "beta_t"]]
    for t, d in prepped.items():
        sub = key.loc[t]
        idx = pd.Index(d["date"].values)
        for c in ("mom_rank", "vol_t", "beta_t"):
            d[c] = sub[c].reindex(idx).values
    return prepped


HALF_A = None


def half_split(panel, seed=7):
    """Same fixed name split the search used: half A was searched, half B never was."""
    names = sorted(panel)
    rng = np.random.default_rng(seed)
    a = set(rng.permutation(names)[: len(names) // 2])
    return a


def slice_panel(panel, lo, hi, names=None, group="mid_small"):
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


def signal_mask(d, top_pct=TOP_PCT):
    return (d["mom_rank"] >= top_pct).fillna(False).values & d["liq"].values


# Exit specifications. 'bracket' is the engine default (2 ATR stop / 2 ATR target). 'time' holds
# to the horizon - stop/target multiples set far enough away that they never trigger, which is the
# specification the drift hypothesis actually implies. Both are applied to the CONTROL identically.
EXITS = {"bracket": dict(), "time": dict(stop_atr_mult=99.0, target_atr_mult=99.0)}


def run_set(sub, top_pct=TOP_PCT, horizon=HORIZON, next_open=False, matched=False, exit_spec="bracket"):
    strat, stocks = [], []
    for t, d in sub.items():
        sig = signal_mask(d, top_pct)
        if next_open:
            sig = np.roll(sig, 1)
            sig[0] = False
        strat += simulate_trades(d, sig, horizon_days=horizon, charge_costs=True, **EXITS[exit_spec])
        stocks.append(d)

    if matched:
        sig_cells = pd.concat([d.loc[signal_mask(d, top_pct), ["date", "vol_t", "beta_t"]]
                               for d in stocks], ignore_index=True).dropna().drop_duplicates()
        sig_cells["_cell_ok"] = True
        stocks = [d.merge(sig_cells, on=["date", "vol_t", "beta_t"], how="left")
                   .assign(_cell_ok=lambda x: x["_cell_ok"].fillna(False)) for d in stocks]

    def control_factory(seed):
        rng = np.random.default_rng(1000 + seed)
        ctrl = []
        for d in stocks:
            liq = d["liq"].values
            if matched:
                ok = d["_cell_ok"].values
                rnd = liq & ok & ~signal_mask(d, top_pct) & (rng.random(len(d)) < 0.5)
            else:
                rnd = liq & (rng.random(len(d)) < 0.10)
            ctrl += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True, **EXITS[exit_spec])
        return ctrl

    return strat, control_factory


def summarize(label, strat, cf, seeds=20, quiet=False):
    if len(strat) < 20:
        print(f"{label:46s} n={len(strat)} - too few trades")
        return None
    st = stable_day_clustered_z(strat, cf, n_seeds=seeds)
    ctrl = cf(0)
    dc = day_clustered_edge(strat, ctrl)
    nets = np.array([t["net_pct"] for t in strat])
    cnets = np.array([t["net_pct"] for t in ctrl])
    if not quiet:
        print(f"{label:46s} n={len(strat):5d} days={dc['n_paired_days']:4d} "
              f"mean_z={st['mean_z']:+5.2f} pass={st['pass_rate']*100:3.0f}% "
              f"[{st['min_z']:+.2f},{st['max_z']:+.2f}] day_edge={dc['day_edge']:+.3f}% "
              f"net={nets.mean():+.3f}% (ctrl {cnets.mean():+.3f}%) win={100*(nets>0).mean():.0f}%")
    return {"stable": st, "dc": dc, "net": float(nets.mean()), "n": len(strat)}


def main():
    panel = prepare(load())
    A = half_split(panel)
    B = set(panel) - A
    LO = pd.Timestamp("2000-01-01")
    FWD_END = pd.Timestamp("2026-08-21")

    ms_all = slice_panel(panel, LO, IS_END)
    print(f"universe: {len(panel)} names, {len(ms_all)} liquid mid/small with in-sample history\n")

    print("== 1. search half (A), in-sample - this is the number NOT to trust ==")
    s, cf = run_set(slice_panel(panel, LO, IS_END, names=A))
    summarize("half A, in-sample, h=8", s, cf)

    print("\n== 2. KILL #1: hold-out half of NAMES (B), in-sample ==")
    s, cf = run_set(slice_panel(panel, LO, IS_END, names=B))
    summarize("half B (never searched), in-sample, h=8", s, cf)

    print("\n== 3. KILL #2: held-out FORWARD window, both halves ==")
    for h in (6, 8, 10):
        s, cf = run_set(slice_panel(panel, FWD_START, FWD_END), horizon=h)
        summarize(f"forward {FWD_START.date()}+, h={h}", s, cf)
    print("   forward, hold-out names only:")
    s, cf = run_set(slice_panel(panel, FWD_START, FWD_END, names=B))
    summarize("forward, half B only, h=8", s, cf)

    print("\n== 4. pooled full sample (all names, all dates) ==")
    for h in (6, 8, 10):
        s, cf = run_set(slice_panel(panel, LO, FWD_END), horizon=h)
        summarize(f"full sample h={h}", s, cf)

    print("\n== 5. KILL #4: volatility/beta-matched control (full sample, h=8) ==")
    s, cf = run_set(slice_panel(panel, LO, FWD_END), matched=True)
    summarize("MATCHED control", s, cf)

    print("\n== 6. KILL #5: decile gradient (full sample, h=8) ==")
    for lo_pct, hi_pct, name in ((0.90, 1.01, "D10"), (0.80, 0.90, "D9"), (0.70, 0.80, "D8"),
                                 (0.50, 0.60, "D6"), (0.0, 0.10, "D1")):
        sub = slice_panel(panel, LO, FWD_END)
        strat, stocks = [], []
        for t, d in sub.items():
            m = ((d["mom_rank"] >= lo_pct) & (d["mom_rank"] < hi_pct)).fillna(False).values & d["liq"].values
            strat += simulate_trades(d, m, horizon_days=HORIZON, charge_costs=True)
            stocks.append(d)

        def cf2(seed, stocks=stocks):
            rng = np.random.default_rng(1000 + seed)
            ctrl = []
            for d in stocks:
                ctrl += simulate_trades(d, d["liq"].values & (rng.random(len(d)) < 0.10),
                                        horizon_days=HORIZON, charge_costs=True)
            return ctrl
        summarize(f"{name}", strat, cf2, seeds=10)

    print("\n== 7. KILL #6: next-session entry (execution fragility, full sample) ==")
    s, cf = run_set(slice_panel(panel, LO, FWD_END), next_open=True)
    summarize("next-session entry, h=8", s, cf)

    print("\n== 8. KILL #7: walk-forward (full sample, h=8) ==")
    dates = sorted({d for dd in slice_panel(panel, LO, FWD_END).values() for d in dd["date"]})
    for k, (tr, te) in enumerate(walk_forward_splits(len(dates), n_splits=4, horizon_days=HORIZON)):
        f_lo, f_hi = dates[te[0]], dates[te[-1]]
        sf, cff = run_set(slice_panel(panel, f_lo, f_hi))
        summarize(f"fold {k+1} {f_lo.date()}..{f_hi.date()}", sf, cff, seeds=10)

    print("\n== 9. large-cap placebo (ranked within Nifty 50, full sample) ==")
    lg = {t: d for t, d in panel.items() if t in NIFTY_50}
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
    s, cf = run_set(lg2)
    summarize("large caps, h=8", s, cf)


if __name__ == "__main__":
    main()
