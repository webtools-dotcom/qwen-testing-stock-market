"""Comprehensive Alpha Hunt for Solid Verdict Pass Strategy in NSE/BSE (2016-2026).
Screens 20 distinct structural hypotheses against all mandatory METHODOLOGY.md hurdles.
"""
import sys, os
sys.path.insert(0, '.')
import pickle
import numpy as np
import pandas as pd

print("Loading master dataset...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

# Liquid mid/small cap universe (>= 25 cr turnover)
df['is_liquid_midsmall'] = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
d = df[df['is_liquid_midsmall']].copy().reset_index(drop=True)

# Build forward returns for h = 21, 30, 42
for h in [21, 30, 42]:
    if f'fwd{h}' not in d.columns:
        d[f'fwd{h}'] = d.groupby('ticker')['close'].pct_change(h).shift(-h) * 100
    if f'fwd{h}_dm' not in d.columns:
        d[f'fwd{h}_dm'] = d[f'fwd{h}'] - d.groupby('date')[f'fwd{h}'].transform('mean')

# Pre-compute core features
d['dist_high52w'] = d['dist_high250']
d['near_52w_high'] = d['dist_high52w'] >= -0.05 # within 5% of 52w high

d['ret20_rank'] = d.groupby('date')['ret20'].transform(lambda x: x.rank(pct=True))
d['ret60_rank'] = d.groupby('date')['ret60'].transform(lambda x: x.rank(pct=True))
d['ret120_rank'] = d.groupby('date')['ret120'].transform(lambda x: x.rank(pct=True))
d['change_252d_rank'] = d.groupby('date')['change_252d'].transform(lambda x: x.rank(pct=True))
d['sharpe60_rank'] = d.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))

# 1. 252-day t-statistic (Trend Consistency)
d['ret1_std252'] = d.groupby('ticker')['ret1'].transform(lambda x: x.rolling(252).std())
d['ret1_mean252'] = d.groupby('ticker')['ret1'].transform(lambda x: x.rolling(252).mean())
d['t_stat_252'] = (d['ret1_mean252'] / (d['ret1_std252'] + 1e-6)) * np.sqrt(252)
d['t_stat_252_rank'] = d.groupby('date')['t_stat_252'].transform(lambda x: x.rank(pct=True))

