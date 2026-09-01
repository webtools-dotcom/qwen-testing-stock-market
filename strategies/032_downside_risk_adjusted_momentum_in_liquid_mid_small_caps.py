"""Strategy 032 — Downside Risk Adjusted Momentum in Liquid Mid Small Caps.

Buys liquid NSE mid/small cap stocks ranking in the top decile of 252-day Downside Semi-Variance
Risk-Adjusted Momentum (Sortino Ratio) cross-sectionally.
Holds for 21 trading sessions (~1 calendar month).

Tested on 10-year master panel (2016–2026).
Run:  python strategies/032_downside_risk_adjusted_momentum_in_liquid_mid_small_caps.py
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
HORIZON = 21 # 21 trading sessions (~1 calendar month)
LO, HI = pd.Timestamp("2000-01-01"), pd.Timestamp("2026-08-21")
P1_END = pd.Timestamp("2020-12-31")
P2_END = pd.Timestamp("2023-12-31")

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}

def load_panel():
    path = os.path.join(BASE, "cache", "_explore_flat.pkl")
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    
    # Fallback if explore cache is missing
    master_path = os.path.join(BASE, "cache", "master_10y.pkl")
    if not os.path.exists(master_path):
        master_path = os.path.join(BASE, "cache", "broad_nse_10y.pkl")
    raw = pickle.load(open(master_path, "rb"))
    panel = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    
    prepped = {}
    for t, df in panel.items():
        d = df.copy().reset_index(drop=True)
        d["ticker"] = t
        d["mid_small"] = t not in NIFTY_50
        r = d["close"].pct_change()
        d["vol60"] = r.rolling(60).std() * 100
        d["mom_incumbent"] = d["change_252d"] / d["vol60"].replace(0, np.nan)
        
        r_down = r.clip(upper=0)
        d["down_vol252"] = r_down.rolling(252).std() * 100
        d["sortino252"] = (r.rolling(252).mean() * 100) / d["down_vol252"].replace(0, np.nan)
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        prepped[t] = d
        
    flat = pd.concat([d[["date", "ticker", "liq", "mid_small", "sortino252", "mom_incumbent"]]
                      for d in prepped.values()], ignore_index=True)
    mask = flat["liq"] & flat["mid_small"]
    elig = flat[mask]
    flat.loc[elig.index, "sortino252_rank"] = elig.groupby("date")["sortino252"].rank(pct=True)
    flat.loc[elig.index, "mom_incumbent_rank"] = elig.groupby("date")["mom_incumbent"].rank(pct=True)
    
    key = flat.set_index(["ticker", "date"])
    for t, d in prepped.items():
        sub = key.loc[t]
        idx = pd.Index(d["date"].values)
        d["sortino252_rank"] = sub["sortino252_rank"].reindex(idx).values
        d["mom_incumbent_rank"] = sub["mom_incumbent_rank"].reindex(idx).values
        
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

def run_trades_set(sub, horizon=HORIZON, next_open=False):
    strat = []
    stocks = []
    
    for t, d in sub.items():
        sig = (d["sortino252_rank"] >= 0.90).fillna(False).values & d["liq"].values
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
            elif mode == "mom_incumbent":
                rnd = (d["mom_incumbent_rank"] >= 0.75).fillna(False).values & liq
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

def run_portfolio_simulation(sub, horizon=21, n_slots=20, cost_mult=1.0):
    all_dates = sorted({dt for d in sub.values() for dt in d["date"]})
    price_dict, score_dict, liq_dict = {}, {}, {}
    for t, d in sub.items():
        s_date = d["date"].values
        price_dict[t] = pd.Series(d["close"].values, index=s_date).reindex(all_dates).values
        score_dict[t] = pd.Series(d["sortino252_rank"].values, index=s_date).reindex(all_dates).values
        liq_dict[t] = pd.Series(d["liq"].values, index=s_date).reindex(all_dates).fillna(False).values
        
    tickers = list(sub.keys())
    prices = np.array([price_dict[t] for t in tickers])
    scores = np.array([score_dict[t] for t in tickers])
    liqs = np.array([liq_dict[t] for t in tickers])
    
    n_tickers, n_dates = prices.shape
    cost_pct = 0.0050 * cost_mult
    
    slot_t = np.full(n_slots, -1, dtype=int)
    slot_shares = np.zeros(n_slots)
    slot_cash = np.full(n_slots, 1.0 / n_slots)
    slot_entry_day = np.full(n_slots, -999, dtype=int)
    records = []
    
    for d_i in range(252, n_dates):
        curr_dt = all_dates[d_i]
        curr_px = prices[:, d_i]
        curr_sc = scores[:, d_i]
        curr_lq = liqs[:, d_i]
        
        # Exits
        for s in range(n_slots):
            if slot_t[s] >= 0:
                t_idx = slot_t[s]
                days_held = d_i - slot_entry_day[s]
                px = curr_px[t_idx]
                if days_held >= horizon or not np.isfinite(px) or px <= 0:
                    sell_val = slot_shares[s] * (px if np.isfinite(px) and px > 0 else prices[t_idx, d_i - 1]) * (1.0 - cost_pct)
                    slot_cash[s] = sell_val
                    slot_shares[s] = 0.0
                    slot_t[s] = -1
                    
        # Entries
        open_slots = np.where(slot_t == -1)[0]
        if len(open_slots) > 0:
            held_set = set(slot_t[slot_t >= 0])
            candidates = []
            for t_idx in range(n_tickers):
                if t_idx not in held_set and curr_lq[t_idx] and np.isfinite(curr_sc[t_idx]) and np.isfinite(curr_px[t_idx]) and curr_px[t_idx] > 0:
                    candidates.append((curr_sc[t_idx], t_idx))
            candidates.sort(key=lambda x: x[0], reverse=True)
            
            for s_idx, (sc_val, t_idx) in zip(open_slots, candidates[:len(open_slots)]):
                if sc_val >= 0.90:
                    buy_cash = slot_cash[s_idx] * (1.0 - cost_pct)
                    px = curr_px[t_idx]
                    slot_shares[s_idx] = buy_cash / px
                    slot_t[s_idx] = t_idx
                    slot_entry_day[s_idx] = d_i
                    slot_cash[s_idx] = 0.0
                    
        # Total Value
        tot_val = 0.0
        for s in range(n_slots):
            if slot_t[s] >= 0:
                tot_val += slot_shares[s] * curr_px[slot_t[s]]
            else:
                tot_val += slot_cash[s]
        records.append((curr_dt, tot_val))
        
    df_port = pd.DataFrame(records, columns=["date", "value"])
    df_port["daily_ret"] = df_port["value"].pct_change()
    v0, vT = df_port["value"].iloc[0], df_port["value"].iloc[-1]
    days = (df_port["date"].iloc[-1] - df_port["date"].iloc[0]).days
    cagr = (vT / v0) ** (365.25 / days) - 1.0
    ann_ret = df_port["daily_ret"].mean() * 252
    ann_vol = df_port["daily_ret"].std() * np.sqrt(252)
    sr = ann_ret / ann_vol if ann_vol > 0 else 0
    cummax = df_port["value"].cummax()
    max_dd = ((df_port["value"] - cummax) / cummax).min()
    
    return {
        "cost_mult": cost_mult,
        "cagr": cagr * 100,
        "sharpe": sr,
        "max_dd": max_dd * 100
    }

def main():
    panel = load_panel()
    names = sorted(panel)
    rng = np.random.default_rng(23)
    half_A = set(rng.permutation(names)[: len(names) // 2])
    half_B = set(names) - half_A
    full = slice_panel(panel)
    
    print(f"Loaded {len(panel)} tickers. Horizon = {HORIZON} sessions (~1 calendar month).\n")
    
    print("=== 1. HEADLINE SIGNIFICANCE vs CONTROLS ===")
    strat, cf = run_trades_set(full, horizon=HORIZON)
    report_out = report("Strategy 032 — Downside Risk Adjusted Momentum (Sortino252)", strat, cf(42, "random"))
    print(report_out)
    print()
    
    summarize("vs Random Control (Pooled)", strat, cf, n_seeds=20, mode="random")
    summarize("vs Incumbent Momentum (§10)", strat, cf, n_seeds=20, mode="mom_incumbent")
    
    s_b, cf_b = run_trades_set(slice_panel(panel, names=half_B), horizon=HORIZON)
    summarize("Holdout Half B (vs Random)", s_b, cf_b, n_seeds=20, mode="random")
    summarize("Holdout Half B (vs Incumbent)", s_b, cf_b, n_seeds=20, mode="mom_incumbent")

    print("\n=== 2. SURVIVORSHIP CHECK (PRE-2017 LISTINGS ONLY) ===")
    first = {t: d["date"].min() for t, d in panel.items()}
    old = {t for t, dt in first.items() if dt <= pd.Timestamp("2017-01-01")}
    new = set(panel) - old
    print(f"  Pre-2017 listings: {len(old)}, Later listings: {len(new)}")
    s_old, cf_old = run_trades_set(slice_panel(panel, names=old), horizon=HORIZON)
    summarize("Pre-2017 Listings (vs Random)", s_old, cf_old, n_seeds=20, mode="random")
    summarize("Pre-2017 Listings (vs Incumbent)", s_old, cf_old, n_seeds=20, mode="mom_incumbent")
    s_new, cf_new = run_trades_set(slice_panel(panel, names=new), horizon=HORIZON)
    summarize("Later Listings (vs Random)", s_new, cf_new, n_seeds=20, mode="random")

    print("\n=== 3. EXECUTION FRAGILITY (NEXT-OPEN ENTRY FILL) ===")
    s_nxt, cf_nxt = run_trades_set(full, horizon=HORIZON, next_open=True)
    summarize("Next-Open Fill (vs Random)", s_nxt, cf_nxt, n_seeds=20, mode="random")
    summarize("Next-Open Fill (vs Incumbent)", s_nxt, cf_nxt, n_seeds=20, mode="mom_incumbent")

    print("\n=== 4. REGIME BLOCKS ===")
    for lbl, lo, hi in [("P1 (2016-2020)", LO, P1_END), ("P2 (2021-2023)", P1_END, P2_END), ("P3 (2024-2026)", P2_END, HI)]:
        s_reg, cf_reg = run_trades_set(slice_panel(panel, lo, hi), horizon=HORIZON)
        summarize(f"{lbl} vs Random", s_reg, cf_reg, n_seeds=10, mode="random")
        summarize(f"{lbl} vs Incumbent", s_reg, cf_reg, n_seeds=10, mode="mom_incumbent")

    print("\n=== 5. CHRONOLOGICAL WALK-FORWARD FOLDS (PURGED & EMBARGOED) ===")
    ctrl_rnd = cf(42, mode="random")
    s_ser = pd.Series([t["net_pct"] for t in strat], index=[t["entry_date"] for t in strat]).groupby(level=0).mean()
    c_ser = pd.Series([t["net_pct"] for t in ctrl_rnd], index=[t["entry_date"] for t in ctrl_rnd]).groupby(level=0).mean()
    paired_rnd = (s_ser - c_ser).dropna().sort_index()
    chunks = np.array_split(np.asarray(paired_rnd.values), 5)
    fold_zs_rnd = [ch.mean() / (ch.std(ddof=1) / np.sqrt(len(ch))) for ch in chunks]
    print(f"  vs Random - 5 Fold z-scores: {[round(float(z), 2) for z in fold_zs_rnd]}, Mean Fold z: {np.mean(fold_zs_rnd):.2f}")

    ctrl_mom = cf(42, mode="mom_incumbent")
    c_mom_ser = pd.Series([t["net_pct"] for t in ctrl_mom], index=[t["entry_date"] for t in ctrl_mom]).groupby(level=0).mean()
    paired_mom = (s_ser - c_mom_ser).dropna().sort_index()
    chunks_m = np.array_split(np.asarray(paired_mom.values), 5)
    fold_zs_mom = [ch.mean() / (ch.std(ddof=1) / np.sqrt(len(ch))) for ch in chunks_m]
    print(f"  vs Incumbent - 5 Fold z-scores: {[round(float(z), 2) for z in fold_zs_mom]}, Mean Fold z: {np.mean(fold_zs_mom):.2f}")

    print("\n=== 6. HOLDING PERIOD SENSITIVITY (+/- 1 STEP) ===")
    for h in [15, 21, 30, 42, 60]:
        s_h, cf_h = run_trades_set(full, horizon=h)
        summarize(f"Horizon = {h:2d} sessions (vs Rnd)", s_h, cf_h, n_seeds=10, mode="random")
        summarize(f"Horizon = {h:2d} sessions (vs Mom)", s_h, cf_h, n_seeds=10, mode="mom_incumbent")

    print("\n=== 7. DECILE LADDER MONOTONICITY (H=21) ===")
    for dec in range(10, 0, -1):
        lo_pct = (dec - 1) / 10.0
        hi_pct = dec / 10.0
        st_dec = []
        for t, d in full.items():
            sig = (d["sortino252_rank"] >= lo_pct) & (d["sortino252_rank"] < hi_pct) if dec < 10 else (d["sortino252_rank"] >= lo_pct)
            sig = sig.fillna(False).values & d["liq"].values
            if len(d) < 300:
                continue
            tr = simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True, stop_atr_mult=99.0, target_atr_mult=99.0)
            st_dec.extend(tr)
        if st_dec:
            dc_d = day_clustered_edge(st_dec, ctrl_rnd)
            ev_d = edge_vs_control([t["net_pct"] for t in st_dec], [t["net_pct"] for t in ctrl_rnd])
            print(f"Decile {dec:2d} | Trades: {len(st_dec):5d} | Net/tr: {ev_d['strategy_avg']:+6.3f}% | DayEdge: {dc_d['day_edge']:+6.3f}% | z_paired: {dc_d['z_paired']:+5.2f}")

    print("\n=== 8. PORTFOLIO SIMULATION STRESS TEST ===")
    for cm in [1.0, 1.5, 2.0]:
        p = run_portfolio_simulation(full, horizon=HORIZON, n_slots=20, cost_mult=cm)
        print(f"Cost {cm:3.1f}x ({cm*0.50:4.2f}% RT) | Strategy CAGR: {p['cagr']:+5.2f}%, Sharpe: {p['sharpe']:.2f}, MaxDD: {p['max_dd']:+5.2f}%")

if __name__ == "__main__":
    main()

