"""Strategy 036 — Institutional Volume Absorption Pullback in Golden Cross Equities.

Tests whether requiring above-average volume (volume ratio >= 1.2x 20-day median) on an oversold
pullback (Wilder RSI(14) <= 35) in established Golden Cross equities (Close > SMA200 and
SMA50 > SMA200 with 1-year momentum >= 30%) provides an edge over random entry and beats the
incumbent AR-001 (RSI<30 Golden Cross) baseline over an 8-trading-day swing horizon.

Run:  python strategies/036_institutional_volume_absorption_pullback_in_golden_cross_equities.py
"""

import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z,
    deflated_sharpe, round_trip_cost_pct
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_TURNOVER = 25e7
HORIZON = 8

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}

def load_data():
    master_path = os.path.join(BASE, "cache", "master_10y.pkl")
    raw = pickle.load(open(master_path, "rb"))
    panel = raw["data"] if isinstance(raw, dict) and "data" in raw else raw

    stocks = {}
    pre_2017 = set()
    large_caps = {}

    for t, df in panel.items():
        if df["date"].min() <= pd.Timestamp("2016-12-31"):
            pre_2017.add(t)
        d = df.dropna(subset=["close", "volume", "rsi", "sma_200", "sma_50", "change_252d", "atr"]).reset_index(drop=True).copy()
        if len(d) < 300:
            continue
        d["ticker"] = t
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        d["uptrend_200"] = (d["close"] > d["sma_200"]).fillna(False)
        d["golden_cross"] = (d["sma_50"] > d["sma_200"]).fillna(False)
        d["mom_252"] = (d["change_252d"] >= 30.0).fillna(False)

        vol20 = d["volume"].rolling(20).median()
        d["vol_ratio"] = d["volume"] / vol20.replace(0, np.nan)

        if t in NIFTY_50:
            large_caps[t] = d
        else:
            stocks[t] = d

    return stocks, pre_2017, large_caps

