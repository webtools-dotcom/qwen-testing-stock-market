"""Strategy 022 - Risk-Adjusted 12-Month Momentum Swing in Mid/Small Caps.

Buys liquid NSE mid/small caps in the top cross-sectional decile of (252-session return / 60-day
volatility), holds 8 sessions, no other filter. 10-year panel (2016-2026).

Rules and the nine kill criteria are pre-registered in the .md. The decisive ones are the hold-out
half of NAMES (kill 1), the 2016-2020 regime block (kill 3) and the vol/beta-matched control
(kill 5).

Run:  python strategies/022_risk_adjusted_12_month_momentum_swing_in_mid_small_caps.py
"""

import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z, walk_forward_splits,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_TURNOVER = 25e7
HORIZON = 8
TOP_PCT = 0.90
P1_END = pd.Timestamp("2020-12-31")
P2_END = pd.Timestamp("2023-12-31")
LO, HI = pd.Timestamp("2000-01-01"), pd.Timestamp("2026-08-21")

# Declared before the run: hold to the horizon, no ATR bracket. The control gets the same rule.
EXIT = dict(stop_atr_mult=99.0, target_atr_mult=99.0)
BRACKET = dict()

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}


def load(cache="broad_nse_10y"):
    obj = pickle.load(open(os.path.join(BASE, "cache", cache + ".pkl"), "rb"))
    return obj["data"] if isinstance(obj, dict) and "data" in obj else obj


def prepare(panel, rank_group="mid_small"):
    """Add the score, its daily cross-sectional rank, and vol/beta tercile labels for the matched
    control. Every input is known at that bar's close; nothing is forward-filled."""
    rets = {}
    for t, df in panel.items():
        s = pd.Series(df["close"].pct_change().values, index=df["date"].values)
        rets[t] = s[~s.index.duplicated()]
    mkt = pd.DataFrame(rets).mean(axis=1).sort_index()

    prepped = {}
    for t, df in panel.items():
        d = df.copy().reset_index(drop=True)
        r = d["close"].pct_change()
        d["ticker"] = t
        d["mid_small"] = t not in NIFTY_50
        d["vol60"] = r.rolling(60).std() * 100
        d["score"] = d["change_252d"] / d["vol60"].replace(0, np.nan)
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        m1 = mkt.reindex(pd.Index(d["date"].values)).values * 100
        d["beta"] = (pd.Series(r.values * 100).rolling(120).cov(pd.Series(m1))
                     / pd.Series(m1).rolling(120).var())
        prepped[t] = d

    flat = pd.concat([d[["date", "ticker", "score", "atr_pct", "beta", "liq", "mid_small"]]
                      for d in prepped.values()], ignore_index=True)
    mask = (flat["liq"] & flat["mid_small"]) if rank_group == "mid_small" else flat["liq"]
    elig = flat[mask]
    flat.loc[elig.index, "rank"] = elig.groupby("date")["score"].rank(pct=True)
    for c, n in (("atr_pct", "vol_t"), ("beta", "beta_t")):
        flat.loc[elig.index, n] = elig.groupby("date")[c].transform(
            lambda s: pd.qcut(s.rank(method="first"), 3, labels=False) if s.notna().sum() >= 3 else np.nan)
    key = flat.set_index(["ticker", "date"])[["rank", "vol_t", "beta_t"]]
    for t, d in prepped.items():
        sub = key.loc[t]
        idx = pd.Index(d["date"].values)
        for c in ("rank", "vol_t", "beta_t"):
            d[c] = sub[c].reindex(idx).values
    return prepped


