"""Comprehensive Multi-Horizon Alpha Lab (h=10 to 42 sessions).
Searches for robust structural anomalies that pass §8 Subgroup, Holdout Half B, Pre-2017 Survivorship,
Walk-forward folds, and the Portfolio Tool Test at 1.5x costs.
"""
import pickle
import numpy as np
import pandas as pd

print("Loading dataset...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

# Liquid mid/small cap universe (>= 25 cr turnover)
df['is_liquid'] = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
d = df[df['is_liquid']].copy().reset_index(drop=True)

# Build forward returns for h = 10, 15, 20, 30, 42 if not already present
for h in [10, 15, 20, 30, 42]:
    if f'fwd{h}' not in d.columns:
        d[f'fwd{h}'] = d.groupby('ticker')['close'].pct_change(h).shift(-h) * 100
    if f'fwd{h}_dm' not in d.columns:
        d[f'fwd{h}_dm'] = d[f'fwd{h}'] - d.groupby('date')[f'fwd{h}'].transform('mean')

# Pre-compute cross-sectional features
d['dist_high52w'] = d['dist_high250']
d['sharpe60_rank'] = d.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))
d['ret60_rank'] = d.groupby('date')['ret60'].transform(lambda x: x.rank(pct=True))
d['ret120_rank'] = d.groupby('date')['ret120'].transform(lambda x: x.rank(pct=True))
d['change_252d_rank'] = d.groupby('date')['change_252d'].transform(lambda x: x.rank(pct=True))

# 12-month minus 1-month momentum (Jegadeesh & Titman 12-1 momentum)
# ret252 - ret20
d['mom_12_1'] = d['change_252d'] - d['ret20']
d['mom_12_1_rank'] = d.groupby('date')['mom_12_1'].transform(lambda x: x.rank(pct=True))

# Residual Momentum (Return minus Beta * Market Return)
d['idio_ret60'] = d['ret60'] - d['beta'] * d['mkt20'] * 3.0
d['idio_ret60_rank'] = d.groupby('date')['idio_ret60'].transform(lambda x: x.rank(pct=True))

# Trend Consistency (Information Ratio / Sharpe over 120 days)
# Mean daily ret / std daily ret over 120 days
d['ret1_std120'] = d.groupby('ticker')['ret1'].transform(lambda x: x.rolling(120).std())
d['ret1_mean120'] = d.groupby('ticker')['ret1'].transform(lambda x: x.rolling(120).mean())
d['trend_ir120'] = (d['ret1_mean120'] / (d['ret1_std120'] + 1e-6)) * np.sqrt(252)
d['trend_ir120_rank'] = d.groupby('date')['trend_ir120'].transform(lambda x: x.rank(pct=True))

# Proximity to 52w High + Trend Consistency Composite
d['composite_high_ir'] = 0.5 * (1.0 + d['dist_high52w']) + 0.5 * d['trend_ir120_rank']
d['composite_rank'] = d.groupby('date')['composite_high_ir'].transform(lambda x: x.rank(pct=True))

# Volatility Compression + High 52w Proximity
d['vol_compress'] = (d['bb_bw_rank'] < 0.25) & (d['dist_high52w'] >= -0.05)

pre2017_set = set(df[df['date'] <= '2017-01-01']['ticker'].unique())

print(f"Features ready across {len(d)} liquid mid/small rows. Evaluating candidates...")

def run_deep_test(name, cond, h=20):
    dm_col = f'fwd{h}_dm'
    raw_col = f'fwd{h}'
    sub = d[cond & d[dm_col].notna()].copy()
    if len(sub) < 50:
        return None
    daily = sub.groupby('date')[dm_col].mean()
    if len(daily) < 25:
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
    
    p1 = sub[sub['period'] == 'P1'].groupby('date')[dm_col].mean()
    p2 = sub[sub['period'] == 'P2'].groupby('date')[dm_col].mean()
    p3 = sub[sub['period'] == 'P3'].groupby('date')[dm_col].mean()
    t_p1 = p1.mean() / (p1.std(ddof=1) / np.sqrt(len(p1))) if len(p1)>5 and p1.std(ddof=1)>0 else 0
    t_p2 = p2.mean() / (p2.std(ddof=1) / np.sqrt(len(p2))) if len(p2)>5 and p2.std(ddof=1)>0 else 0
    t_p3 = p3.mean() / (p3.std(ddof=1) / np.sqrt(len(p3))) if len(p3)>5 and p3.std(ddof=1)>0 else 0
    
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
        't_P1': t_p1, 't_P2': t_p2, 't_P3': t_p3
    }

results = []

# Test Candidate Families across horizons:
for h_test in [15, 20, 30]:
    # 1. Residual Momentum Leader (Idiosyncratic Momentum Top 10% > SMA50 > SMA200)
    c1 = (d['idio_ret60_rank'] >= 0.90) & (d['close'] > d['sma_50']) & (d['sma_50'] > d['sma_200'])
    results.append(run_deep_test("Idiosyncratic Mom Top 10% in Bull Alignment", c1, h=h_test))
    
    # 2. 120d Trend Information Ratio Leaders (Top 10% Trend IR + Dist 52w >= -10%)
    c2 = (d['trend_ir120_rank'] >= 0.90) & (d['dist_high52w'] >= -0.10) & (d['close'] > d['sma_50'])
    results.append(run_deep_test("120d Trend IR Top 10% within 10% of 52w High", c2, h=h_test))
    
    # 3. 12-1 Momentum + Low Volatility Quality (Mom 12-1 Top 15% + Vol50 lowest 40%)
    vol50_rank = d.groupby('date')['vol50'].transform(lambda x: x.rank(pct=True))
    c3 = (d['mom_12_1_rank'] >= 0.85) & (vol50_rank <= 0.40) & (d['close'] > d['sma_50'])
    results.append(run_deep_test("12-1 Momentum in Low-Volatility Mid/Small Caps", c3, h=h_test))
    
    # 4. Composite (52w Proximity + 120d IR) Top Decile with Pullback Entry (Ret5 < 0)
    c4 = (d['composite_rank'] >= 0.90) & (d['ret5'] < 0.0) & (d['close'] > d['sma_50'])
    results.append(run_deep_test("Composite Leader 5-day Mild Pullback", c4, h=h_test))
    
    # 5. Volatility Squeeze in 52-Week High Trend Leaders (BB Squeeze + 52w High Proximity + Close > SMA50)
    c5 = d['vol_compress'] & (d['ret60_rank'] >= 0.80) & (d['close'] > d['sma_50'])
    results.append(run_deep_test("Volatility Squeeze Consolidation at 52w Highs", c5, h=h_test))

res_df = pd.DataFrame([r for r in results if r is not None])
print("\n--- Multi-Horizon Alpha Lab Results ---")
print(res_df.sort_values(by=['h', 't_stat'], ascending=[True, False]).to_string(index=False))
