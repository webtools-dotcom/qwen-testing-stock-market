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

# Load cached 88-stock panel (5-year)
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
    
    # 2, 3, 4 period RSI
    d['rsi_2'] = ta.momentum.RSIIndicator(close=d['close'], window=2).rsi()
    d['rsi_3'] = ta.momentum.RSIIndicator(close=d['close'], window=3).rsi()
    d['rsi_4'] = ta.momentum.RSIIndicator(close=d['close'], window=4).rsi()
    
    # 20-day low / high
    d['low_20'] = d['low'].rolling(20).min()
    d['low_20_prev'] = d['low_20'].shift(1)
    d['high_20'] = d['high'].rolling(20).max()
    d['high_20_prev'] = d['high_20'].shift(1)
    
    # 10-day low
    d['low_10_prev'] = d['low'].rolling(10).min().shift(1)
    
    # Consecutive Down Days
    d['down_day'] = d['close'] < d['close'].shift(1)
    down_count = np.zeros(len(d), dtype=int)
    c = 0
    for i in range(len(d)):
        if d['down_day'].iat[i]:
            c += 1
        else:
            c = 0
        down_count[i] = c
    d['consec_down'] = down_count
    
    # Bollinger Bands (20, 2.0)
    bb = ta.volatility.BollingerBands(close=d['close'], window=20, window_dev=2)
    d['bb_low'] = bb.bollinger_lband()
    d['bb_high'] = bb.bollinger_hband()
    d['bb_pct'] = (d['close'] - d['bb_low']) / (d['bb_high'] - d['bb_low']).replace(0, np.nan)
    
    # Keltner Channels (20, 2.0 ATR)
    d['kc_low'] = d['sma_20'] - 2.0 * d['atr']
    d['kc_high'] = d['sma_20'] + 2.0 * d['atr']
    
    # Distance to 20 EMA and 50 SMA
    d['dist_sma200'] = d['close'] / d['sma_200'] - 1
    d['dist_sma50'] = d['close'] / d['sma_50'] - 1
    
    # Volume metrics
    d['vol_med_20'] = d['volume'].rolling(20).median()
    d['vol_ratio'] = d['volume'] / d['vol_med_20'].replace(0, np.nan)
    
    # ADX(14)
    adx_ind = ta.trend.ADXIndicator(high=d['high'], low=d['low'], close=d['close'], window=14)
    d['adx'] = adx_ind.adx()
    d['di_pos'] = adx_ind.adx_pos()
    d['di_neg'] = adx_ind.adx_neg()

    d = d.dropna(subset=['rsi', 'rsi_2', 'atr', 'close', 'sma_200', 'sma_50', 'turnover_60d']).reset_index(drop=True)
    if len(d) >= 300:
        processed[ticker] = d

print(f"Loaded {len(processed)} stocks ({sum(1 for d in processed.values() if d['is_large_cap'].iat[0])} large, {sum(1 for d in processed.values() if not d['is_large_cap'].iat[0])} mid/small)")

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
        print(f"[{name:45s}] INSUFFICIENT TRADES (trades={len(strat)})")
        return None
    
    def ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for d in valid_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        return c_trades
    
    sc = stable_day_clustered_z(strat, ctrl_factory, n_seeds=20)
    
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
        
    ms_sc = stable_day_clustered_z(ms_strat, ms_ctrl_factory, n_seeds=20) if len(ms_strat) >= 10 else None
    
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
    
    print(f"[{name:48s}] Tr={res['n_strategy']:3d} | Net={res['strategy_avg']:+5.2f}% | Edge={res['edge']:+5.2f}% | "
          f"StableZ={mean_z:+5.2f} ({pass_r:3.0f}%) | MS_Z={ms_mean_z:+5.2f} ({ms_pass_r:3.0f}%) | F4_z={f4_z:+5.2f}")
    return {
        'name': name, 'trades': res['n_strategy'], 'net': res['strategy_avg'], 'edge': res['edge'],
        'mean_z': mean_z, 'pass_rate': pass_r, 'ms_mean_z': ms_mean_z, 'wf_folds': wf_folds
    }

print("\n" + "="*115)
print("EXPLORING CANDIDATE SWING STRATEGIES")
print("="*115)

# 1. 2-period RSI Extreme Oversold in Structural Uptrend (Connors RSI pullback)
eval_strategy("1. RSI(2) < 5 in 200 SMA Uptrend (7d)", 
              lambda d: (d['rsi_2'] < 5.0) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200']), horizon=7)

eval_strategy("1b. RSI(2) < 10 in 200 SMA Uptrend (7d)", 
              lambda d: (d['rsi_2'] < 10.0) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200']), horizon=7)

eval_strategy("1c. RSI(2) < 10 + Close < 5 SMA in Uptrend (7d)", 
              lambda d: (d['rsi_2'] < 10.0) & (d['close'] < d['close'].rolling(5).mean()) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200']), horizon=7)

# 2. Consecutive Down Days in Structural Uptrend
eval_strategy("2. 4 Consec Down Days in 200 SMA Uptrend", 
              lambda d: (d['consec_down'] >= 4) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200']), horizon=7)

eval_strategy("2b. 5 Consec Down Days in 200 SMA Uptrend", 
              lambda d: (d['consec_down'] >= 5) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200']), horizon=7)

# 3. Turtle Soup / False Breakdown Liquidity Sweep in Uptrend
eval_strategy("3. 20-day Low False Breakdown in Uptrend", 
              lambda d: (d['low'] < d['low_20_prev']) & (d['close'] > d['low_20_prev']) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200']), horizon=7)

eval_strategy("3b. 10-day Low False Breakdown in Uptrend", 
              lambda d: (d['low'] < d['low_10_prev']) & (d['close'] > d['low_10_prev']) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200']), horizon=7)

# 4. Bollinger Band %B < 0 (Close < Lower Band) in Uptrend
eval_strategy("4. BB %B < 0 (Close < Lower BB) in Uptrend", 
              lambda d: (d['close'] < d['bb_low']) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200']), horizon=7)

eval_strategy("4b. BB Lower Touch + Green Day in Uptrend", 
              lambda d: (d['low'] < d['bb_low']) & (d['close'] > d['open']) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200']), horizon=7)

# 5. Keltner Channel Lower Touch + Green Day
eval_strategy("5. Keltner Lower Touch + Close > Open in Uptrend", 
              lambda d: (d['low'] < d['kc_low']) & (d['close'] > d['open']) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200']), horizon=7)

# 6. ADX Strong Trend (>25, +DI > -DI) + Short Term Oversold (RSI_2 < 10)
eval_strategy("6. ADX > 25 Trend + RSI(2) < 10 Pullback", 
              lambda d: (d['adx'] > 25.0) & (d['di_pos'] > d['di_neg']) & (d['rsi_2'] < 10.0) & (d['close'] > d['sma_200']), horizon=7)

# 7. 3 Consec Down + Vol > 1.5x in Uptrend
eval_strategy("7. 3 Consec Down + Vol > 1.5x in Uptrend", 
              lambda d: (d['consec_down'] >= 3) & (d['vol_ratio'] > 1.5) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200']), horizon=7)
