"""Strategy 010 — 3-Day Downside Accelerating Climax in Uptrend.

Hypothesis:
In liquid Indian equities (turnover >= ₹25cr/day), when an equity in an established primary
uptrend (Close > SMA 200) suffers 3 consecutive days of accelerating percentage losses
(ret[t] < ret[t-1] < ret[t-2] < 0) with a 5-day drop < -6%, retail stop-losses cascade
simultaneously. This represents a short-term panic liquidation / capitulation climax. As selling
exhausts, institutional dip-buyers absorb the forced selling, generating a sharp mean-reverting
swing rebound over the subsequent 6–10 trading days.

Run:  python strategies/010_3_day_downside_accelerating_climax_in_uptrend.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import numpy as np
import pandas as pd
import ta
from data_loader import CACHE_DIR, get_panel
from backtest_engine import (
    simulate_trades, day_clustered_edge, edge_vs_control,
    stable_day_clustered_z, walk_forward_splits, deflated_sharpe,
    effective_trials, sharpe, report
)

LARGE_CAPS = {
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'AXISBANK.NS',
    'LT.NS', 'ITC.NS', 'HINDUNILVR.NS', 'MARUTI.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS',
    'SUNPHARMA.NS', 'CIPLA.NS', 'DRREDDY.NS', 'WIPRO.NS', 'TECHM.NS', 'HCLTECH.NS', 'BAJFINANCE.NS',
    'ASIANPAINT.NS', 'ULTRACEMCO.NS', 'GRASIM.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'COALINDIA.NS',
    'ADANIPORTS.NS', 'TITAN.NS', 'NESTLEIND.NS', 'BRITANNIA.NS', 'DIVISLAB.NS', 'EICHERMOT.NS',
    'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'BPCL.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS',
    'INDUSINDBK.NS', 'KOTAKBANK.NS', 'M&M.NS', 'SBILIFE.NS', 'SHRIRAMFIN.NS', 'TRENT.NS', 'APOLLOHOSP.NS'
}

HORIZON = 7
MIN_TURNOVER = 25e7
ROC_THRESHOLD = -6.0


def signal_mask(d, roc_th=ROC_THRESHOLD):
    """3 consecutive down days with accelerating percentage drops in 200 SMA uptrend.
    
    Condition: ret[t] < ret[t-1] < ret[t-2] < 0 AND 5-day RoC < roc_th AND Close > SMA 200.
    """
    daily_ret = d['close'].pct_change() * 100
    roc_5 = d['close'].pct_change(5) * 100
    
    accel = (daily_ret < daily_ret.shift(1)) & (daily_ret.shift(1) < daily_ret.shift(2)) & (daily_ret.shift(2) < 0)
    deep_drop = roc_5 < roc_th
    uptrend = d['close'] > d['sma_200']
    
    return (accel & deep_drop & uptrend).fillna(False).values


def run():
    cache_path = os.path.join(CACHE_DIR, "nifty_research_150_5y.pkl")
    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as fh:
            obj = pickle.load(fh)
        panel = obj['data']
        print(f"Loaded cached panel ({len(panel)} stocks, 5y)...")
    else:
        raise FileNotFoundError(f"Cache file {cache_path} not found.")

    valid_dfs = []
    for ticker, df in panel.items():
        d = df.copy().sort_values('date').reset_index(drop=True)
        d = d.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'turnover_60d']).reset_index(drop=True)
        if len(d) >= 300:
            d['ticker'] = ticker
            d['is_large_cap'] = ticker in LARGE_CAPS
            valid_dfs.append(d)

    n_large = sum(1 for d in valid_dfs if d['is_large_cap'].iat[0])
    n_midsm = sum(1 for d in valid_dfs if not d['is_large_cap'].iat[0])
    print(f"Valid stocks: {len(valid_dfs)} ({n_large} large, {n_midsm} mid/small)\n")

    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    for d in valid_dfs:
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d, ROC_THRESHOLD) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl  += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(report(f"Strategy 010 — 3-Day Accelerating Climax in Uptrend (Horizon {HORIZON}d, Costs Charged)",
                 strat, ctrl, holding_days=HORIZON))

    dc = day_clustered_edge(strat, ctrl)
    print("\n--- DAY-CLUSTERED HEADLINE VERDICT ---")
    if dc:
        print(f"  Single Draw z_paired : {dc['z_paired']:+.2f} (day_edge: {dc['day_edge']:+.3f}%, paired days: {dc['n_paired_days']})")

    def ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for d in valid_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
        return c_trades

    sc = stable_day_clustered_z(strat, ctrl_factory, n_seeds=20)
    if sc:
        print(f"  Stable Mean z_paired : {sc['mean_z']:+.2f} (min: {sc['min_z']:+.2f}, max: {sc['max_z']:+.2f}) across {sc['n_seeds']} seeds")
        print(f"  Pass Rate (z >= 2.0) : {sc['pass_rate']*100:.1f}%")

    # Mid/Small Subgroup (§8)
    ms_strat, ms_ctrl = [], []
    ms_indices = []
    for idx, d in enumerate(valid_dfs):
        if d['is_large_cap'].iat[0]:
            continue
        ms_indices.append(idx)
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d, ROC_THRESHOLD) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        ms_strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ms_ctrl += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    def ms_ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for idx in ms_indices:
            d = valid_dfs[idx]
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
        return c_trades

    ms_res = edge_vs_control([t['net_pct'] for t in ms_strat], [t['net_pct'] for t in ms_ctrl])
    ms_sc = stable_day_clustered_z(ms_strat, ms_ctrl_factory, n_seeds=20) if len(ms_strat) >= 10 else None
    print("\n--- SUBGROUP BREAKDOWN (§8) ---")
    if ms_res and ms_sc:
        print(f"  Mid/Small Caps Alone : Trades {ms_res['n_strategy']} | Net {ms_res['strategy_avg']:+.2f}% | Edge {ms_res['edge']:+.2f}% | Stable Mean z: {ms_sc['mean_z']:+.2f} (Pass: {ms_sc['pass_rate']*100:.0f}%)")
    elif ms_res:
        ms_dc = day_clustered_edge(ms_strat, ms_ctrl)
        z_str = f"z_paired {ms_dc['z_paired']:+.2f}" if ms_dc else "n/a"
        print(f"  Mid/Small Caps Alone : Trades {ms_res['n_strategy']} | Net {ms_res['strategy_avg']:+.2f}% | Edge {ms_res['edge']:+.2f}% | {z_str}")

    lc_strat, lc_ctrl = [], []
    for d in valid_dfs:
        if not d['is_large_cap'].iat[0]:
            continue
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d, ROC_THRESHOLD) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        lc_strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        lc_ctrl += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    lc_res = edge_vs_control([t['net_pct'] for t in lc_strat], [t['net_pct'] for t in lc_ctrl])
    if lc_res:
        lc_dc = day_clustered_edge(lc_strat, lc_ctrl)
        z_str = f"z_paired {lc_dc['z_paired']:+.2f}" if lc_dc else "n/a"
        print(f"  Large Caps Alone     : Trades {lc_res['n_strategy']} | Net {lc_res['strategy_avg']:+.2f}% | Edge {lc_res['edge']:+.2f}% | {z_str}")

    # Walk-forward validation
    sample_len = len(valid_dfs[0])
    splits = list(walk_forward_splits(sample_len, n_splits=4, horizon_days=HORIZON))
    print(f"\n--- WALK-FORWARD VALIDATION ({len(splits)} purged folds) ---")
    for fold_idx, ((tr0, tr1), (te0, te1)) in enumerate(splits, 1):
        f_rng = np.random.default_rng(42 + fold_idx)
        f_strat, f_ctrl = [], []
        for d in valid_dfs:
            test_df = d.iloc[te0:te1].reset_index(drop=True)
            if len(test_df) < HORIZON + 2:
                continue
            liq = (test_df['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            sig = signal_mask(test_df, ROC_THRESHOLD) & liq
            rnd = (f_rng.random(len(test_df)) < 0.08) & liq
            f_strat += simulate_trades(test_df, sig, horizon_days=HORIZON, charge_costs=True)
            f_ctrl += simulate_trades(test_df, rnd, horizon_days=HORIZON, charge_costs=True)
        f_res = edge_vs_control([t['net_pct'] for t in f_strat], [t['net_pct'] for t in f_ctrl])
        f_dc = day_clustered_edge(f_strat, f_ctrl)
        d_start = valid_dfs[0]['date'].iat[min(te0, sample_len-1)].strftime('%Y-%m-%d')
        d_end = valid_dfs[0]['date'].iat[min(te1-1, sample_len-1)].strftime('%Y-%m-%d')
        if f_res and f_dc:
            print(f"  Fold {fold_idx} ({d_start} to {d_end}): Trades {f_res['n_strategy']:4d} | Net {f_res['strategy_avg']:+5.2f}% | Edge {f_res['edge']:+5.2f}% | z_paired {f_dc['z_paired']:+5.2f}")
        else:
            print(f"  Fold {fold_idx} ({d_start} to {d_end}): Trades {len(f_strat):4d} -- insufficient for paired analysis")

    # Parameter sensitivity scan
    print("\n--- PARAMETER SENSITIVITY LADDER ---")
    all_srs = []
    for th in [-4.0, -6.0, -8.0]:
        th_strat = []
        for d in valid_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            sig = signal_mask(d, th) & liq
            th_strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        th_res = edge_vs_control([t['net_pct'] for t in th_strat], [t['net_pct'] for t in ctrl])
        th_dc = day_clustered_edge(th_strat, ctrl)
        th_sr = sharpe([t['net_pct'] for t in th_strat], holding_days=HORIZON)
        all_srs.append(th_sr)
        if th_res and th_dc:
            print(f"  5d RoC < {th:4.1f}% : Trades {th_res['n_strategy']:4d} | Net {th_res['strategy_avg']:+5.2f}% | Edge {th_res['edge']:+5.2f}% | z_paired {th_dc['z_paired']:+5.2f} | Sharpe {th_sr:.2f}")

    # Final verdict guide
    print("\n" + "="*70)
    print("FINAL VERDICT")
    print("="*70)
    if sc:
        if sc['mean_z'] >= 2.0 and sc['pass_rate'] >= 0.80 and (ms_sc is None or ms_sc['mean_z'] >= 2.0):
            print(f"VERDICT: ADOPT-eligible — Stable mean z_paired {sc['mean_z']:.2f} >= 2.0")
        else:
            print(f"VERDICT: REJECT — Stable mean z_paired {sc['mean_z']:.2f} < 2.0 (pass rate {sc['pass_rate']*100:.0f}%)")


if __name__ == "__main__":
    run()
