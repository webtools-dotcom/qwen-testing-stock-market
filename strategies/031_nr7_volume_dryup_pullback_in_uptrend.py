"""Strategy 031 — NR7 Volume Dryup Pullback in Uptrend.

Buys liquid NSE mid/small caps forming an NR7 (Narrowest Range in 7 sessions) with volume dryup
(< 0.60x 20-day average volume) while trading above both their 50-day and 200-day SMAs.
Tested on a 10-year master panel (2016-2026).

Run:  python strategies/031_nr7_volume_dryup_pullback_in_uptrend.py
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
HORIZON = 15 # 15 sessions (~3 weeks)
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

def prepare(panel):
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
        
        # NR7 & Volume Dryup features
        d["rng"] = (d["high"] - d["low"]) / d["close"] * 100
        min_rng_7 = d["rng"].rolling(7).min()
        d["is_nr7"] = d["rng"] <= min_rng_7
        d["vol_dryup"] = d["volume"] < 0.60 * d["volume"].rolling(20).mean()
        
        # Trend filters
        d["in_uptrend"] = (d["close"] > d["sma_200"]) & (d["close"] > d["sma_50"])
        
        # Signal
        d["signal"] = d["is_nr7"] & d["vol_dryup"] & d["in_uptrend"]
        
        # Momentum score for incumbent comparison (252d return / vol60)
        d["mom_score"] = d["change_252d"] / d["vol60"].replace(0, np.nan)

        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        m1 = mkt.reindex(pd.Index(d["date"].values)).values * 100
        d["beta"] = (pd.Series(r.values * 100).rolling(120).cov(pd.Series(m1))
                     / pd.Series(m1).rolling(120).var())
        prepped[t] = d

    flat = pd.concat([d[["date", "ticker", "liq", "mid_small", "atr_pct", "beta", "mom_score"]]
                      for d in prepped.values()], ignore_index=True)
    mask = flat["liq"] & flat["mid_small"]
    elig = flat[mask]
    flat.loc[elig.index, "mom_rank"] = elig.groupby("date")["mom_score"].rank(pct=True)

    for c, n in (("atr_pct", "vol_t"), ("beta", "beta_t")):
        flat.loc[elig.index, n] = elig.groupby("date")[c].transform(
            lambda s: pd.qcut(s.rank(method="first"), 3, labels=False) if s.notna().sum() >= 3 else np.nan)

    key = flat.set_index(["ticker", "date"])
    for t, d in prepped.items():
        sub = key.loc[t]
        idx = pd.Index(d["date"].values)
        for c in ["mom_rank", "vol_t", "beta_t"]:
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

def run_trades_set(sub, horizon=HORIZON, next_open=False, matched=False):
    strat = []
    stocks = []
    
    for t, d in sub.items():
        sig = d["signal"].fillna(False).values & d["liq"].values
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
        
    def control_factory(seed, mode="random"):
        rng = np.random.default_rng(seed)
        ctrl = []
        for t, d in stocks:
            liq = d["liq"].values
            if mode == "random":
                rnd = (rng.random(len(d)) < 0.10) & liq
            elif mode == "uptrend":
                rnd = (rng.random(len(d)) < 0.10) & d["in_uptrend"].fillna(False).values & liq
            elif mode == "mom_incumbent":
                rnd = (d["mom_rank"] >= 0.75).fillna(False).values & liq
            ct = simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True,
                                 stop_atr_mult=99.0, target_atr_mult=99.0)
            for item in ct:
                item["ticker"] = t
            ctrl.extend(ct)
        return ctrl

    return strat, control_factory

def summarize(label, strat, cf, n_seeds=20, mode="random"):
    if not strat:
        print(f"{label}: NO TRADES", flush=True)
        return None
    c0 = cf(42, mode=mode)
    ev = edge_vs_control([t["net_pct"] for t in strat], [t["net_pct"] for t in c0])
    dc = day_clustered_edge(strat, c0)
    sc = stable_day_clustered_z(strat, lambda s: cf(s, mode=mode), n_seeds=n_seeds)
    print(f"{label:<36} | Tr: {len(strat):5d} | Day: {dc['n_paired_days']:4d} | "
          f"Stable Mean z: {sc['mean_z']:+5.2f} (pass {sc['pass_rate']*100:3.0f}%, min {sc['min_z']:+5.2f}, max {sc['max_z']:+5.2f}) | "
          f"DayEdge: {dc['day_edge']:+6.3f}% | Net/tr: {ev['strategy_avg']:+6.3f}% (ctrl {ev['control_avg']:+6.3f}%)",
          flush=True)
    return {"ev": ev, "dc": dc, "sc": sc}

def main():
    raw_panel = load("master_10y")
    panel = prepare(raw_panel)
    names = sorted(panel)
    rng = np.random.default_rng(23)
    half_A = set(rng.permutation(names)[: len(names) // 2])
    half_B = set(names) - half_A
    full = slice_panel(panel)
    
    print(f"Loaded {len(panel)} names, {len(full)} liquid mid/small caps. Horizon = {HORIZON} sessions.\n", flush=True)
    
    print("=== 1. HEADLINE SIGNIFICANCE vs CONTROLS ===", flush=True)
    strat, cf = run_trades_set(full, horizon=HORIZON)
    pooled = summarize("vs Random Control", strat, cf, mode="random")
    summarize("vs Uptrend Control", strat, cf, mode="uptrend")
    summarize("vs Incumbent Momentum Basket (§10)", strat, cf, mode="mom_incumbent")
    
    s_b, cf_b = run_trades_set(slice_panel(panel, names=half_B), horizon=HORIZON)
    summarize("Holdout Half B (vs Random)", s_b, cf_b, mode="random")

    print("\n=== 2. HOLDING PERIOD SENSITIVITY (+/- 1 STEP) ===", flush=True)
    for h in [6, 8, 10, 15, 21]:
        s_h, cf_h = run_trades_set(full, horizon=h)
        summarize(f"Horizon = {h:2d} sessions", s_h, cf_h, n_seeds=10, mode="random")

    print("\n=== 3. REGIME BLOCKS ===", flush=True)
    for lbl, lo, hi in [("P1 (2016-2020)", LO, P1_END), ("P2 (2021-2023)", P1_END, P2_END), ("P3 (2024-2026)", P2_END, HI)]:
        s_reg, cf_reg = run_trades_set(slice_panel(panel, lo, hi), horizon=HORIZON)
        summarize(lbl, s_reg, cf_reg, mode="random")

    print("\n=== 4. SURVIVORSHIP CHECK (PRE-2017 LISTINGS ONLY) ===", flush=True)
    first = {t: d["date"].min() for t, d in panel.items()}
    old = {t for t, dt in first.items() if dt <= pd.Timestamp("2017-01-01")}
    new = set(panel) - old
    print(f"  Pre-2017 names: {len(old)}, Later listings: {len(new)}", flush=True)
    s_old, cf_old = run_trades_set(slice_panel(panel, names=old), horizon=HORIZON)
    r_old = summarize("Pre-2017 Listings Only", s_old, cf_old, mode="random")
    s_new, cf_new = run_trades_set(slice_panel(panel, names=new), horizon=HORIZON)
    summarize("Later Listings Only", s_new, cf_new, mode="random")

    print("\n=== 5. CHRONOLOGICAL WALK-FORWARD FOLDS ===", flush=True)
    ctrl = cf(42, mode="random")
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
    print(f"  Mean Fold z: {fold_zs.mean():.2f}, Spread std: {fold_zs.std(ddof=1):.2f}", flush=True)

if __name__ == "__main__":
    main()

