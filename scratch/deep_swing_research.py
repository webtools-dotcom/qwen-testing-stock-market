"""Comprehensive swing trading hypothesis lab for NSE/BSE 6-10 day horizon.
"""
import pickle
import numpy as np
import pandas as pd
from scipy import stats

print("Loading _master_flat.pkl...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

print(f"Loaded {len(df)} rows across {df['ticker'].nunique()} tickers.")

mask_liq = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
d = df[mask_liq].copy().reset_index(drop=True)
print(f"Filtered to liquid mid/small caps: {len(d)} rows, {d['ticker'].nunique()} tickers, dates {d['date'].min()} to {d['date'].max()}")

# Helper for testing a boolean signal mask across regimes and name-halves
def eval_signal(name, sig_mask, target_col='fwd8_dm', raw_target='fwd8'):
    sub = d[sig_mask & d[target_col].notna()].copy()
    n_trades = len(sub)
    if n_trades < 100:
        return None
    
    # Paired daily edge
    daily = sub.groupby('date')[target_col].mean()
    n_days = len(daily)
    if n_days < 20:
        return None
    
    mean_edge = daily.mean()
    se = daily.std(ddof=1) / np.sqrt(n_days)
    t_stat = mean_edge / se if se > 0 else 0.0
    
    # Check half A vs half B
    half_A = sub[sub['half'] == 'A'].groupby('date')[target_col].mean()
    t_A = half_A.mean() / (half_A.std(ddof=1) / np.sqrt(len(half_A))) if len(half_A) > 10 else 0.0
    
    half_B = sub[sub['half'] == 'B'].groupby('date')[target_col].mean()
    t_B = half_B.mean() / (half_B.std(ddof=1) / np.sqrt(len(half_B))) if len(half_B) > 10 else 0.0
    
    # Check 3 periods
    p1 = sub[sub['period'] == 'P1'].groupby('date')[target_col].mean()
    p2 = sub[sub['period'] == 'P2'].groupby('date')[target_col].mean()
    p3 = sub[sub['period'] == 'P3'].groupby('date')[target_col].mean()
    
    t_p1 = p1.mean() / (p1.std(ddof=1) / np.sqrt(len(p1))) if len(p1) > 10 else 0.0
    t_p2 = p2.mean() / (p2.std(ddof=1) / np.sqrt(len(p2))) if len(p2) > 10 else 0.0
    t_p3 = p3.mean() / (p3.std(ddof=1) / np.sqrt(len(p3))) if len(p3) > 10 else 0.0
    
    raw_mean = sub[raw_target].mean()
    
    return {
        'name': name,
        'trades': n_trades,
        'days': n_days,
        'day_edge': mean_edge,
        't_stat': t_stat,
        't_A': t_A,
        't_B': t_B,
        't_P1': t_p1,
        't_P2': t_p2,
        't_P3': t_p3,
        'raw_fwd': raw_mean
    }

print("Testing signals...")
results = []

# 1. 20-day high breakout with turnover expansion
sig1 = (d['close'] >= d['high20']) & (d['turnover_z'] > 1.5)
r = eval_signal('20d High Breakout + Turn_Z > 1.5', sig1)
if r: results.append(r)

# 2. 10-day high breakout with low volume before, surge today
sig2 = (d['close'] >= d['high10']) & (d['vol_ratio1'] > 2.0)
r = eval_signal('10d High Breakout + Vol_Ratio1 > 2', sig2)
if r: results.append(r)

# 3. Bollinger Band squeeze expansion (bb_bw_rank < 0.20 and close > sma_20 and ret1 > 2%)
sig3 = (d['bb_bw_rank'] < 0.20) & (d['close'] > d['sma_20']) & (d['ret1'] > 2.0)
r = eval_signal('BB Squeeze Expansion (BW rank < 0.2, ret1 > 2%)', sig3)
if r: results.append(r)

# 4. Pullback in strong momentum: momentum_60d top quartile + rsi between 40 and 50
sig4 = (d['momentum_60d'] > d['momentum_60d'].quantile(0.75)) & (d['rsi'] >= 40) & (d['rsi'] <= 50) & (d['close'] > d['sma_50'])
r = eval_signal('Mom60 Top Q + RSI 40-50 Pullback > SMA50', sig4)
if r: results.append(r)

# 5. Consecutive down days in strong 252d trend: change_252d > 30% and dn_streak >= 3 and rsi < 40
sig5 = (d['change_252d'] > 30) & (d['dn_streak'] >= 3) & (d['rsi'] < 40) & (d['close'] > d['sma_200'])
r = eval_signal('252d Trend (>30%) + 3d Down Streak + RSI<40', sig5)
if r: results.append(r)

# 6. Low volatility high Sharpe trend: sharpe60 top decile
sig6 = d.groupby('date')['sharpe60'].transform(lambda x: x >= x.quantile(0.90))
r = eval_signal('Sharpe60 Top Decile', sig6)
if r: results.append(r)

# 7. Amihud drop (liquidity surge without price runaway): amihud_z < -1.5 and ret1 > 1.0 and ret1 < 5.0
sig7 = (d['amihud_z'] < -1.5) & (d['ret1'] > 1.0) & (d['ret1'] < 5.0) & (d['close'] > d['sma_50'])
r = eval_signal('Amihud Drop (z < -1.5) + Moderate Gain (1-5%) > SMA50', sig7)
if r: results.append(r)

# 8. Range position breakout: rng_pos > 0.90 with volume expansion
sig8 = (d['rng_pos'] > 0.90) & (d['vol_ratio1'] > 1.5) & (d['dist_high250'] > -0.10)
r = eval_signal('Rng_Pos > 0.90 + Vol_Ratio > 1.5 + Near 52w High (>-10%)', sig8)
if r: results.append(r)

# 9. Idiosyncratic strength: resid5 > 5% and beta < 1.2
sig9 = (d['resid5'] > 5.0) & (d['beta'] < 1.2) & (d['close'] > d['sma_50'])
r = eval_signal('Idiosyncratic 5d Residual > 5% (Beta < 1.2)', sig9)
if r: results.append(r)

# 10. Gap and go: gap > 1.0% and close > open and turnover_z > 1.0
sig10 = (d['gap'] > 1.0) & (d['close'] > d['open']) & (d['turnover_z'] > 1.0) & (d['close'] > d['sma_50'])
r = eval_signal('Gap > 1% + Green Bar + Turnover_Z > 1.0 > SMA50', sig10)
if r: results.append(r)

res_df = pd.DataFrame(results)
print(res_df.to_string(index=False))
