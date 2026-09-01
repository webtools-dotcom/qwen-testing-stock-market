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
    d['range'] = d['high'] - d['low']
    d['range_med_20'] = d['range'].rolling(20).median()
    d['daily_ret'] = d['close'].pct_change() * 100
    
    # 1. Volume Dry-Up (VDU) after Thrust:
    # Thrust 2-4 days ago: daily_ret > 3%, vol_ratio > 2.0
    d['thrust'] = (d['daily_ret'] > 3.0) & (d['vol_ratio'] > 2.0) & (d['close'] > d['sma_200'])
    # Low volume pullback: volume < 0.7x 20d median for last 2 days
    d['vol_low_2d'] = (d['vol_ratio'] < 0.75) & (d['vol_ratio'].shift(1) < 0.75)
    d['pullback_holding'] = (d['close'] > d['close'].shift(3) * 0.98) # holding near thrust price
    d['vdu_pullback'] = d['thrust'].shift(2) & d['vol_low_2d'] & d['pullback_holding'] & (d['close'] > d['sma_200'])
    
    # 2. 50-day SMA False Breakdown Spring (Wyckoff Spring at 50 SMA in Uptrend):
    # Low < 50 SMA, but Close > 50 SMA, Close > Open, Volume > 1.3x median, SMA 50 > SMA 200
    d['spring_50sma'] = (d['low'] < d['sma_50']) & (d['close'] > d['sma_50']) & (d['close'] > d['open']) & (d['vol_ratio'] > 1.3) & (d['sma_50'] > d['sma_200']) & (d['close'] > d['sma_200'])
    
    # 3. Williams %R Extreme Oversold (< -90) in Macro Uptrend:
    # Williams %R over 14 bars
    hh_14 = d['high'].rolling(14).max()
    ll_14 = d['low'].rolling(14).min()
    d['williams_r'] = (hh_14 - d['close']) / (hh_14 - ll_14).replace(0, np.nan) * -100
    d['williams_oversold'] = (d['williams_r'] < -90.0) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200'])
    
    # 4. Stochastic RSI Oversold Reversal (%K crosses above %D from < 15):
    stoch_rsi = ta.momentum.StochRSIIndicator(close=d['close'], window=14, smooth1=3, smooth2=3)
    d['stoch_k'] = stoch_rsi.stochrsi_k() * 100
    d['stoch_d'] = stoch_rsi.stochrsi_d() * 100
    d['stoch_cross'] = (d['stoch_k'] > d['stoch_d']) & (d['stoch_k'].shift(1) <= d['stoch_d'].shift(1)) & (d['stoch_k'].shift(1) < 15.0) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200'])

    # 5. Chaikin Money Flow (CMF) Bullish Divergence at Oversold:
    cmf = ta.volume.ChaikinMoneyFlowIndicator(high=d['high'], low=d['low'], close=d['close'], volume=d['volume'], window=20)
    d['cmf'] = cmf.chaikin_money_flow()
    d['cmf_div'] = (d['rsi'] < 40) & (d['cmf'] > 0.08) & (d['close'] > d['sma_200']) & (d['close'] > d['open'])

    # 6. Narrow Range 7 (NR7) after 3-day Pullback to 20 EMA in Uptrend:
    d['nr7'] = d['range'] == d['range'].rolling(7).min()
    d['ema_20'] = ta.trend.EMAIndicator(close=d['close'], window=20).ema_indicator()
    d['nr7_ema20_pullback'] = d['nr7'] & (d['low'] <= 1.01 * d['ema_20']) & (d['close'] >= d['ema_20']) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200'])

    # 7. Consecutive 3-bar range contraction directly on 20 EMA:
    d['range_shrink_3d'] = (d['range'] < d['range'].shift(1)) & (d['range'].shift(1) < d['range'].shift(2))
    d['shrink_ema20'] = d['range_shrink_3d'] & (d['low'] <= 1.01 * d['ema_20']) & (d['close'] >= d['ema_20']) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200'])

    d = d.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'sma_50', 'williams_r', 'stoch_k', 'cmf', 'turnover_60d']).reset_index(drop=True)
    if len(d) >= 300:
        processed[ticker] = d

print(f"Loaded {len(processed)} stocks with structural swing indicators.")

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
        print(f"[{name:52s}] INSUFFICIENT TRADES (trades={len(strat)})")
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
    
    print(f"[{name:52s}] Tr={res['n_strategy']:3d} | Net={res['strategy_avg']:+5.2f}% | Edge={res['edge']:+5.2f}% | "
          f"StableZ={mean_z:+5.2f} ({pass_r:3.0f}%) | MS_Z={ms_mean_z:+5.2f} ({ms_pass_r:3.0f}%) | F4_z={f4_z:+5.2f}")
    return {
        'name': name, 'trades': res['n_strategy'], 'net': res['strategy_avg'], 'edge': res['edge'],
        'mean_z': mean_z, 'pass_rate': pass_r, 'ms_mean_z': ms_mean_z, 'wf_folds': wf_folds
    }

print("\n" + "="*120)
print("TESTING STRUCTURAL SWING HYPOTHESES")
print("="*120)

eval_strategy("1. Volume Dry-Up (VDU) after Thrust (7d)",
              lambda d: d['vdu_pullback'], horizon=7)

eval_strategy("2. Wyckoff 50-SMA Spring (Low<50SMA, Close>50SMA+Vol)",
              lambda d: d['spring_50sma'], horizon=7)

eval_strategy("3. Williams %R < -90 Oversold Washout in Uptrend",
              lambda d: d['williams_oversold'], horizon=7)

eval_strategy("4. StochRSI Bullish Cross (<15) in Uptrend",
              lambda d: d['stoch_cross'], horizon=7)

eval_strategy("5. CMF Bullish Inflow (>0.08) at RSI<40 in Uptrend",
              lambda d: d['cmf_div'], horizon=7)

eval_strategy("6. NR7 at 20 EMA Pullback in Uptrend",
              lambda d: d['nr7_ema20_pullback'], horizon=7)

eval_strategy("7. 3-Day Range Shrink directly at 20 EMA in Uptrend",
              lambda d: d['shrink_ema20'], horizon=7)
