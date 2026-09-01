import sys, os
sys.path.insert(0, r"d:\nabop\backtesting-unique-strategies")

import pickle
import numpy as np
import pandas as pd
import ta
from data_loader import CACHE_DIR
from backtest_engine import (
    simulate_trades, edge_vs_control, day_clustered_edge,
    stable_day_clustered_z, walk_forward_splits, report
)

path = os.path.join(CACHE_DIR, "nifty_research_150_5y.pkl")
with open(path, 'rb') as fh:
    obj = pickle.load(fh)
panel = obj['data']

MIN_TURNOVER = 25e7

LARGE_CAPS = {
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'AXISBANK.NS',
    'LT.NS', 'ITC.NS', 'HINDUNILVR.NS', 'MARUTI.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS',
    'SUNPHARMA.NS', 'CIPLA.NS', 'DRREDDY.NS', 'WIPRO.NS', 'TECHM.NS', 'HCLTECH.NS', 'BAJFINANCE.NS',
    'ASIANPAINT.NS', 'ULTRACEMCO.NS', 'GRASIM.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'COALINDIA.NS',
    'ADANIPORTS.NS', 'TITAN.NS', 'NESTLEIND.NS', 'BRITANNIA.NS', 'DIVISLAB.NS', 'EICHERMOT.NS',
    'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'BPCL.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS',
    'INDUSINDBK.NS', 'KOTAKBANK.NS', 'M&M.NS', 'SBILIFE.NS', 'SHRIRAMFIN.NS', 'TRENT.NS', 'APOLLOHOSP.NS'
}

processed = {}
for ticker, df in panel.items():
    d = df.copy().sort_values('date').reset_index(drop=True)
    d['ticker'] = ticker
    d['is_large_cap'] = ticker in LARGE_CAPS
    
    # RSI velocity / acceleration
    d['rsi_vel_3'] = d['rsi'] - d['rsi'].shift(3)
    d['rsi_vel_5'] = d['rsi'] - d['rsi'].shift(5)
    
    # Range / Volume
    d['vol_med_20'] = d['volume'].rolling(20).median()
    d['vol_ratio'] = d['volume'] / d['vol_med_20'].replace(0, np.nan)
    d['daily_ret'] = d['close'].pct_change() * 100
    
    # Setup 1: Rapid RSI Velocity Collapse (RSI drops > 18 points in 3 days, ending < 32, in uptrend)
    d['rsi_velocity_washout'] = (d['rsi_vel_3'] < -16.0) & (d['rsi'] < 32) & (d['close'] > d['sma_200'])
    
    # Setup 2: RSI Velocity Washout in Mid/Small Caps only
    d['rsi_vel_ms'] = d['rsi_velocity_washout'] & (~d['is_large_cap'])
    
    # Setup 3: 5-Day RSI Velocity Collapse (RSI drops > 22 points in 5 days, ending < 32)
    d['rsi_5d_vel'] = (d['rsi_vel_5'] < -22.0) & (d['rsi'] < 32) & (d['close'] > d['sma_200'])
    
    # Setup 4: 200 SMA Structural Rebound with Hammer (Price touches 200 SMA and bounces)
    d['touch_200sma'] = (d['low'] <= 1.01 * d['sma_200']) & (d['close'] >= d['sma_200']) & (d['close'] > d['open']) & (d['vol_ratio'] > 1.2)
    
    # Setup 5: 3-Bar Bear Trap Below 50 SMA (Dips below 50 SMA for 1-2 bars, then strong close back above 50 SMA +2%)
    d['bear_trap_50sma'] = (d['low'].shift(1) < d['sma_50'].shift(1)) & (d['close'] > d['sma_50'] * 1.015) & (d['vol_ratio'] > 1.5) & (d['close'] > d['sma_200'])

    d = d.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'sma_50', 'turnover_60d']).reset_index(drop=True)
    if len(d) >= 300:
        processed[ticker] = d

print(f"Loaded {len(processed)} stocks.")

