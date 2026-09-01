"""Strategy 027 — 52-Week High Trend Consistency Composite in Mid/Small Caps.

Buys liquid NSE mid/small caps ranked in the top decile of a dual composite:
1. George & Hwang 52-week high nearness (Close / 252-day High)
2. 252-day Trend Consistency / Information Ratio (mean daily return / daily return std * sqrt(252))

Holding horizon: 42 sessions (~2.0 calendar months), time exit, no ATR bracket.
Tested on a 10-year master panel (2016-2026).

Run:  python strategies/027_52_week_high_trend_consistency_composite_in_mid_small_caps.py
"""

import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z, 
    edge_vs_control, sharpe, deflated_sharpe, effective_trials, 
    round_trip_cost_pct, report
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_TURNOVER = 25e7
HORIZON = 42 # 2 months
TOP_PCT = 0.90
P1_END = pd.Timestamp("2020-12-31")
P2_END = pd.Timestamp("2023-12-31")
LO, HI = pd.Timestamp("2000-01-01"), pd.Timestamp("2026-08-21")

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}

def load(cache="master_10y"):
    path = os.path.join(BASE, "cache", cache + ".pkl")
    if not os.path.exists(path):
        path = os.path.join(BASE, "cache", "broad_nse_10y.pkl")
    obj = pickle.load(open(path, "rb"))
    return obj["data"] if isinstance(obj, dict) and "data" in obj else obj

def prepare(panel, rank_group="mid_small"):
    """Compute 52w high nearness, 252d trend t-stat, composite rank, and vol/beta terciles."""
    rets = {}
    for t, df in panel.items():
        s = pd.Series(df["close"].pct_change().values, index=df["date"].values)
        rets[t] = s[~s.index.duplicated()]
    mkt = pd.DataFrame(rets).mean(axis=1).sort_index()

    prepped = {}
    for t, df in panel.items():
        d = df.copy().reset_index(drop=True)
        d["ticker"] = t
        d["mid_small"] = t not in NIFTY_50
        r = d["close"].pct_change()
        d["ret_1"] = r
        d["vol60"] = r.rolling(60).std() * 100
        d["vol252"] = r.rolling(252).std() * 100
        
        # 1. 252-day t-statistic of daily returns (Sharpe / consistency of 12m trend)
        mu252 = r.rolling(252).mean()
        sd252 = r.rolling(252).std()
        d["t_stat_252"] = (mu252 / sd252.replace(0, np.nan)) * np.sqrt(252)
        
        # 2. 52-week High Nearness
        high_252 = d["high"].rolling(252).max()
        d["near_52w_high"] = d["close"] / high_252

        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        m1 = mkt.reindex(pd.Index(d["date"].values)).values * 100
        d["beta"] = (pd.Series(r.values * 100).rolling(120).cov(pd.Series(m1))
                     / pd.Series(m1).rolling(120).var())
        prepped[t] = d

    flat = pd.concat([d[["date", "ticker", "liq", "mid_small", "atr_pct", "beta", "t_stat_252", "near_52w_high"]]
                      for d in prepped.values()], ignore_index=True)
    mask = (flat["liq"] & flat["mid_small"]) if rank_group == "mid_small" else flat["liq"]
    elig = flat[mask]

    for col in ["t_stat_252", "near_52w_high"]:
        flat.loc[elig.index, f"rank_{col}"] = elig.groupby("date")[col].rank(pct=True)

    flat.loc[elig.index, "rank_comp"] = (
        flat.loc[elig.index, "rank_t_stat_252"] + flat.loc[elig.index, "rank_near_52w_high"]
    ) / 2.0
    flat.loc[elig.index, "rank"] = flat.loc[elig.index].groupby("date")["rank_comp"].rank(pct=True)

    for c, n in (("atr_pct", "vol_t"), ("beta", "beta_t")):
        flat.loc[elig.index, n] = elig.groupby("date")[c].transform(
            lambda s: pd.qcut(s.rank(method="first"), 3, labels=False) if s.notna().sum() >= 3 else np.nan)

    key = flat.set_index(["ticker", "date"])
    for t, d in prepped.items():
        sub = key.loc[t]
        idx = pd.Index(d["date"].values)
        for c in ["rank", "vol_t", "beta_t"]:
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

