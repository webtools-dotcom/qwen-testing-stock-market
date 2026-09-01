"""Strategy 026 — Quarterly (63-Session) Risk-Adjusted Momentum in Mid/Small Caps.

Buys liquid NSE mid/small caps in the top cross-sectional decile of 63-session (quarterly)
return divided by 60-session daily return volatility:
    score = (close_t / close_{t-63} - 1.0) / vol60
Holds for 21 sessions (~1 calendar month), no ATR bracket. 10-year panel (2016-2026).

Run:  python strategies/026_quarterly_risk_adjusted_momentum_in_mid_small_caps.py
"""

import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch"))

import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z,
    walk_forward_splits, round_trip_cost_pct, sharpe, deflated_sharpe
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_TURNOVER = 25e7
HOLD = 21                       # 21 sessions = 1 calendar month (canonical monthly rebalance)
TOP_PCT = 0.90
P1_END = pd.Timestamp("2020-12-31")
P2_END = pd.Timestamp("2023-12-31")
LO, HI = pd.Timestamp("2000-01-01"), pd.Timestamp("2026-08-21")

EXIT = dict(stop_atr_mult=99.0, target_atr_mult=99.0)

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}


def load_panel():
    obj = pickle.load(open(os.path.join(BASE, "cache", "master_10y.pkl"), "rb"))
    return obj["data"] if isinstance(obj, dict) and "data" in obj else obj


def prepare(panel, rank_group="mid_small"):
    """Compute 63-session risk-adjusted momentum score and daily cross-sectional decile ranks."""
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
        # 63-session (quarterly) risk-adjusted momentum
        ret_63 = d["close"] / d["close"].shift(63) - 1.0
        d["score"] = ret_63 / (d["vol60"] + 1e-4)
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


def run_set(sub, top_pct=TOP_PCT, lo_pct=None, horizon=HOLD, next_open=False, matched=False):
    strat, stocks = [], []
    for t, d in sub.items():
        sig = signal_mask(d, top_pct, lo_pct)
        if next_open:
            sig = np.roll(sig, 1)
            sig[0] = False
        strat += simulate_trades(d, sig, horizon_days=horizon, charge_costs=True, **EXIT)
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
            ctrl += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True, **EXIT)
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