def eval_strategy(name, signal_fn, horizon=7):
    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    valid_dfs = []
    
    for ticker, d in processed.items():
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_fn(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        
        strat_t = simulate_trades(d, sig, horizon_days=horizon, charge_costs=True)
        ctrl_t = simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        strat += strat_t
        ctrl += ctrl_t
        valid_dfs.append(d)
        
    res = edge_vs_control([t['net_pct'] for t in strat], [t['net_pct'] for t in ctrl])
    dc = day_clustered_edge(strat, ctrl)
    
    if res is None or dc is None or len(strat) < 15:
        print(f"[{name:55s}] INSUFFICIENT TRADES (trades={len(strat)})")
        return None
    
    def ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for d in valid_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        return c_trades
    
    sc = stable_day_clustered_z(strat, ctrl_factory, n_seeds=15)
    
    # Subgroup Mid/Small check (§8)
    ms_strat, ms_ctrl = [], []
    for ticker, d in processed.items():
        if d['is_large_cap'].iat[0]:
            continue
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_fn(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        ms_strat += simulate_trades(d, sig, horizon_days=horizon, charge_costs=True)
        ms_ctrl += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        
    def ms_ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for ticker, d in processed.items():
            if d['is_large_cap'].iat[0]:
                continue
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        return c_trades
        
    ms_sc = stable_day_clustered_z(ms_strat, ms_ctrl_factory, n_seeds=15) if len(ms_strat) >= 10 else None
    
    # Walk forward
    sample_len = len(valid_dfs[0])
    splits = list(walk_forward_splits(sample_len, n_splits=4, horizon_days=horizon))
    wf_folds = []
    for fold_idx, ((tr0, tr1), (te0, te1)) in enumerate(splits, 1):
        f_rng = np.random.default_rng(42 + fold_idx)
        f_strat, f_ctrl = [], []
        for d in valid_dfs:
            test_df = d.iloc[te0:te1].reset_index(drop=True)
            if len(test_df) < horizon + 2:
                continue
            liq = (test_df['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            sig = signal_fn(test_df) & liq
            rnd = (f_rng.random(len(test_df)) < 0.08) & liq
            f_strat += simulate_trades(test_df, sig, horizon_days=horizon, charge_costs=True)
            f_ctrl += simulate_trades(test_df, rnd, horizon_days=horizon, charge_costs=True)
        f_dc = day_clustered_edge(f_strat, f_ctrl)
        f_res = edge_vs_control([t['net_pct'] for t in f_strat], [t['net_pct'] for t in f_ctrl])
        if f_dc and f_res:
            wf_folds.append((fold_idx, f_res['n_strategy'], f_res['strategy_avg'], f_dc['z_paired']))
        else:
            wf_folds.append((fold_idx, 0, 0.0, 0.0))

    mean_z = sc['mean_z'] if sc else 0.0
    pass_r = sc['pass_rate'] * 100 if sc else 0.0
    ms_mean_z = ms_sc['mean_z'] if ms_sc else 0.0
    ms_pass_r = ms_sc['pass_rate'] * 100 if ms_sc else 0.0
    f4_z = wf_folds[-1][3] if wf_folds else 0.0
    f4_net = wf_folds[-1][2] if wf_folds else 0.0
    
    print(f"[{name:55s}] Tr={res['n_strategy']:3d} | Net={res['strategy_avg']:+5.2f}% | Edge={res['edge']:+5.2f}% | "
          f"StableZ={mean_z:+5.2f} ({pass_r:3.0f}%) | MS_Z={ms_mean_z:+5.2f} ({ms_pass_r:3.0f}%) | F4_z={f4_z:+5.2f}")
    return {
        'name': name, 'trades': res['n_strategy'], 'net': res['strategy_avg'], 'edge': res['edge'],
        'mean_z': mean_z, 'pass_rate': pass_r, 'ms_mean_z': ms_mean_z, 'wf_folds': wf_folds
    }

print("\n" + "="*125)
print("TESTING RSI VELOCITY & STRUCTURE TESTS")
print("="*125)

eval_strategy("1. RSI 3-Day Velocity Drop (>16pt drop, RSI<32)",
              lambda d: d['rsi_velocity_washout'], horizon=7)

eval_strategy("2. RSI 3-Day Velocity Drop in Mid/Small Caps",
              lambda d: d['rsi_vel_ms'], horizon=7)

eval_strategy("3. RSI 5-Day Velocity Drop (>22pt drop, RSI<32)",
              lambda d: d['rsi_5d_vel'], horizon=7)

eval_strategy("4. 200 SMA Touch & Green Rebound + Vol > 1.2x",
              lambda d: d['touch_200sma'], horizon=7)

eval_strategy("5. 3-Bar Bear Trap Below 50 SMA + Vol > 1.5x",
              lambda d: d['bear_trap_50sma'], horizon=7)