def run_trades(sub, top_pct=TOP_PCT, lo_pct=None, horizon=HORIZON, next_open=False, matched=False):
    strat = []
    stocks = []
    
    for t, d in sub.items():
        r = d["rank"]
        m = (r >= top_pct) if lo_pct is None else ((r >= lo_pct) & (r < top_pct))
        sig = m.fillna(False).values & d["liq"].values
        if len(d) < 300:
            continue
            
        tr = simulate_trades(d, sig, horizon_days=horizon, charge_costs=True,
                             stop_atr_mult=99.0, target_atr_mult=99.0)
        for item in tr:
            item["ticker"] = t
            if next_open:
                idx = item["entry_idx"]
                if idx + 1 < len(d):
                    nxt_open = d["open"].iat[idx + 1]
                    item["entry_date"] = d["date"].iat[idx + 1]
                    exit_px = d["close"].iat[min(idx + 1 + horizon, len(d) - 1)]
                    gross = (exit_px - nxt_open) / nxt_open * 100
                    item["gross_pct"] = gross
                    item["net_pct"] = gross - item["cost_pct"]
        strat.extend(tr)
        stocks.append((t, d))
        
    def control_factory(seed):
        rng = np.random.default_rng(seed)
        ctrl = []
        if matched:
            all_rows = []
            for t, d in stocks:
                df_c = d[["date", "vol_t", "beta_t", "liq"]].copy()
                df_c["ticker"] = t
                df_c["row_idx"] = np.arange(len(d))
                all_rows.append(df_c)
            flat_c = pd.concat(all_rows, ignore_index=True)
            flat_c = flat_c[flat_c["liq"] & flat_c["vol_t"].notna() & flat_c["beta_t"].notna()]
            pool_map = flat_c.groupby(["date", "vol_t", "beta_t"])[["ticker", "row_idx"]].apply(
                lambda g: g.values.tolist()
            ).to_dict()
            
            for st in strat:
                t = st["ticker"]
                d = next(df for (tk, df) in stocks if tk == t)
                dt = st["entry_date"]
                row = d[d["date"] == dt]
                if len(row) == 0:
                    continue
                vt, bt = row["vol_t"].iat[0], row["beta_t"].iat[0]
                cand = pool_map.get((dt, vt, bt), [])
                if cand:
                    pick_t, pick_idx = cand[rng.integers(0, len(cand))]
                    pick_d = next(df for (tk, df) in stocks if tk == pick_t)
                    if pick_idx + horizon < len(pick_d):
                        en_px = pick_d["close"].iat[pick_idx]
                        ex_px = pick_d["close"].iat[pick_idx + horizon]
                        cost = round_trip_cost_pct(pick_d["turnover_60d"].iat[pick_idx])
                        gross = (ex_px - en_px) / en_px * 100
                        ctrl.append({
                            "entry_date": dt,
                            "gross_pct": gross,
                            "net_pct": gross - cost,
                            "cost_pct": cost,
                            "held": horizon,
                            "ticker": pick_t
                        })
        else:
            for t, d in stocks:
                liq = d["liq"].values
                rnd = (rng.random(len(d)) < 0.10) & liq
                ct = simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True,
                                     stop_atr_mult=99.0, target_atr_mult=99.0)
                for item in ct:
                    item["ticker"] = t
                ctrl.extend(ct)
        return ctrl

    return strat, control_factory

def summarize(label, strat, cf, n_seeds=20):
    if not strat:
        print(f"{label}: NO TRADES", flush=True)
        return None
    c0 = cf(42)
    ev = edge_vs_control([t["net_pct"] for t in strat], [t["net_pct"] for t in c0])
    dc = day_clustered_edge(strat, c0)
    sc = stable_day_clustered_z(strat, cf, n_seeds=n_seeds)
    print(f"{label:<36} | Tr: {len(strat):4d} | Day: {dc['n_paired_days']:4d} | "
          f"Stable Mean z: {sc['mean_z']:+5.2f} (pass {sc['pass_rate']*100:3.0f}%, min {sc['min_z']:+5.2f}, max {sc['max_z']:+5.2f}) | "
          f"DayEdge: {dc['day_edge']:+6.3f}% | Net/tr: {ev['strategy_avg']:+6.3f}% (ctrl {ev['control_avg']:+6.3f}%)",
          flush=True)
    return {"ev": ev, "dc": dc, "sc": sc}