def run_portfolio_sim(prepped, hold=HOLD, k=20, cost_mult=1.0):
    keep = ["date", "ticker", "close", "rank", "liq", "turnover_60d"]
    df = pd.concat([d[keep] for d in prepped.values() if d["ticker"].iloc[0] not in NIFTY_50], ignore_index=True)
    df = df[df["liq"]].sort_values(["date", "ticker"])
    
    dates = np.sort(df["date"].unique())
    px = df.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
    rk = df.pivot_table(index="date", columns="ticker", values="rank", aggfunc="last")
    to = df.pivot_table(index="date", columns="ticker", values="turnover_60d", aggfunc="last")
    
    dates = px.index.values
    rk = rk.reindex(px.index)
    to = to.reindex(px.index)
    ret = px.pct_change()
    
    # 1. Benchmark
    bench_eq = (1 + ret.mean(axis=1).fillna(0)).cumprod()
    
    # 2. Strategy Portfolio
    equity = 1.0
    curve = {}
    open_pos = {} # ticker -> (days_left, weight_val)
    for i, dt in enumerate(dates):
        if open_pos:
            r = ret.loc[dt]
            for t in list(open_pos):
                d_left, val = open_pos[t]
                rr = r.get(t, np.nan)
                val = val * (1 + (0.0 if not np.isfinite(rr) else rr))
                d_left -= 1
                if d_left <= 0:
                    equity += val
                    del open_pos[t]
                else:
                    open_pos[t] = (d_left, val)
        slots = k - len(open_pos)
        if slots > 0 and i < len(dates) - hold - 1:
            row = rk.loc[dt]
            cand = row[(row >= TOP_PCT)].sort_values(ascending=False).index.tolist()
            cand = [t for t in cand if t not in open_pos and np.isfinite(px.loc[dt].get(t, np.nan))]
            take = cand[:slots]
            if take:
                per = equity / max(1, slots) if equity > 0 else 0.0
                per = min(per, equity / max(1, len(take))) if len(take) else 0.0
                for t in take:
                    if equity <= 0:
                        break
                    cost = round_trip_cost_pct(to.loc[dt].get(t, np.nan)) * cost_mult / 100.0
                    stake = min(per, equity)
                    equity -= stake
                    open_pos[t] = (hold, stake * (1 - cost))
        curve[dt] = equity + sum(v for _, v in open_pos.values())
        
    strat_eq = pd.Series(curve)
    
    # 3. Random portfolio control
    rng = np.random.default_rng(42)
    equity = 1.0
    curve_r = {}
    open_pos_r = {}
    for i, dt in enumerate(dates):
        if open_pos_r:
            r = ret.loc[dt]
            for t in list(open_pos_r):
                d_left, val = open_pos_r[t]
                rr = r.get(t, np.nan)
                val = val * (1 + (0.0 if not np.isfinite(rr) else rr))
                d_left -= 1
                if d_left <= 0:
                    equity += val
                    del open_pos_r[t]
                else:
                    open_pos_r[t] = (d_left, val)
        slots = k - len(open_pos_r)
        if slots > 0 and i < len(dates) - hold - 1:
            row = rk.loc[dt]
            cand = row[row.notna()].index.tolist()
            rng.shuffle(cand)
            cand = [t for t in cand if t not in open_pos_r and np.isfinite(px.loc[dt].get(t, np.nan))]
            take = cand[:slots]
            if take:
                per = equity / max(1, slots) if equity > 0 else 0.0
                per = min(per, equity / max(1, len(take))) if len(take) else 0.0
                for t in take:
                    if equity <= 0:
                        break
                    cost = round_trip_cost_pct(to.loc[dt].get(t, np.nan)) * cost_mult / 100.0
                    stake = min(per, equity)
                    equity -= stake
                    open_pos_r[t] = (hold, stake * (1 - cost))
        curve_r[dt] = equity + sum(v for _, v in open_pos_r.values())
        
    rnd_eq = pd.Series(curve_r)
    return strat_eq, bench_eq, rnd_eq


def calc_stats(eq, label):
    r = eq.pct_change().dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1).min()
    sh = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0
    print(f"  {label:<32s} CAGR {cagr*100:+6.2f}% | maxDD {dd*100:6.1f}% | Sharpe {sh:5.2f} | final {eq.iloc[-1]:.2f}x")
    return {"cagr": cagr, "dd": dd, "sharpe": sh}


