"""Hunt for Modern 2026 Passing Alpha in NSE/BSE.
Evaluates structural catalysts designed to produce strong edge in P1 (2016-2020), P2 (2021-2023), and P3 (2024-2026).
"""
import sys, os
sys.path.insert(0, '.')
import pickle
import numpy as np
import pandas as pd
from backtest_engine import simulate_trades, day_clustered_edge, stable_day_clustered_z

print("Loading dataset...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

# Liquid mid/small caps (turnover >= 25 cr)
df['is_liquid_midsmall'] = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
d = df[df['is_liquid_midsmall']].copy().reset_index(drop=True)

# Build forward returns for h = 10, 15, 20
for h in [10, 15, 20]:
    if f'fwd{h}' not in d.columns:
        d[f'fwd{h}'] = d.groupby('ticker')['close'].pct_change(h).shift(-h) * 100
    if f'fwd{h}_dm' not in d.columns:
        d[f'fwd{h}_dm'] = d[f'fwd{h}'] - d.groupby('date')[f'fwd{h}'].transform('mean')

# 1. 12-1 Momentum (Ret252 - Ret20)
d['mom_12_1'] = d['change_252d'] - d['ret20']
d['mom_12_1_rank'] = d.groupby('date')['mom_12_1'].transform(lambda x: x.rank(pct=True))

# 2. 60-day Momentum & Sharpe
d['ret60_rank'] = d.groupby('date')['ret60'].transform(lambda x: x.rank(pct=True))
d['sharpe60_rank'] = d.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))

# 3. Pullback features
d['ret3'] = (d['close'] - d.groupby('ticker')['close'].shift(3)) / d.groupby('ticker')['close'].shift(3) * 100
d['ret5'] = (d['close'] - d.groupby('ticker')['close'].shift(5)) / d.groupby('ticker')['close'].shift(5) * 100

# 4. Volume Climax Breakout: 1-day Volume > 3.0x 50d SMA + Ret1 > 3.0% + Close within 3% of 52w High
d['near_52w'] = d['dist_high250'] >= -0.03
d['vol_climax_breakout'] = (d['vol_ratio1'] >= 3.0) & (d['ret1'] >= 3.0) & d['near_52w'] & (d['close'] > d['sma_50'])

# 5. 12-1 Momentum + 5-day Dip Pullback: Mom 12-1 Top 15% + Ret5 < -3.0% + Close > SMA50
d['mom_dip_pullback'] = (d['mom_12_1_rank'] >= 0.85) & (d['ret5'] <= -3.0) & (d['close'] > d['sma_50'])

# 6. Relative Strength Expansion in Market Downturn: Ret20 > 5% while Mkt20 < -2%
d['mkt_down'] = d['mkt20'] < -2.0
d['rs_divergence'] = d['mkt_down'] & (d['ret20'] > 5.0) & (d['close'] > d['sma_50']) & (d['vol_ratio1'] > 1.2)

# 7. Low Volatility Consolidation Breakout: BB Bandwidth < 25% + Ret1 > 2.5% + Vol Ratio > 2.0 + Mom60 Top 20%
d['squeeze_thrust'] = (d['bb_bw_rank'] <= 0.25) & (d['ret1'] >= 2.5) & (d['vol_ratio1'] >= 2.0) & (d['ret60_rank'] >= 0.80) & (d['close'] > d['sma_50'])

# 8. Multi-Month Base Breakout with Volume Surge: Dist High20 == 0 (new 20d high) + Dist High250 >= -0.05 + Vol > 2.5x
prev_high20 = d.groupby('ticker')['dist_high20'].shift(1)
d['new_20d_high'] = (d['dist_high20'] >= -0.001) & (prev_high20 < -0.01)
d['base_breakout'] = d['new_20d_high'] & (d['dist_high250'] >= -0.05) & (d['vol_ratio1'] >= 2.5) & (d['close'] > d['sma_50'])

pre2017_set = set(df[df['date'] <= '2017-01-01']['ticker'].unique())

print("Testing candidate hypotheses across h=10, 15, 20...")

def eval_cand(name, mask_col, h=15):
    dm_col = f'fwd{h}_dm'
    raw_col = f'fwd{h}'
    sub = d[d[mask_col] & d[dm_col].notna()].copy()
    if len(sub) < 50: return None
    daily = sub.groupby('date')[dm_col].mean()
    if len(daily) < 25: return None
    
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
    
    p1 = sub[sub['period'] == 'P1'].groupby('date')[dm_col].mean()
    p2 = sub[sub['period'] == 'P2'].groupby('date')[dm_col].mean()
    p3 = sub[sub['period'] == 'P3'].groupby('date')[dm_col].mean()
    t_p1 = p1.mean() / (p1.std(ddof=1) / np.sqrt(len(p1))) if len(p1)>5 and p1.std(ddof=1)>0 else 0
    t_p2 = p2.mean() / (p2.std(ddof=1) / np.sqrt(len(p2))) if len(p2)>5 and p2.std(ddof=1)>0 else 0
    t_p3 = p3.mean() / (p3.std(ddof=1) / np.sqrt(len(p3))) if len(p3)>5 and p3.std(ddof=1)>0 else 0
    
    return {
        'name': name, 'h': h, 'trades': len(sub), 'days': len(daily),
        'net%': net_ret, 'day_edge%': edge, 't_stat': t_stat,
        't_A': t_A, 't_B': t_B, 't_pre': t_pre,
        't_P1': t_p1, 't_P2': t_p2, 't_P3': t_p3
    }

results = []
for h in [10, 15, 20]:
    results.append(eval_cand("Volume Climax Breakout at 52w High (>3x Vol)", 'vol_climax_breakout', h))
    results.append(eval_cand("12-1 Momentum + 5-day Dip Pullback (Ret5<-3%)", 'mom_dip_pullback', h))
    results.append(eval_cand("RS Divergence in Down Market (Ret20>5% vs Mkt<-2%)", 'rs_divergence', h))
    results.append(eval_cand("Squeeze Volatility Expansion Thrust (>2x Vol)", 'squeeze_thrust', h))
    results.append(eval_cand("Base Breakout to New 20d High with Surge (>2.5x Vol)", 'base_breakout', h))

res_df = pd.DataFrame([r for r in results if r is not None])
print("\n" + "="*110)
print("MODERN 2026 ALPHA SCREENING RESULTS")
print("="*110)
print(res_df.to_string(index=False))
