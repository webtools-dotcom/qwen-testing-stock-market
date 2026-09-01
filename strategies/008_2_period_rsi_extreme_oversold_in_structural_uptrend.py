"""Strategy 008 — 2-Period RSI Extreme Oversold in Structural Uptrend.

Hypothesis:
In liquid Indian equities (turnover >= ₹25cr/day), when an equity in an established primary
uptrend (Close > SMA 200 and SMA 50 > SMA 200) suffers extreme short-term selling pressure
causing the 2-period RSI to drop into deep oversold territory (RSI_2 < 5.0), it represents a
temporary micro-liquidation / retail stop run. Institutional dip-buyers step in to defend the
macro uptrend, generating a mean-reverting swing rebound over the subsequent 6–10 trading days.

Run:  python strategies/008_2_period_rsi_extreme_oversold_in_structural_uptrend.py
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
RSI_THRESHOLD = 5.0


def signal_mask(d, threshold=RSI_THRESHOLD):
    """RSI(2) < threshold in secular uptrend (Close > SMA 200 and SMA 50 > SMA 200)."""
    return (d['rsi_2'] < threshold) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200'])


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
        d['rsi_2'] = ta.momentum.RSIIndicator(close=d['close'], window=2).rsi()
        d = d.dropna(subset=['rsi_2', 'atr', 'close', 'sma_200', 'sma_50', 'turnover_60d']).reset_index(drop=True)
        if len(d) >= 300:
            d['ticker'] = ticker
            d['is_large_cap'] = ticker in LARGE_CAPS
            valid_dfs.append(d)

    print(f"Valid stocks: {len(valid_dfs)} ({sum(1 for d in valid_dfs if d['is_large_cap'].iat[0])} large, {sum(1 for d in valid_dfs if not d['is_large_cap'].iat[0])} mid/small)\n")

    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    for d in valid_dfs:
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d, RSI_THRESHOLD) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl  += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(report(f"Strategy 008 — 2-Period RSI < {RSI_THRESHOLD} in Uptrend (Horizon {HORIZON}d, Costs Charged)",
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
    for d in valid_dfs:
        if d['is_large_cap'].iat[0]:
            continue
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d, RSI_THRESHOLD) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        ms_strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ms_ctrl += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    def ms_ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for d in valid_dfs:
            if d['is_large_cap'].iat[0]:
                continue
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
        return c_trades

    ms_res = edge_vs_control([t['net_pct'] for t in ms_strat], [t['net_pct'] for t in ms_ctrl])
    ms_sc = stable_day_clustered_z(ms_strat, ms_ctrl_factory, n_seeds=20)
    print("\n--- SUBGROUP BREAKDOWN (§8) ---")
    if ms_res and ms_sc:
        print(f"  Mid/Small Caps Alone : Trades {ms_res['n_strategy']} | Net {ms_res['strategy_avg']:+.2f}% | Edge {ms_res['edge']:+.2f}% | Stable Mean z: {ms_sc['mean_z']:+.2f} (Pass: {ms_sc['pass_rate']*100:.0f}%)")

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
            sig = signal_mask(test_df, RSI_THRESHOLD) & liq
            rnd = (f_rng.random(len(test_df)) < 0.08) & liq
            f_strat += simulate_trades(test_df, sig, horizon_days=HORIZON, charge_costs=True)
            f_ctrl += simulate_trades(test_df, rnd, horizon_days=HORIZON, charge_costs=True)
        f_res = edge_vs_control([t['net_pct'] for t in f_strat], [t['net_pct'] for t in f_ctrl])
        f_dc = day_clustered_edge(f_strat, f_ctrl)
        d_start = valid_dfs[0]['date'].iat[min(te0, sample_len-1)].strftime('%Y-%m-%d')
        d_end = valid_dfs[0]['date'].iat[min(te1-1, sample_len-1)].strftime('%Y-%m-%d')
        if f_res and f_dc:
            print(f"  Fold {fold_idx} ({d_start} to {d_end}): Trades {f_res['n_strategy']:4d} | Net {f_res['strategy_avg']:+5.2f}% | Edge {f_res['edge']:+5.2f}% | z_paired {f_dc['z_paired']:+5.2f}")

    # Parameter sensitivity scan across RSI thresholds (2, 5, 8, 10, 15)
    print("\n--- PARAMETER SENSITIVITY LADDER ---")
    all_srs = []
    for th in [2.0, 5.0, 8.0, 10.0, 15.0]:
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
            print(f"  RSI_2 < {th:4.1f} : Trades {th_res['n_strategy']:4d} | Net {th_res['strategy_avg']:+5.2f}% | Edge {th_res['edge']:+5.2f}% | z_paired {th_dc['z_paired']:+5.2f} | Sharpe {th_sr:.2f}")

    # Deflated Sharpe
    dsr_res = deflated_sharpe(sharpe([t['net_pct'] for t in strat], holding_days=HORIZON), all_srs, len(strat))
    if dsr_res:
        print(f"\nDeflated Sharpe Ratio (DSR): {dsr_res['dsr']:.4f} across {dsr_res['n_trials']} trials")


if __name__ == "__main__":
    run()