def run():
    print("=" * 80)
    print("STRATEGY 036: Institutional Volume Absorption Pullback in Golden Cross Equities")
    print("=" * 80)

    stocks, pre_2017_all, large_caps = load_data()
    tickers = sorted(stocks.keys())
    pre_2017 = pre_2017_all.intersection(set(tickers))
    later_listed = set(tickers) - pre_2017

    half = len(tickers) // 2
    half_A = set(tickers[:half])
    half_B = set(tickers[half:])

    print(f"Panel: {len(tickers)} Mid/Small liquid stocks, {len(large_caps)} Large caps")
    print(f"Survivorship Split: {len(pre_2017)} Pre-2017 listed, {len(later_listed)} Later listed")
    print(f"Subgroup Split: {len(half_A)} Half A names, {len(half_B)} Half B names")

    # 1. Baseline Strategy Trades (Horizon = 8d, Close > SMA_200, SMA_50 > SMA_200, Mom >= 30%, RSI <= 35, Vol >= 1.2x)
    strat_trades = []
    strat_no = []
    for t, d in stocks.items():
        liq = d["liq"].values
        sig = (d["rsi"] <= 35.0) & (d["vol_ratio"] >= 1.20) & d["golden_cross"] & d["uptrend_200"] & d["mom_252"] & liq
        trs = simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        for tr in trs: tr["ticker"] = t
        strat_trades += trs

        # Next-Open entry simulation
        open_ = d["open"].values
        close = d["close"].values
        turnover = d["turnover_60d"].values
        n = len(d)
        last_exit = -1
        for i in range(n - HORIZON - 1):
            if not sig[i] or i <= last_exit:
                continue
            nxt = i + 1
            entry_price = open_[nxt]
            exit_price = close[nxt + HORIZON]
            gross = (exit_price - entry_price) / entry_price * 100
            cost = round_trip_cost_pct(turnover[nxt])
            strat_no.append({
                'entry_date': d['date'].iat[nxt],
                'gross_pct': gross,
                'net_pct': gross - cost,
                'cost_pct': cost,
                'ticker': t
            })
            last_exit = nxt + HORIZON

    print(f"\n[1] Strategy Trades: {len(strat_trades)} (Next-Open: {len(strat_no)})")
    gross_ret = np.mean([tr["gross_pct"] for tr in strat_trades])
    net_ret = np.mean([tr["net_pct"] for tr in strat_trades])
    cost_ret = np.mean([tr["cost_pct"] for tr in strat_trades])
    win_rate = np.mean([tr["net_pct"] > 0 for tr in strat_trades]) * 100
    print(f"    Gross Return / Trade : {gross_ret:+.3f}%")
    print(f"    Round-Trip Cost      : {cost_ret:.3f}%")
    print(f"    NET Return / Trade   : {net_ret:+.3f}%")
    print(f"    Win Rate             : {win_rate:.1f}%")

    # 2. Pre-generate 20 Random Control Seeds
    print("\n[2] Generating 20 Random-Entry Controls...")
    t0 = time.time()
    controls = []
    controls_no = []
    for s in range(20):
        rng = np.random.default_rng(s)
        ctrl, ctrl_no = [], []
        for t, d in stocks.items():
            liq = d["liq"].values
            rnd = (rng.random(len(d)) < 0.05) & liq
            trs = simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
            for tr in trs: tr["ticker"] = t
            ctrl += trs

            open_ = d["open"].values
            close = d["close"].values
            turnover = d["turnover_60d"].values
            n = len(d)
            last_exit = -1
            for i in range(n - HORIZON - 1):
                if not rnd[i] or i <= last_exit: continue
                nxt = i + 1
                entry_price = open_[nxt]
                exit_price = close[nxt + HORIZON]
                gross = (exit_price - entry_price) / entry_price * 100
                cost = round_trip_cost_pct(turnover[nxt])
                ctrl_no.append({
                    'entry_date': d['date'].iat[nxt],
                    'gross_pct': gross,
                    'net_pct': gross - cost,
                    'ticker': t
                })
                last_exit = nxt + HORIZON
        controls.append(ctrl)
        controls_no.append(ctrl_no)
    print(f"    Generated in {time.time()-t0:.1f}s")

    # Stable Z vs Random Control
    zs_rnd = [day_clustered_edge(strat_trades, c)['z_paired'] for c in controls]
    edges_rnd = [day_clustered_edge(strat_trades, c)['day_edge'] for c in controls]
    mean_z_rnd = np.mean(zs_rnd)
    pass_rate_rnd = np.mean([z >= 2.0 for z in zs_rnd]) * 100
    mean_edge_rnd = np.mean(edges_rnd)
    print(f"    Stable Mean z_paired : {mean_z_rnd:+.2f} (min {np.min(zs_rnd):+.2f}, max {np.max(zs_rnd):+.2f})")
    print(f"    Pass Rate (z >= 2.0) : {pass_rate_rnd:.1f}%")
    print(f"    Net Day Edge vs Ctrl : {mean_edge_rnd:+.3f}%")

    # 3. Head-to-Head vs AR-001 (Golden Cross RSI<30) Baseline (METHODOLOGY §10)
    print("\n[3] Head-to-Head vs AR-001 (Golden Cross RSI<30) Baseline (METHODOLOGY §10):")
    inc_trades = []
    for t, d in stocks.items():
        liq = d["liq"].values
        sig = (d["rsi"] < 30) & d["golden_cross"] & d["uptrend_200"] & liq
        trs = simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        for tr in trs: tr["ticker"] = t
        inc_trades += trs
    dc_inc = day_clustered_edge(strat_trades, inc_trades)
    print(f"    Incumbent AR-001 Trades : {len(inc_trades)}")
    print(f"    Incumbent Net Return    : {np.mean([tr['net_pct'] for tr in inc_trades]):+.3f}%")
    print(f"    Day-Clustered z_paired  : {dc_inc['z_paired']:+.2f}")
    print(f"    Net Day Edge vs Incumb  : {dc_inc['day_edge']:+.3f}%")
    print(f"    Paired Days             : {dc_inc['n_paired_days']}")

    # 4. Subgroup Tests (§8)
    print("\n[4] Subgroup Robustness (§8):")
    strat_A = [tr for tr in strat_trades if tr["ticker"] in half_A]
    strat_B = [tr for tr in strat_trades if tr["ticker"] in half_B]
    zs_A = [day_clustered_edge(strat_A, [tr for tr in c if tr["ticker"] in half_A])['z_paired'] for c in controls]
    zs_B = [day_clustered_edge(strat_B, [tr for tr in c if tr["ticker"] in half_B])['z_paired'] for c in controls]
    print(f"    Half A (n={len(strat_A):4d}) : stable mean z = {np.mean(zs_A):+.2f} (pass {np.mean([z>=2.0 for z in zs_A])*100:.0f}%)")
    print(f"    Half B (n={len(strat_B):4d}) : stable mean z = {np.mean(zs_B):+.2f} (pass {np.mean([z>=2.0 for z in zs_B])*100:.0f}%)")

    # 5. Survivorship Test: Pre-2017 Listings (§4)
    print("\n[5] Survivorship Check (Pre-2017 Listings):")
    strat_pre17 = [tr for tr in strat_trades if tr["ticker"] in pre_2017]
    strat_post17 = [tr for tr in strat_trades if tr["ticker"] in later_listed]
    zs_pre17 = [day_clustered_edge(strat_pre17, [tr for tr in c if tr["ticker"] in pre_2017])['z_paired'] for c in controls]
    zs_post17 = [day_clustered_edge(strat_post17, [tr for tr in c if tr["ticker"] in later_listed])['z_paired'] for c in controls]
    print(f"    Pre-2017 (n={len(strat_pre17):4d}) : stable mean z = {np.mean(zs_pre17):+.2f} (pass {np.mean([z>=2.0 for z in zs_pre17])*100:.0f}%)")
    print(f"    Post-2017 (n={len(strat_post17):4d}): stable mean z = {np.mean(zs_post17):+.2f}")

    # 6. Execution Fragility: Next-Open Fills
    print("\n[6] Execution Fragility (Next-Open Entry Fill):")
    zs_no = [day_clustered_edge(strat_no, c_no)['z_paired'] for c_no in controls_no]
    net_no = np.mean([tr["net_pct"] for tr in strat_no])
    print(f"    Next-Open Trades       : {len(strat_no)}")
    print(f"    Next-Open Net Return   : {net_no:+.3f}%")
    print(f"    Next-Open Stable Mean z: {np.mean(zs_no):+.2f} (pass {np.mean([z>=2.0 for z in zs_no])*100:.0f}%)")

    # 7. Walk-Forward Chronological Folds (§7)
    print("\n[7] Chronological Walk-Forward Folds (5 Folds):")
    dates = pd.to_datetime([tr['entry_date'] for tr in strat_trades])
    fold_edges = pd.date_range(dates.min(), dates.max(), periods=6)
    ctrl_sample = controls[0]
    fold_zs = []
    for f_idx in range(5):
        d0, d1 = fold_edges[f_idx], fold_edges[f_idx+1]
        f_s = [tr for tr in strat_trades if d0 <= pd.to_datetime(tr['entry_date']) < d1]
        f_c = [tr for tr in ctrl_sample if d0 <= pd.to_datetime(tr['entry_date']) < d1]
        dc_f = day_clustered_edge(f_s, f_c)
        z_f = dc_f['z_paired'] if dc_f else 0.0
        fold_zs.append(z_f)
        print(f"    Fold {f_idx+1} ({d0.strftime('%Y-%m')} to {d1.strftime('%Y-%m')}) : Trades={len(f_s):3d}, z_paired={z_f:+5.2f}")
    print(f"    Mean Fold z = {np.mean(fold_zs):+.2f}")

    # 8. Threshold Sensitivity Step (§6)
    print("\n[8] Threshold Sensitivity (Wilder RSI Cutoff Steps):")
    for rsi_step in [30.0, 32.0, 35.0, 38.0]:
        s_step = []
        for t, d in stocks.items():
            liq = d["liq"].values
            sig = (d["rsi"] <= rsi_step) & (d["vol_ratio"] >= 1.20) & d["golden_cross"] & d["uptrend_200"] & d["mom_252"] & liq
            trs = simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
            for tr in trs: tr["ticker"] = t
            s_step += trs
        z_step = np.mean([day_clustered_edge(s_step, c)['z_paired'] for c in controls])
        net_step = np.mean([tr["net_pct"] for tr in s_step])
        print(f"    RSI <= {rsi_step:4.1f} | Trades: {len(s_step):4d} | Net: {net_step:+.3f}% | Mean z: {z_step:+5.2f}")

    print("\n" + "=" * 80)
    print("VERDICT EVALUATION:")
    print(f"1. Pooled Mean z vs Random  : {mean_z_rnd:+.2f} (Pass: {pass_rate_rnd:.0f}%) -> {'PASS' if mean_z_rnd >= 2.0 else 'FAIL'}")
    print(f"2. Head-to-head vs AR-001  : z = {dc_inc['z_paired']:+.2f} (Edge: {dc_inc['day_edge']:+.3f}%) -> {'PASS' if dc_inc['z_paired'] >= 2.0 and dc_inc['day_edge'] > 0 else 'FAIL'}")
    print(f"3. Half A Subgroup (§8)     : z = {np.mean(zs_A):+.2f} -> {'PASS' if np.mean(zs_A) >= 2.0 else 'FAIL'}")
    print(f"4. Half B Subgroup (§8)     : z = {np.mean(zs_B):+.2f} -> {'PASS' if np.mean(zs_B) >= 2.0 else 'FAIL'}")
    print(f"5. Pre-2017 Survivorship (§4): z = {np.mean(zs_pre17):+.2f} -> {'PASS' if np.mean(zs_pre17) >= 2.0 else 'FAIL'}")
    print(f"6. Most Recent Fold (§7)    : Fold 5 z = {fold_zs[4]:+.2f} -> {'PASS' if fold_zs[4] >= 0 else 'FAIL'}")
    print(f"7. Next-Open Execution Fill : Net = {net_no:+.3f}%, Mean z = {np.mean(zs_no):+.2f} -> {'PASS' if np.mean(zs_no) >= 2.0 else 'FAIL'}")
    print("=" * 80)

if __name__ == "__main__":
    run()

