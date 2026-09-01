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
    
    # Range / Volume
    d['vol_med_20'] = d['volume'].rolling(20).median()
    d['vol_ratio'] = d['volume'] / d['vol_med_20'].replace(0, np.nan)
    d['daily_ret'] = d['close'].pct_change() * 100
    d['roc_5'] = d['close'].pct_change(5) * 100
    d['roc_10'] = d['close'].pct_change(10) * 100
    d['roc_20'] = d['close'].pct_change(20) * 100
    
    # ATR stretch from 20 EMA
    d['ema_20'] = ta.trend.EMAIndicator(close=d['close'], window=20).ema_indicator()
    d['atr_stretch_20'] = (d['close'] - d['ema_20']) / d['atr']
    
    # 1. Top Momentum Leader Sharp 5d Pullback:
    # 60d momentum > 25%, Close > SMA200, 5-day drop < -7%, RSI < 38
    d['mom_leader_pullback'] = (d['momentum_60d'] > 20.0) & (d['roc_5'] < -6.0) & (d['rsi'] < 38) & (d['close'] > d['sma_200'])
    
    # 2. Top Momentum Leader 10d RoC Pullback:
    # 60d momentum > 25%, Close > SMA200, 10-day drop < -10%, RSI < 35
    d['mom_leader_roc10_pullback'] = (d['momentum_60d'] > 20.0) & (d['roc_10'] < -9.0) & (d['rsi'] < 35) & (d['close'] > d['sma_200'])
    
    # 3. Severe 3.0x ATR Downside Extension from 20 EMA:
    d['extreme_atr_stretch'] = (d['atr_stretch_20'] < -2.8) & (d['close'] > d['sma_200'])
    
    # 4. Post-Earnings / Massive Gap Continuation (Gap > 4%, Volume > 3x, next day entry hold 8 days):
    # Gap up: open > close[t-1] * 1.035, close > open, vol > 2.5x
    d['mega_gap_thrust'] = (d['open'] > d['close'].shift(1) * 1.03) & (d['close'] > d['open']) & (d['vol_ratio'] > 2.5) & (d['close'] > d['sma_200'])

    # 5. 3-Day Acceleration Downside Climax (Each day's drop bigger than previous: ret[t] < ret[t-1] < ret[t-2] < 0):
    d['accel_down'] = (d['daily_ret'] < d['daily_ret'].shift(1)) & (d['daily_ret'].shift(1) < d['daily_ret'].shift(2)) & (d['daily_ret'].shift(2) < 0) & (d['roc_5'] < -6.0) & (d['close'] > d['sma_200'])

    # 6. Bollinger Band Width Squeeze Breakout:
    bb = ta.volatility.BollingerBands(close=d['close'], window=20, window_dev=2)
    d['bb_width'] = (bb.bollinger_hband() - bb.bollinger_lband()) / d['close'] * 100
    d['bb_squeeze'] = d['bb_width'] < d['bb_width'].rolling(60).quantile(0.15)
    d['squeeze_breakout'] = d['bb_squeeze'].shift(1) & (d['close'] > bb.bollinger_hband()) & (d['vol_ratio'] > 2.0) & (d['close'] > d['sma_200'])

    d = d.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'momentum_60d', 'atr_stretch_20', 'turnover_60d']).reset_index(drop=True)
    if len(d) >= 300:
        processed[ticker] = d

print(f"Loaded {len(processed)} stocks with deep setup features.")

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
print("TESTING DEEP SETUP HYPOTHESES")
print("="*125)

eval_strategy("1. Top Momentum Leader 5-day Drop (Mom60>20%, RoC5<-6%)",
              lambda d: d['mom_leader_pullback'], horizon=7)

eval_strategy("2. Top Momentum Leader 10-day Drop (Mom60>20%, RoC10<-9%)",
              lambda d: d['mom_leader_roc10_pullback'], horizon=7)

eval_strategy("3. Severe 2.8x ATR Downside Extension from 20 EMA",
              lambda d: d['extreme_atr_stretch'], horizon=7)

eval_strategy("4. Mega Gap-Up + Volume Thrust Continuation (8d hold)",
              lambda d: d['mega_gap_thrust'], horizon=8)

eval_strategy("5. 3-Day Downside Acceleration Climax (ret[t]<ret[t-1]<ret[t-2])",
              lambda d: d['accel_down'], horizon=7)

eval_strategy("6. Bollinger Band Squeeze Breakout + Volume > 2.0x",
              lambda d: d['squeeze_breakout'], horizon=7)
