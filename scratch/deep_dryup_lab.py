"""Deep exploration of Volume-Dryup Pullback in Quality Trend Leaders.
"""
import pickle
import numpy as np
import pandas as pd
from scipy import stats

print("Loading _master_flat.pkl...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

# Liquid mid/small caps
mask_liq = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
d = df[mask_liq].copy().reset_index(drop=True)

# Add custom features
d['dist_high52w'] = d['dist_high250']
d['sharpe60_rank'] = d.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))
d['dist_high52w_rank'] = d.groupby('date')['dist_high52w'].transform(lambda x: x.rank(pct=True))
d['comp_score'] = (d['dist_high52w_rank'] + d['sharpe60_rank']) / 2.0
d['composite_rank'] = d.groupby('date')['comp_score'].transform(lambda x: x.rank(pct=True))

d['vol_dryup_1d'] = d['vol_ratio1'] < 0.70
d['vol_dryup_2d'] = (d['vol_ratio1'] + d['vol_ratio3']) / 2.0 < 0.75
d['pullback_3d'] = d['ret3'] < -1.0
d['pullback_5d'] = d['ret5'] < -1.5
d['above_sma50'] = d['close'] > d['sma_50']
d['above_sma200'] = d['close'] > d['sma_200']

def run_tests(horizon=8):
    print(f"\n==================== Testing horizon={horizon} sessions ====================")
    results = []
    
    configs = [
        ("Sharpe60 Top15% + 3d PB (<-1%) + VolDryup (<0.7) > SMA50",
         (d['sharpe60_rank'] >= 0.85) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])),
         
        ("Sharpe60 Top15% + 3d PB (<-1.5%) + VolDryup (<0.7) > SMA50",
         (d['sharpe60_rank'] >= 0.85) & (d['ret3'] < -1.5) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])),
         
        ("Sharpe60 Top15% + 3d PB (<-2%) + VolDryup (<0.7) > SMA50",
         (d['sharpe60_rank'] >= 0.85) & (d['ret3'] < -2.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])),
         
        ("Sharpe60 Top15% + 3d PB (<-1%) + VolDryup (<0.6) > SMA50",
         (d['sharpe60_rank'] >= 0.85) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.60) & (d['close'] > d['sma_50'])),
         
        ("Sharpe60 Top15% + 3d PB (<-1%) + VolDryup (<0.8) > SMA50",
         (d['sharpe60_rank'] >= 0.85) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.80) & (d['close'] > d['sma_50'])),
         
        ("Sharpe60 Top10% + 3d PB (<-1%) + VolDryup (<0.7) > SMA50",
         (d['sharpe60_rank'] >= 0.90) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])),
         
        ("Sharpe60 Top20% + 3d PB (<-1%) + VolDryup (<0.7) > SMA50",
         (d['sharpe60_rank'] >= 0.80) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])),

        ("Composite (52w+Sharpe) Top15% + 3d PB (<-1%) + VolDryup (<0.7) > SMA50",
         (d['composite_rank'] >= 0.85) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])),

        ("Composite (52w+Sharpe) Top15% + 3d PB (<-1.5%) + VolDryup (<0.7) > SMA50",
         (d['composite_rank'] >= 0.85) & (d['ret3'] < -1.5) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])),

        ("Composite (52w+Sharpe) Top15% + 5d PB (<-2%) + VolDryup (<0.7) > SMA50",
         (d['composite_rank'] >= 0.85) & (d['ret5'] < -2.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])),

        ("Composite (52w+Sharpe) Top15% + 3d PB (<-1%) + VolDryup (<0.7) + Near SMA20 (±2%)",
         (d['composite_rank'] >= 0.85) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] >= d['sma_20']*0.98) & (d['close'] <= d['sma_20']*1.02)),

        ("52w High Nearness (<8%) + 3d PB (<-1%) + VolDryup (<0.7) > SMA50",
         (d['dist_high52w'] > -0.08) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])),

        ("52w High Nearness (<5%) + 3d PB (<-1%) + VolDryup (<0.7) > SMA50",
         (d['dist_high52w'] > -0.05) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])),
    ]
    
    target_col = f'fwd{horizon}_dm'
    raw_col = f'fwd{horizon}'
    
    for name, cond in configs:
        sub = d[cond & d[target_col].notna()].copy()
        if len(sub) < 50:
            continue
        daily = sub.groupby('date')[target_col].mean()
        if len(daily) < 15:
            continue
        edge = daily.mean()
        se = daily.std(ddof=1) / np.sqrt(len(daily))
        t_stat = edge / se if se > 0 else 0
        raw_ret = sub[raw_col].mean()
        
        hA = sub[sub['half'] == 'A'].groupby('date')[target_col].mean()
        hB = sub[sub['half'] == 'B'].groupby('date')[target_col].mean()
        t_A = hA.mean() / (hA.std(ddof=1) / np.sqrt(len(hA))) if len(hA) > 5 and hA.std(ddof=1)>0 else 0
        t_B = hB.mean() / (hB.std(ddof=1) / np.sqrt(len(hB))) if len(hB) > 5 and hB.std(ddof=1)>0 else 0
        
        p1 = sub[sub['period'] == 'P1'].groupby('date')[target_col].mean()
        p2 = sub[sub['period'] == 'P2'].groupby('date')[target_col].mean()
        p3 = sub[sub['period'] == 'P3'].groupby('date')[target_col].mean()
        t_p1 = p1.mean() / (p1.std(ddof=1) / np.sqrt(len(p1))) if len(p1) > 5 and p1.std(ddof=1)>0 else 0
        t_p2 = p2.mean() / (p2.std(ddof=1) / np.sqrt(len(p2))) if len(p2) > 5 and p2.std(ddof=1)>0 else 0
        t_p3 = p3.mean() / (p3.std(ddof=1) / np.sqrt(len(p3))) if len(p3) > 5 and p3.std(ddof=1)>0 else 0
        
        results.append({
            'name': name,
            'trades': len(sub),
            'days': len(daily),
            'day_edge': edge,
            't_stat': t_stat,
            't_A': t_A, 't_B': t_B,
            't_P1': t_p1, 't_P2': t_p2, 't_P3': t_p3,
            'raw_fwd': raw_ret
        })
    res_df = pd.DataFrame(results)
    print(res_df.to_string(index=False))

for h in [6, 8, 10]:
    run_tests(h)