def run_portfolio_sim(panel, hold=HORIZON, k=20, cost_mult=1.0, mode="strategy", seed=0):
    keep = ["date", "ticker", "close", "rank", "liq", "turnover_60d", "mid_small"]
    dfs = []
    for t, d in panel.items():
        if d["mid_small"].iloc[0]:
            dfs.append(d[keep])
    df = pd.concat(dfs, ignore_index=True).sort_values(["date", "ticker"])
    df = df[df["liq"]].copy()

    px = df.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
    rk = df.pivot_table(index="date", columns="ticker", values="rank", aggfunc="last")
    to = df.pivot_table(index="date", columns="ticker", values="turnover_60d", aggfunc="last")
    
    dates = px.index.values
    rk = rk.reindex(px.index)
    to = to.reindex(px.index)
    ret = px.pct_change()
    rng = np.random.default_rng(seed)

    if mode == "benchmark":
        eq = (1 + ret.mean(axis=1).fillna(0)).cumprod()
        return eq

    equity = 1.0
    curve = {}
    open_pos = {}
    
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
            if mode == "strategy":
                cand = row[row >= 0.90].sort_values(ascending=False).index.tolist()
            else:
                cand = row[row.notna()].index.tolist()
                rng.shuffle(cand)
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
    return pd.Series(curve)

def calc_pf_stats(eq):
    r = eq.pct_change().dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1).min()
    sh = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0
    return {"cagr": cagr, "dd": dd, "sharpe": sh}

def yearly_returns(eq):
    df = pd.DataFrame({"eq": eq})
    df["year"] = pd.to_datetime(df.index).year
    first = df.groupby("year")["eq"].first()
    last = df.groupby("year")["eq"].last()
    return (last / first - 1) * 100