def main():
    panel = prepare(load_panel())
    names = sorted(panel)
    rng = np.random.default_rng(23)
    A = set(rng.permutation(names)[: len(names) // 2])
    B = set(names) - A
    full = slice_panel(panel)
    print(f"Universe {len(panel)} total names, {len(full)} liquid mid/small, hold={HOLD}\n", flush=True)

    print("== KILL 1: Pooled and Hold-out Half B of Names ==", flush=True)
    strat, cf = run_set(full, horizon=HOLD)
    pooled = summarize(f"Pooled h={HOLD}", strat, cf)
    s_b, c_b = run_set(slice_panel(panel, names=B), horizon=HOLD)
    summarize("Hold-out Half B (Unseen)", s_b, c_b)

    print("\n== KILL 2: +/-1 Step in Holding Period ==", flush=True)
    for h in (15, 21, 30, 42):
        s, c = run_set(full, horizon=h)
        summarize(f"Hold = {h} sessions", s, c, seeds=10)

    print("\n== KILL 3: Regime Blocks (Walk-Forward Chronological Partitions) ==", flush=True)
    for lbl, lo, hi in (("P1 2016-2020", LO, P1_END), ("P2 2021-2023", P1_END, P2_END),
                        ("P3 2024-2026", P2_END, HI)):
        s, c = run_set(slice_panel(panel, lo, hi), horizon=HOLD)
        summarize(lbl, s, c)

    print("\n== KILL 4: Survivorship Check (Pre-2017 Listings) ==", flush=True)
    first = {t: d["date"].min() for t, d in panel.items()}
    old = {t for t, dt in first.items() if dt <= pd.Timestamp("2017-01-01")}
    new = set(panel) - old
    print(f"   {len(old)} pre-2017 names, {len(new)} later listings", flush=True)
    s_old, c_old = run_set(slice_panel(panel, names=old), horizon=HOLD)
    r_old = summarize("Pre-2017 names only", s_old, c_old)
    s_new, c_new = run_set(slice_panel(panel, names=new), horizon=HOLD)
    summarize("Later listings only", s_new, c_new)
    if r_old and pooled:
        keep = r_old["dc"]["day_edge"] / pooled["dc"]["day_edge"]
        print(f"   Pre-2017 subgroup retains {100*keep:.0f}% of pooled day_edge (kill threshold >= 60%)", flush=True)

    print("\n== KILL 5: Decile Ladder Gradient ==", flush=True)
    for lo_p, hi_p, name in ((0.90, None, "D10 (Top Decile)"), (0.80, 0.90, "D09"), (0.70, 0.80, "D08"),
                             (0.45, 0.55, "D05 (Median)"), (0.0, 0.10, "D01 (Bottom Decile)")):
        if hi_p is None:
            s, c = run_set(full, horizon=HOLD)
        else:
            s, c = run_set(full, top_pct=hi_p, lo_pct=lo_p, horizon=HOLD)
        summarize(name, s, c, seeds=10)

    print("\n== KILL 6: Controls and Execution Fragility ==", flush=True)
    s_mat, c_mat = run_set(full, horizon=HOLD, matched=True)
    summarize("Vol/Beta-MATCHED Control", s_mat, c_mat)
    s_nxt, c_nxt = run_set(full, horizon=HOLD, next_open=True)
    summarize("Next-Session Entry Fill", s_nxt, c_nxt)

    print("\n== KILL 7: Walk-Forward 5 Folds Stability ==", flush=True)
    dates = sorted({d for dd in full.values() for d in dd["date"]})
    for k, (tr, te) in enumerate(walk_forward_splits(len(dates), n_splits=5, horizon_days=HOLD)):
        if len(te) == 0:
            continue
        f_lo, f_hi = dates[te[0]], dates[te[-1]]
        s, c = run_set(slice_panel(panel, f_lo, f_hi), horizon=HOLD)
        summarize(f"Fold {k+1} ({f_lo.date()}..{f_hi.date()})", s, c, seeds=10)

    print("\n== KILL 8: Large-Caps Check ==", flush=True)
    lp = prepare(load_panel(), rank_group="all")
    lg = slice_panel(lp, group="large")
    s_lg, c_lg = run_set(lg, horizon=HOLD)
    summarize("Large Caps (Nifty 50)", s_lg, c_lg, seeds=10)

    print("\n== KILL 9: THE PORTFOLIO TOOL TEST (20 Slots, Cash-Constrained, Costs Charged) ==", flush=True)
    s_eq, b_eq, r_eq = run_portfolio_sim(panel, hold=HOLD, k=20)
    calc_stats(s_eq, "Strategy (63d Mom, h=21)")
    calc_stats(b_eq, "Buy & Hold Benchmark Universe")
    calc_stats(r_eq, "Random Selection Control")
    
    print("\n   Per Calendar Year (Strategy vs Buy & Hold vs Random):", flush=True)
    for y in sorted(set(s_eq.index.year)):
        a = s_eq[s_eq.index.year == y]; b = b_eq[b_eq.index.year == y]; c = r_eq[r_eq.index.year == y]
        if len(a) < 20:
            continue
        ra = a.iloc[-1] / a.iloc[0] - 1
        rb = b.iloc[-1] / b.iloc[0] - 1
        rc = c.iloc[-1] / c.iloc[0] - 1
        print(f"     {y}: Strategy {ra*100:+7.2f}% | Buy-Hold {rb*100:+7.2f}% | Random {rc*100:+7.2f}% | Excess {100*(ra-rb):+7.2f}%", flush=True)

    print("\n   Cost Sensitivity (Round-Trip Friction):", flush=True)
    for cm in (1.0, 1.5, 2.0):
        s_cm, _, _ = run_portfolio_sim(panel, hold=HOLD, k=20, cost_mult=cm)
        calc_stats(s_cm, f"Strategy Costs x{cm:.1f}")


if __name__ == "__main__":
    main()