def half_split(panel, seed=23):
    """The same fixed name split the 10-year search used: A was searched, B never was."""
    names = sorted(panel)
    rng = np.random.default_rng(seed)
    return set(rng.permutation(names)[: len(names) // 2])


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


def signal_mask(d, top_pct=TOP_PCT, lo_pct=None):
    r = d["rank"]
    m = (r >= top_pct) if lo_pct is None else ((r >= lo_pct) & (r < top_pct))
    return m.fillna(False).values & d["liq"].values


def run_set(sub, top_pct=TOP_PCT, lo_pct=None, horizon=HORIZON, next_open=False,
            matched=False, exit_kw=None):
    exit_kw = EXIT if exit_kw is None else exit_kw
    strat, stocks = [], []
    for t, d in sub.items():
        sig = signal_mask(d, top_pct, lo_pct)
        if next_open:
            sig = np.roll(sig, 1)
            sig[0] = False
        strat += simulate_trades(d, sig, horizon_days=horizon, charge_costs=True, **exit_kw)
        stocks.append(d)

    if matched:
        cells = pd.concat([d.loc[signal_mask(d, top_pct, lo_pct), ["date", "vol_t", "beta_t"]]
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
                rnd = liq & d["_ok"].values & ~signal_mask(d, top_pct, lo_pct) & (rng.random(len(d)) < 0.5)
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
    panel = prepare(load())
    A = half_split(panel)
    B = set(panel) - A
    print(f"universe {len(panel)} names; half A {len(A)}, half B {len(B)}\n", flush=True)

    print("== 1. pooled, both halves, full 10y (KILL #2) ==", flush=True)
    for h in (6, 8, 10):
        s, cf = run_set(slice_panel(panel), horizon=h)
        summarize(f"pooled h={h}", s, cf)

    print("\n== 2. KILL #1: hold-out half of NAMES (B, never searched) ==", flush=True)
    s, cf = run_set(slice_panel(panel, names=B))
    summarize("half B, h=8", s, cf)
    s, cf = run_set(slice_panel(panel, names=A))
    summarize("half A (searched), h=8", s, cf)

    print("\n== 3. KILL #3/#4: regime blocks ==", flush=True)
    for lbl, lo, hi in (("P1 2016-2020", LO, P1_END),
                        ("P2 2021-2023", P1_END, P2_END),
                        ("P3 2024-2026", P2_END, HI)):
        s, cf = run_set(slice_panel(panel, lo, hi))
        summarize(f"{lbl}", s, cf)
    print("   P1 on the hold-out half only (hardest cell):", flush=True)
    s, cf = run_set(slice_panel(panel, LO, P1_END, names=B))
    summarize("P1 x half B", s, cf)

    print("\n== 4. KILL #5: vol/beta-matched control (full 10y) ==", flush=True)
    s, cf = run_set(slice_panel(panel), matched=True)
    summarize("MATCHED control h=8", s, cf)

    print("\n== 5. KILL #6: next-session entry ==", flush=True)
    s, cf = run_set(slice_panel(panel), next_open=True)
    summarize("next-session entry h=8", s, cf)

    print("\n== 6. KILL #7: decile gradient ==", flush=True)
    for lo_p, hi_p, name in ((0.90, None, "D10"), (0.80, 0.90, "D9"), (0.70, 0.80, "D8"),
                             (0.45, 0.55, "D5"), (0.0, 0.10, "D1")):
        if hi_p is None:
            s, cf = run_set(slice_panel(panel))
        else:
            s, cf = run_set(slice_panel(panel), top_pct=hi_p, lo_pct=lo_p)
        summarize(name, s, cf, seeds=10)

    print("\n== 7. engine-default ATR bracket (reported, not the spec) ==", flush=True)
    s, cf = run_set(slice_panel(panel), exit_kw=BRACKET)
    summarize("bracket exit h=8", s, cf, seeds=10)

    print("\n== 8. KILL #8: walk-forward, 5 folds ==", flush=True)
    dates = sorted({d for dd in slice_panel(panel).values() for d in dd["date"]})
    for k, (tr, te) in enumerate(walk_forward_splits(len(dates), n_splits=5, horizon_days=HORIZON)):
        if len(te) == 0:
            continue
        f_lo, f_hi = dates[te[0]], dates[te[-1]]
        s, cf = run_set(slice_panel(panel, f_lo, f_hi))
        summarize(f"fold {k+1} {f_lo.date()}..{f_hi.date()}", s, cf, seeds=10)

    print("\n== 9. KILL #9: large caps (ranked within Nifty 50) ==", flush=True)
    lp = prepare(load(), rank_group="all")
    lg = slice_panel(lp, group="large")
    s, cf = run_set(lg)
    summarize("large caps h=8", s, cf, seeds=10)


if __name__ == "__main__":
    main()
