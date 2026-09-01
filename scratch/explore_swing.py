"""Explore high-alpha swing mechanisms (6-10 day horizon) in NSE mid/small caps.
"""
import pickle
import numpy as np
import pandas as pd
from scipy import stats

print("Loading _master_flat.pkl...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

mask_liq = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
d = df[mask_liq].copy().reset_index(drop=True)

# Engineer features
d['dist_high52w'] = d['dist_high250']
d['sharpe60_rank'] = d.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))
d['ret60_rank'] = d.groupby('date')['ret60'].transform(lambda x: x.rank(pct=True))
d['turnover_z_rank'] = d.groupby('date')['turnover_z'].transform(lambda x: x.rank(pct=True))
d['amihud_z_rank'] = d.groupby('date')['amihud_z'].transform(lambda x: x.rank(pct=True))
d['dist_high52w_rank'] = d.groupby('date')['dist_high52w'].transform(lambda x: x.rank(pct=True))
d['composite_52w_sharpe'] = (d['dist_high52w_rank'] + d['sharpe60_rank']) / 2.0
d['composite_rank'] = d.groupby('date')['composite_52w_sharpe'].transform(lambda x: x.rank(pct=True))

def test_signal(name, cond, horizon=8):
    target_col = f'fwd{horizon}_dm'
    raw_col = f'fwd{horizon}'
    sub = d[cond & d[target_col].notna()].copy()
    if len(sub) < 50:
        return None
    daily = sub.groupby('date')[target_col].mean()
    if len(daily) < 15:
        return None
    edge = daily.mean()
    se = daily.std(ddof=1) / np.sqrt(len(daily))
    t_stat = edge / se if se > 0 else 0
    raw_ret = sub[raw_col].mean()
    
    # Subgroups
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
    
    return {
        'name': name,
        'trades': len(sub),
        'days': len(daily),
        'day_edge': edge,
        't_stat': t_stat,
        't_A': t_A, 't_B': t_B,
        't_P1': t_p1, 't_P2': t_p2, 't_P3': t_p3,
        'raw_fwd': raw_ret
    }

print("Running hypothesis scan...")
runs = []

# H1: Quality Trend + 3-day pullback into support (Sharpe60 top 15% + ret3 < -2% + close > sma50)
c1 = (d['sharpe60_rank'] >= 0.85) & (d['ret3'] < -2.0) & (d['close'] > d['sma_50'])
runs.append(test_signal('Sharpe60 Top15% + 3d Pullback (<-2%) > SMA50', c1))

# H2: Quality Trend + 3-day pullback with volume dry-up (Sharpe60 top 15% + ret3 < -1% + vol_ratio1 < 0.7)
c2 = (d['sharpe60_rank'] >= 0.85) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.7) & (d['close'] > d['sma_50'])
runs.append(test_signal('Sharpe60 Top15% + Pullback + Vol Dryup (vol_ratio < 0.7)', c2))

# H3: Quality Trend + Inside Day / Tight Range (Sharpe60 top 15% + bb_bw_rank < 0.15 + ret1 > 0)
c3 = (d['sharpe60_rank'] >= 0.85) & (d['bb_bw_rank'] < 0.15) & (d['ret1'] > 0)
runs.append(test_signal('Sharpe60 Top15% + Tight Squeeze (BW rank < 0.15) + Green Day', c3))

# H4: 52-Week High Nearness + High Volume Pocket Pivot (dist_high52w > -0.05 + ret1 > 2% + turnover_z > 1.5)
c4 = (d['dist_high52w'] > -0.05) & (d['ret1'] > 2.0) & (d['turnover_z'] > 1.5)
runs.append(test_signal('Near 52w High (within 5%) + 2% Pop + Turnover_Z > 1.5', c4))

# H5: Dual Sharpe Momentum: Sharpe60 top 10% + 52w High Nearness (top 10%)
c5 = (d['sharpe60_rank'] >= 0.90) & (d['dist_high52w'] > -0.05)
runs.append(test_signal('Sharpe60 Top10% + 52w High Nearness (<5% from high)', c5))

# H6: Stealth Institutional Accumulation: Amihud drop (top liquidity inflow) + Price Tightness (ret5 between -1% and +2%) + Sharpe60 > 70%
c6 = (d['amihud_z'] < -1.5) & (d['ret5'].between(-1.0, 2.0)) & (d['sharpe60_rank'] >= 0.70)
runs.append(test_signal('Stealth Accumulation (Amihud z<-1.5 + 5d Tightness + Sharpe60>70%)', c6))

# H7: Intraday Institutional Accumulation: co_ret > 1.5% with high turnover + in uptrend (close > sma200 & sharpe60 > 0.8)
c7 = (d['co_ret'] > 1.5) & (d['turnover_z'] > 1.5) & (d['sharpe60_rank'] >= 0.80) & (d['close'] > d['sma_200'])
runs.append(test_signal('Intraday Thrust (CO > 1.5% + Turn_Z > 1.5 + Sharpe60 > 80%)', c7))

# H8: Momentum Breakout from Multi-Week Base: 20-day High + Sharpe60 > 80% + Vol Surge
c8 = (d['close'] >= d['high20']) & (d['sharpe60_rank'] >= 0.80) & (d['vol_ratio1'] > 1.5)
runs.append(test_signal('20d High Breakout + Sharpe60 > 80% + Vol_Ratio > 1.5', c8))

# H9: Relative Strength Gap: Stock at 20-day high while market (Nifty) is below its 20-day high + Sharpe60 > 80%
c9 = (d['close'] >= d['high20']) & (d['mkt20'] < 0) & (d['sharpe60_rank'] >= 0.80)
runs.append(test_signal('Idiosyncratic 20d High in Weak Market (Mkt20 < 0) + Sharpe60 > 80%', c9))

# H10: Low Beta Compounder Thrust: Beta < 0.8 + Sharpe60 > 90% + ret1 > 1.0%
c10 = (d['beta'] < 0.8) & (d['sharpe60_rank'] >= 0.90) & (d['ret1'] > 1.0)
runs.append(test_signal('Low-Beta Compounder Thrust (Beta < 0.8 + Sharpe60 Top10% + Green)', c10))

# H11: Pure 52-Week High Nearness Top Decile at 8-day hold
c11 = d['dist_high52w_rank'] >= 0.90
runs.append(test_signal('52-Week High Nearness Top Decile (h=8)', c11))

# H12: Composite 52w High Nearness + Sharpe60 Top Decile at 8-day hold
c12 = d['composite_rank'] >= 0.90
runs.append(test_signal('Composite (52w High + Sharpe60) Top Decile (h=8)', c12))

# H13: Composite Top 5% at 8-day hold
c13 = d['composite_rank'] >= 0.95
runs.append(test_signal('Composite (52w High + Sharpe60) Top 5% (h=8)', c13))

# H14: Composite Top Decile + Volume Squeeze Expansion
c14 = (d['composite_rank'] >= 0.90) & (d['vol_ratio1'] > 1.5) & (d['ret1'] > 1.0)
runs.append(test_signal('Composite Top10% + Vol Expansion (>1.5) + Ret1>1%', c14))

# H15: Composite Top Decile + Pullback to 10 EMA / Support (ret3 between -1.5% and -5%)
c15 = (d['composite_rank'] >= 0.90) & (d['ret3'].between(-5.0, -1.5)) & (d['close'] > d['sma_50'])
runs.append(test_signal('Composite Top10% + Pullback (-5% to -1.5%) > SMA50', c15))

res_df = pd.DataFrame([r for r in runs if r is not None])
print(res_df.to_string(index=False))