# 2. 252-day Calmar Ratio (Ret252 / Max Drawdown over 252d)
def rolling_max_dd(series, window=252):
    # compute rolling max drawdown
    roll_max = series.rolling(window, min_periods=window//2).max()
    dd = (series / roll_max - 1.0)
    min_dd = dd.rolling(window, min_periods=window//2).min()
    return min_dd.abs()

d['rolling_dd252'] = d.groupby('ticker')['close'].transform(rolling_max_dd)
d['calmar252'] = d['change_252d'] / (d['rolling_dd252'] * 100 + 1e-4)
d['calmar252_rank'] = d.groupby('date')['calmar252'].transform(lambda x: x.rank(pct=True))

# 3. Dual Acceleration: Ret60 rank minus Ret252 rank (Momentum accelerating in last quarter)
d['mom_accel'] = d['ret60_rank'] - d['change_252d_rank']
d['mom_accel_rank'] = d.groupby('date')['mom_accel'].transform(lambda x: x.rank(pct=True))

# 4. Volatility Contraction at All-Time Highs: BB Bandwidth lowest 30% + Dist 52w >= -5%
d['vol_squeeze_52w'] = (d['bb_bw_rank'] <= 0.30) & (d['dist_high52w'] >= -0.05)

# 5. Market Regime Filter: % of liquid mid/small caps above 50 SMA
d['above_sma50'] = d['close'] > d['sma_50']
breadth = d.groupby('date')['above_sma50'].mean()
d['mkt_breadth'] = d['date'].map(breadth)
d['bull_market'] = d['mkt_breadth'] >= 0.50

# 6. Moving Average Ribbon Alignment: Close > SMA20 > SMA50 > SMA200
d['ma_ribbon'] = (d['close'] > d['sma_20']) & (d['sma_20'] > d['sma_50']) & (d['sma_50'] > d['sma_200'])

# 7. Amihud Illiquidity Ratio (Float Scarcity): Ret1_abs / Volume
d['float_scarcity'] = d['amihud_z'] # precomputed Amihud illiquidity z-score
d['float_scarcity_rank'] = d.groupby('date')['float_scarcity'].transform(lambda x: x.rank(pct=True))

# 8. Multi-Factor Composites:
# Composite A: Calmar252 + 52w High Proximity (Low Drawdown Trend Compounders)
d['comp_calmar_52w'] = 0.5 * d['calmar252_rank'] + 0.5 * (1.0 + d['dist_high52w'])
d['comp_calmar_52w_rank'] = d.groupby('date')['comp_calmar_52w'].transform(lambda x: x.rank(pct=True))

# Composite B: Sharpe60 + 52w High Proximity + MA Ribbon
d['comp_sharpe_52w'] = 0.5 * d['sharpe60_rank'] + 0.5 * (1.0 + d['dist_high52w'])
d['comp_sharpe_52w_rank'] = d.groupby('date')['comp_sharpe_52w'].transform(lambda x: x.rank(pct=True))

# Composite C: Mom 12-1 + Trend Consistency (t_stat_252) + 52w High Proximity
d['mom_12_1'] = d['change_252d'] - d['ret20']
d['mom_12_1_rank'] = d.groupby('date')['mom_12_1'].transform(lambda x: x.rank(pct=True))
d['comp_tri_factor'] = (1/3.0)*d['mom_12_1_rank'] + (1/3.0)*d['t_stat_252_rank'] + (1/3.0)*(1.0 + d['dist_high52w'])
d['comp_tri_factor_rank'] = d.groupby('date')['comp_tri_factor'].transform(lambda x: x.rank(pct=True))

pre2017_set = set(df[df['date'] <= '2017-01-01']['ticker'].unique())

print(f"Features ready. Testing candidate universe across 10 years...")

def screen_candidate(name, cond, h=30):
    dm_col = f'fwd{h}_dm'
    raw_col = f'fwd{h}'
    sub = d[cond & d[dm_col].notna()].copy()
    if len(sub) < 100:
        return None
    daily = sub.groupby('date')[dm_col].mean()
    if len(daily) < 50:
        return None
        
    edge = daily.mean()
    se = daily.std(ddof=1) / np.sqrt(len(daily))
    t_stat = edge / se if se > 0 else 0
    raw_ret = sub[raw_col].mean()
    net_ret = raw_ret - 0.50
    
    hA = sub[sub['half'] == 'A'].groupby('date')[dm_col].mean()
    hB = sub[sub['half'] == 'B'].groupby('date')[dm_col].mean()
    t_A = hA.mean() / (hA.std(ddof=1) / np.sqrt(len(hA))) if len(hA)>5 and hA.std(ddof=1)>0 else 0
    t_B = hB.mean() / (hB.std(ddof=1) / np.sqrt(len(hB))) if len(hB)>5 and hB.std(ddof=1)>0 else 0
    
    pre = sub[sub['ticker'].isin(pre2017_set)].groupby('date')[dm_col].mean()
    t_pre = pre.mean() / (pre.std(ddof=1) / np.sqrt(len(pre))) if len(pre)>5 and pre.std(ddof=1)>0 else 0
    edge_pre = pre.mean()
    
    p1 = sub[sub['period'] == 'P1'].groupby('date')[dm_col].mean()
    p2 = sub[sub['period'] == 'P2'].groupby('date')[dm_col].mean()
    p3 = sub[sub['period'] == 'P3'].groupby('date')[dm_col].mean()
    t_p1 = p1.mean() / (p1.std(ddof=1) / np.sqrt(len(p1))) if len(p1)>5 and p1.std(ddof=1)>0 else 0
    t_p2 = p2.mean() / (p2.std(ddof=1) / np.sqrt(len(p2))) if len(p2)>5 and p2.std(ddof=1)>0 else 0
    t_p3 = p3.mean() / (p3.std(ddof=1) / np.sqrt(len(p3))) if len(p3)>5 and p3.std(ddof=1)>0 else 0
    
    # Check if candidate passes ALL hurdle thresholds:
    # 1. t_stat >= 3.0
    # 2. t_A >= 2.0 and t_B >= 2.0
    # 3. t_pre >= 2.0 and edge_pre >= 0.60 * edge
    # 4. t_p1 > 0, t_p2 > 0, t_p3 > 0
    passes_all = (
        (t_stat >= 3.0) and 
        (t_A >= 2.0) and 
        (t_B >= 2.0) and 
        (t_pre >= 2.0) and 
        (edge_pre >= 0.60 * edge) and 
        (t_p1 > 0) and (t_p2 > 0) and (t_p3 > 0) and
        (net_ret >= 2.5)
    )
    
    return {
        'name': name,
        'h': h,
        'trades': len(sub),
        'days': len(daily),
        'raw%': raw_ret,
        'net%': net_ret,
        'day_edge%': edge,
        't_stat': t_stat,
        't_A': t_A, 't_B': t_B,
        't_pre2017': t_pre,
        'pre_ratio': edge_pre / (edge + 1e-6),
        't_P1': t_p1, 't_P2': t_p2, 't_P3': t_p3,
        'PASS': 'PASS' if passes_all else 'FAIL'
    }

cands = []

for h_cand in [21, 30, 42]:
    # Candidate 1: Calmar252 Top Decile + 52w High Proximity (> SMA50)
    c1 = (d['comp_calmar_52w_rank'] >= 0.90) & (d['close'] > d['sma_50'])
    cands.append(screen_candidate("Calmar252 + 52w Proximity Top Decile", c1, h=h_cand))
    
    # Candidate 2: Calmar252 Top 10% + MA Ribbon Alignment (20 > 50 > 200 SMA)
    c2 = (d['calmar252_rank'] >= 0.90) & d['ma_ribbon']
    cands.append(screen_candidate("Calmar252 Top 10% in Full MA Ribbon Alignment", c2, h=h_cand))
    
    # Candidate 3: Tri-Factor Composite (12-1 Mom + 252d t-stat + 52w Proximity) Top Decile
    c3 = (d['comp_tri_factor_rank'] >= 0.90) & (d['close'] > d['sma_50'])
    cands.append(screen_candidate("Tri-Factor (12-1 Mom + t-stat252 + 52w) Top Decile", c3, h=h_cand))
    
    # Candidate 4: Tri-Factor Composite with Bull Market Breadth Filter (Breadth >= 50%)
    c4 = (d['comp_tri_factor_rank'] >= 0.90) & (d['close'] > d['sma_50']) & d['bull_market']
    cands.append(screen_candidate("Tri-Factor Composite with Bull Market Breadth Filter", c4, h=h_cand))
    
    # Candidate 5: Sharpe60 + 52w Proximity Top Decile (> SMA50)
    c5 = (d['comp_sharpe_52w_rank'] >= 0.90) & (d['close'] > d['sma_50'])
    cands.append(screen_candidate("Sharpe60 + 52w Proximity Top Decile", c5, h=h_cand))
    
    # Candidate 6: Momentum Acceleration (Ret60 vs Ret252) + 52w Proximity + Float Scarcity
    c6 = (d['mom_accel_rank'] >= 0.85) & (d['dist_high52w'] >= -0.05) & (d['float_scarcity_rank'] >= 0.60) & (d['close'] > d['sma_50'])
    cands.append(screen_candidate("Momentum Acceleration + 52w High + Float Scarcity", c6, h=h_cand))
    
    # Candidate 7: 252-day t-statistic (Trend Consistency) Top 10% + Volatility Contraction at 52w High
    c7 = (d['t_stat_252_rank'] >= 0.90) & d['vol_squeeze_52w'] & (d['close'] > d['sma_50'])
    cands.append(screen_candidate("Trend Consistency t_stat252 + Vol Squeeze at 52w High", c7, h=h_cand))

res_df = pd.DataFrame([c for c in cands if c is not None])
print("\n" + "="*110)
print("COMPREHENSIVE ALPHA HUNT SCREENING RESULTS")
print("="*110)
print(res_df.to_string(index=False))

# Filter for all candidates with PASS status or top t-statistics
passes = res_df[res_df['PASS'] == 'PASS']
print(f"\nTotal Candidates tested: {len(res_df)} | Total Clean PASSES: {len(passes)}")
if len(passes) > 0:
    print(passes.to_string(index=False))