def main():
    raw_panel = load("master_10y")
    panel = prepare(raw_panel)
    names = sorted(panel)
    rng = np.random.default_rng(23)
    half_A = set(rng.permutation(names)[: len(names) // 2])
    half_B = set(names) - half_A
    full = slice_panel(panel)
    
    print(f"Loaded {len(panel)} names, {len(full)} liquid mid/small caps. Pre-registered Horizon = {HORIZON} sessions (~2.0 months).\n", flush=True)
    
    print("=== 1. HEADLINE SIGNIFICANCE & HOLDOUT HALF B ===", flush=True)
    strat, cf = run_trades(full, horizon=HORIZON)
    pooled = summarize("Pooled Mid/Small (Baseline)", strat, cf)
    
    s_b, cf_b = run_trades(slice_panel(panel, names=half_B), horizon=HORIZON)
    summarize("Holdout Half B of Names", s_b, cf_b)
    
    print("\n=== 2. DECILE LADDER GRADIENT ===", flush=True)
    for dec in range(10, 0, -1):
        hi_p = dec / 10.0
        lo_p = (dec - 1) / 10.0
        s_d, cf_d = run_trades(full, top_pct=hi_p, lo_pct=lo_p, horizon=HORIZON)
        summarize(f"Decile D{dec:02d} ({lo_p*100:.0f}%-{hi_p*100:.0f}%)", s_d, cf_d, n_seeds=10)

    print("\n=== 3. HOLDING PERIOD SENSITIVITY (+/- 1 STEP) ===", flush=True)
    for h in [21, 30, 42, 50, 60]:
        s_h, cf_h = run_trades(full, horizon=h)
        summarize(f"Horizon = {h:2d} sessions (~{h/21:.1f}m)", s_h, cf_h, n_seeds=10)

    print("\n=== 4. REGIME BLOCKS ===", flush=True)
    for lbl, lo, hi in [("P1 (2016-2020)", LO, P1_END), ("P2 (2021-2023)", P1_END, P2_END), ("P3 (2024-2026)", P2_END, HI)]:
        s_reg, cf_reg = run_trades(slice_panel(panel, lo, hi), horizon=HORIZON)
        summarize(lbl, s_reg, cf_reg)

    print("\n=== 5. SURVIVORSHIP CHECK (PRE-2017 LISTINGS ONLY) ===", flush=True)
    first = {t: d["date"].min() for t, d in panel.items()}
    old = {t for t, dt in first.items() if dt <= pd.Timestamp("2017-01-01")}
    new = set(panel) - old
    print(f"  Pre-2017 names: {len(old)}, Later listings: {len(new)}", flush=True)
    s_old, cf_old = run_trades(slice_panel(panel, names=old), horizon=HORIZON)
    r_old = summarize("Pre-2017 Listings Only", s_old, cf_old)
    s_new, cf_new = run_trades(slice_panel(panel, names=new), horizon=HORIZON)
    summarize("Later Listings Only", s_new, cf_new)
    if r_old and pooled:
        retention = r_old["dc"]["day_edge"] / pooled["dc"]["day_edge"]
        print(f"  Pre-2017 subgroup retention: {retention*100:.1f}% (Kill threshold: >= 60% and z >= 2.0)", flush=True)

    print("\n=== 6. VOL/BETA-MATCHED CONTROL & NEXT-OPEN FILL ===", flush=True)
    s_mat, cf_mat = run_trades(full, horizon=HORIZON, matched=True)
    summarize("Vol/Beta-Matched Control", s_mat, cf_mat)
    s_nxt, cf_nxt = run_trades(full, horizon=HORIZON, next_open=True)
    summarize("Next-Session Entry (Next Open)", s_nxt, cf_nxt)

    print("\n=== 7. CHRONOLOGICAL WALK-FORWARD FOLDS ===", flush=True)
    ctrl = cf(42)
    s_ser = pd.Series([t["net_pct"] for t in strat], index=[t["entry_date"] for t in strat]).groupby(level=0).mean()
    c_ser = pd.Series([t["net_pct"] for t in ctrl], index=[t["entry_date"] for t in ctrl]).groupby(level=0).mean()
    paired = (s_ser - c_ser).dropna().sort_index()
    z_pool = paired.mean() / (paired.std(ddof=1) / np.sqrt(len(paired)))
    
    K_folds = 5
    def get_fold_zs(v, k):
        chunks = np.array_split(np.asarray(v), k)
        return np.array([ch.mean() / (ch.std(ddof=1) / np.sqrt(len(ch))) for ch in chunks if len(ch) > 5 and ch.std(ddof=1) > 0])
    
    fold_zs = get_fold_zs(paired.values, K_folds)
    print(f"  Paired days: {len(paired)}, Pooled z: {z_pool:+.2f}", flush=True)
    print(f"  5 Walk-Forward Fold z-scores: {np.round(fold_zs, 2)}", flush=True)
    print(f"  Mean Fold z: {fold_zs.mean():.2f} (Homogeneous expected: {z_pool/np.sqrt(K_folds):.2f}), Spread std: {fold_zs.std(ddof=1):.2f}", flush=True)

    print("\n=== 8. PORTFOLIO SIMULATION & STRESS TEST ===", flush=True)
    eq_bench = run_portfolio_sim(panel, hold=HORIZON, mode="benchmark")
    b_st = calc_pf_stats(eq_bench)
    print(f"  Benchmark (Equal-Weight Universe B&H): CAGR {b_st['cagr']*100:+5.2f}% | MaxDD {b_st['dd']*100:5.2f}% | Sharpe {b_st['sharpe']:.2f}", flush=True)

    eq_strat = run_portfolio_sim(panel, hold=HORIZON, cost_mult=1.0, mode="strategy")
    s_st = calc_pf_stats(eq_strat)
    print(f"  Strategy (1.0x costs, 0.50% RT)       : CAGR {s_st['cagr']*100:+5.2f}% | MaxDD {s_st['dd']*100:5.2f}% | Sharpe {s_st['sharpe']:.2f}", flush=True)

    eq_15 = run_portfolio_sim(panel, hold=HORIZON, cost_mult=1.5, mode="strategy")
    s15_st = calc_pf_stats(eq_15)
    print(f"  Strategy (1.5x costs, 0.75% RT)       : CAGR {s15_st['cagr']*100:+5.2f}% | MaxDD {s15_st['dd']*100:5.2f}% | Sharpe {s15_st['sharpe']:.2f}", flush=True)

    eq_20 = run_portfolio_sim(panel, hold=HORIZON, cost_mult=2.0, mode="strategy")
    s20_st = calc_pf_stats(eq_20)
    print(f"  Strategy (2.0x costs, 1.00% RT)       : CAGR {s20_st['cagr']*100:+5.2f}% | MaxDD {s20_st['dd']*100:5.2f}% | Sharpe {s20_st['sharpe']:.2f}", flush=True)

    rand_cagrs = []
    for s in [1, 2, 3]:
        eq_rnd = run_portfolio_sim(panel, hold=HORIZON, cost_mult=1.0, mode="random", seed=s)
        rand_cagrs.append(calc_pf_stats(eq_rnd)["cagr"] * 100)
    print(f"  Random Control Portfolios (3 seeds)   : CAGR {np.mean(rand_cagrs):+5.2f}% (min {min(rand_cagrs):+5.2f}%, max {max(rand_cagrs):+5.2f}%)", flush=True)

    yr_strat = yearly_returns(eq_strat)
    yr_bench = yearly_returns(eq_bench)
    excess = yr_strat - yr_bench
    print("\n  Yearly Returns & Excess vs B&H (%):", flush=True)
    for y in sorted(excess.index):
        print(f"    {y}: Strategy {yr_strat[y]:+6.1f}% | B&H {yr_bench[y]:+6.1f}% | Excess {excess[y]:+6.1f}%", flush=True)

if __name__ == "__main__":
    main()

