"""Comprehensive engine backtest of Volume-Dryup Pullback swing strategies.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import numpy as np
import pandas as pd
from scipy import stats
from backtest_engine import simulate_trades, day_clustered_edge, stable_day_clustered_z, report, walk_forward_splits

print("Loading broad_nse_10y.pkl panel...")
with open("cache/broad_nse_10y.pkl", "rb") as f:
    d_obj = pickle.load(f)
panel = d_obj['data'] if isinstance(d_obj, dict) and '__meta__' in d_obj else d_obj

print(f"Panel contains {len(panel)} tickers.")

# Precompute cross-sectional features date by date
frames = []
for t, df in panel.items():
    if len(df) < 250:
        continue
    df = df.copy()
    df['ticker'] = t
    frames.append(df)

big = pd.concat(frames, ignore_index=True)
big = big.sort_values(['date', 'ticker']).reset_index(drop=True)

# Compute daily cross-sectional 60d Sharpe / 60d return and 52w high nearness
big['dist_high52w'] = big['close'] / big.groupby('ticker')['high'].transform(lambda x: x.rolling(250, min_periods=100).max()) - 1.0
big['ret60'] = big.groupby('ticker')['close'].transform(lambda x: x.pct_change(60) * 100)
big['ret3'] = big.groupby('ticker')['close'].transform(lambda x: x.pct_change(3) * 100)
big['ret1'] = big.groupby('ticker')['close'].transform(lambda x: x.pct_change(1) * 100)

# Vol ratio 1d: volume / 20d sma volume
big['vol_sma20'] = big.groupby('ticker')['volume'].transform(lambda x: x.rolling(20).mean())
big['vol_ratio1'] = big['volume'] / big['vol_sma20']

# 60d Sharpe
def roll_sharpe(s):
    r = s.pct_change()
    return r.rolling(60).mean() / r.rolling(60).std() * np.sqrt(252)

big['sharpe60'] = big.groupby('ticker')['close'].transform(roll_sharpe)

NIFTY50_APPROX = set(big.groupby('ticker')['turnover_60d'].max().nlargest(50).index)
big['is_liquid_midsmall'] = (big['turnover_60d'] >= 25e7) & (~big['ticker'].isin(NIFTY50_APPROX))

# Groupby date rank
big['sharpe60_rank'] = big.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))
big['dist_high52w_rank'] = big.groupby('date')['dist_high52w'].transform(lambda x: x.rank(pct=True))
big['comp_score'] = (big['sharpe60_rank'] + big['dist_high52w_rank']) / 2.0
big['comp_rank'] = big.groupby('date')['comp_score'].transform(lambda x: x.rank(pct=True))

print("Features computed. Re-splitting panel into ticker dict...")
panel_feat = {t: grp.reset_index(drop=True) for t, grp in big.groupby('ticker')}

def test_engine_strategy(name, signal_func, horizon=8, stop_atr=2.0, target_atr=2.0, exit_rsi=None):
    print(f"\n=======================================================")
    print(f"Testing Candidate: {name} (horizon={horizon})")
    print(f"=======================================================")
    
    rng = np.random.default_rng(42)
    strat_trades, ctrl_trades = [], []
    
    per_ticker_sig = {}
    per_ticker_liq = {}
    
    for t, df in panel_feat.items():
        if len(df) < 300:
            continue
        liq = df['is_liquid_midsmall'].fillna(False).values
        sig = signal_func(df) & liq
        per_ticker_sig[t] = sig
        per_ticker_liq[t] = liq
        
        st = simulate_trades(df, sig, horizon_days=horizon, stop_atr_mult=stop_atr, 
                             target_atr_mult=target_atr, exit_rsi=exit_rsi, 
                             charge_costs=True, allow_overlap=False)
        strat_trades += st
        
        ctrl_mask = (rng.random(len(df)) < 0.10) & liq
        ct = simulate_trades(df, ctrl_mask, horizon_days=horizon, stop_atr_mult=stop_atr, 
                             target_atr_mult=target_atr, exit_rsi=exit_rsi, 
                             charge_costs=True, allow_overlap=False)
        ctrl_trades += ct
        
    print(report(name, strat_trades, ctrl_trades, holding_days=horizon))
    
    def ctrl_factory(seed):
        r = np.random.default_rng(seed)
        c_trades = []
        for t, df in panel_feat.items():
            if t not in per_ticker_liq:
                continue
            liq = per_ticker_liq[t]
            ctrl_mask = (r.random(len(df)) < 0.10) & liq
            c_trades += simulate_trades(df, ctrl_mask, horizon_days=horizon, stop_atr_mult=stop_atr, 
                                        target_atr_mult=target_atr, exit_rsi=exit_rsi, 
                                        charge_costs=True, allow_overlap=False)
        return c_trades

    stable = stable_day_clustered_z(strat_trades, ctrl_factory, n_seeds=20)
    print(f"Stable Control (20 seeds): Mean z_paired = {stable['mean_z']:.2f} (min {stable['min_z']:.2f}, max {stable['max_z']:.2f}), Pass Rate = {stable['pass_rate']*100:.1f}%")
    return strat_trades, ctrl_trades, stable

# Candidate 1: Volume Dry-Up Pullback in Quality 60d Trend
def sig_c1(df):
    return (df['sharpe60_rank'] >= 0.85) & (df['ret3'] < -1.0) & (df['vol_ratio1'] < 0.70) & (df['close'] > df['sma_50'])

# Candidate 2: Volume Dry-Up Pullback in Composite 52w+Sharpe Leaders
def sig_c2(df):
    return (df['comp_rank'] >= 0.85) & (df['ret3'] < -1.0) & (df['vol_ratio1'] < 0.70) & (df['close'] > df['sma_50'])

# Candidate 3: Volume Dry-Up Pullback in 52w High Leaders (<8% from 52w high)
def sig_c3(df):
    return (df['dist_high52w'] > -0.08) & (df['ret3'] < -1.0) & (df['vol_ratio1'] < 0.70) & (df['close'] > df['sma_50'])

test_engine_strategy("C1: Sharpe60 Top15% + 3d Pullback + Vol Dryup (<0.7) > SMA50", sig_c1, horizon=8)
test_engine_strategy("C2: Composite Top15% + 3d Pullback + Vol Dryup (<0.7) > SMA50", sig_c2, horizon=8)
test_engine_strategy("C3: 52w High Nearness (<8%) + 3d Pullback + Vol Dryup (<0.7) > SMA50", sig_c3, horizon=8)
