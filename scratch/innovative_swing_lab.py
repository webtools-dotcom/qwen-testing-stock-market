"""Innovative Swing Strategy Lab for NSE/BSE.
Tests hypotheses targeting > +2.0% net return per trade and portfolio CAGR > Buy & Hold.
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

# Build features
d['dist_high52w'] = d['dist_high250']
d['sharpe60_rank'] = d.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))
d['ret60_rank'] = d.groupby('date')['ret60'].transform(lambda x: x.rank(pct=True))
d['ret120_rank'] = d.groupby('date')['ret120'].transform(lambda x: x.rank(pct=True))

# Market regime: Nifty 50 above 50 SMA
mkt_regime = d.groupby('date')['mkt20'].mean() # surrogate or check mkt trend
# True market index trend
d['mkt_uptrend'] = d['mkt20'] > 0

# Relative strength vs market: 20d return - mkt20
d['rs20'] = d['ret20'] - d['mkt20']
d['rs20_rank'] = d.groupby('date')['rs20'].transform(lambda x: x.rank(pct=True))

# ATR percentage
d['atr_pct'] = d['atr'] / d['close'] * 100

# High-to-low range expansion relative to 10-day average range
d['hl_pct'] = (d['high'] - d['low']) / d['close'] * 100
d['hl_sma10'] = d.groupby('ticker')['hl_pct'].transform(lambda x: x.rolling(10).mean())
d['range_expansion'] = d['hl_pct'] / (d['hl_sma10'] + 1e-6)

# Volatility squeeze: BB Bandwidth Rank < 0.15
d['in_squeeze'] = d['bb_bw_rank'] < 0.20

# 52w High Proximity & Consolidation
d['near_52w'] = d['dist_high52w'] >= -0.10
d['dist_sma20'] = (d['close'] - d['sma_20']) / d['sma_20'] * 100
d['dist_sma50'] = (d['close'] - d['sma_50']) / d['sma_50'] * 100

print("Features built. Evaluating candidate hypotheses across horizons h=8, 10, 15...")

def eval_hypothesis(name, mask, h=10):
    raw_col = f'fwd{h}'
    dm_col = f'fwd{h}_dm'
    
    sub = d[mask & d[dm_col].notna()].copy()
    if len(sub) < 50:
        return None
        
    daily = sub.groupby('date')[dm_col].mean()
    if len(daily) < 20:
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
    
    pre2017 = sub[sub['ticker'].isin(set(df[df['date'] <= '2017-01-01']['ticker'].unique()))].groupby('date')[dm_col].mean()
    t_pre = pre2017.mean() / (pre2017.std(ddof=1) / np.sqrt(len(pre2017))) if len(pre2017)>5 and pre2017.std(ddof=1)>0 else 0
    
    p1 = sub[sub['period'] == 'P1'].groupby('date')[dm_col].mean()
    p2 = sub[sub['period'] == 'P2'].groupby('date')[dm_col].mean()
    p3 = sub[sub['period'] == 'P3'].groupby('date')[dm_col].mean()
    t_p1 = p1.mean() / (p1.std(ddof=1) / np.sqrt(len(p1))) if len(p1)>5 and p1.std(ddof=1)>0 else 0
    t_p2 = p2.mean() / (p2.std(ddof=1) / np.sqrt(len(p2))) if len(p2)>5 and p2.std(ddof=1)>0 else 0
    t_p3 = p3.mean() / (p3.std(ddof=1) / np.sqrt(len(p3))) if len(p3)>5 and p3.std(ddof=1)>0 else 0
    
    return {
        'name': name,
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

cands = []

# 1. Post-Squeeze Relative Strength Expansion in 52w Leaders:
# Stock in BB Squeeze (BW < 20%) within 8% of 52w high, today breaks out with ret1 > 2% and RS20 Top 15%
prev_squeeze = d.groupby('ticker')['in_squeeze'].shift(1).fillna(False)
h1 = prev_squeeze & (d['dist_high52w'] >= -0.08) & (d['ret1'] > 2.0) & (d['rs20_rank'] >= 0.85) & (d['vol_ratio1'] > 1.5)
cands.append(eval_hypothesis("Squeeze Expansion + RS20 D10 near 52w High", h1, h=10))

# 2. Institutional Momentum Consolidation Breakout (60d Momentum Top 10% + 5d Low-Vol Rest + 1d Thrust)
# 5d low vol rest: ret5 between -3% and +1%, today ret1 > 2.5% on vol_ratio > 2.0
h2 = (d['ret60_rank'] >= 0.90) & (d['ret5'].between(-3.0, 1.0)) & (d['ret1'] > 2.5) & (d['vol_ratio1'] > 2.0) & (d['close'] > d['sma_50'])
cands.append(eval_hypothesis("Mom60 D10 + 5d Flag Rest + 1d Volume Thrust (>2x Vol)", h2, h=10))

# 3. High Sharpe 120-Day Intermediate Trend Pullback to 20 SMA with Volume Dry-Up
# Ret120 Top 15% + Dist SMA20 between -2% and +1% + Vol Dry-Up < 0.65 + Close > SMA50
h3 = (d['ret120_rank'] >= 0.85) & (d['dist_sma20'].between(-2.0, 1.5)) & (d['vol_ratio1'] < 0.65) & (d['close'] > d['sma_50']) & (d['ret3'] < -0.5)
cands.append(eval_hypothesis("120d Trend Leader 20 SMA Pullback + Vol Dryup", h3, h=10))

# 4. Asymmetric Capitulation Reversal in Quality Uptrend (3-Day Flush + Low RSI + Hammer/Close in top 30% of daily bar)
# Close > SMA200, Ret3 < -4.0%, RSI < 35, Close near High of the day ((Close-Low)/(High-Low) > 0.70)
d['bar_loc'] = (d['close'] - d['low']) / (d['high'] - d['low'] + 1e-6)
h4 = (d['close'] > d['sma_200']) & (d['ret3'] < -4.0) & (d['rsi'] < 38) & (d['bar_loc'] >= 0.70) & (d['vol_ratio1'] > 1.3)
cands.append(eval_hypothesis("Quality Capitulation Hammer (Ret3<-4%, RSI<38, Close>70% Range > SMA200)", h4, h=8))

# 5. Dual-Momentum Trend Leader New Multi-Month High after Base Consolidation
# Stock breaks to new 60d high after 20d ATR consolidation, Sharpe60 Top 15%
prev_dist60 = d.groupby('ticker')['dist_high20'].shift(1) # surrogate
h5 = (d['sharpe60_rank'] >= 0.85) & (d['dist_high52w'] >= -0.05) & (d['ret20'].between(0.0, 6.0)) & (d['ret1'] > 2.0) & (d['vol_ratio1'] > 1.8)
cands.append(eval_hypothesis("Tight Base Breakout in Sharpe60 Leaders (20d tight base + 1d Vol Thrust)", h5, h=10))

# 6. Trend Pullback with Regime Filter (Market in Uptrend + Stock Sharpe60 D10 + 3d Pullback + Inside Bar)
# Inside bar: High <= Prev High and Low >= Prev Low
prev_high = d.groupby('ticker')['high'].shift(1)
prev_low = d.groupby('ticker')['low'].shift(1)
inside_bar = (d['high'] <= prev_high) & (d['low'] >= prev_low)
h6 = d['mkt_uptrend'] & (d['sharpe60_rank'] >= 0.90) & (d['ret3'] < -1.0) & inside_bar & (d['close'] > d['sma_50'])
cands.append(eval_hypothesis("Inside Bar Compression in Quality Leaders during Market Uptrend", h6, h=10))

# 7. 52-Week High Breakout Continuation with Multi-Day Volume Climax Support
# Within 2% of 52w high, Vol Ratio 3-day average > 2.0, Ret20 > 15%, Close > SMA20
h7 = (d['dist_high52w'] >= -0.02) & (d['vol_ratio3'] > 2.0) & (d['ret20'] > 15.0) & (d['close'] > d['sma_20'])
cands.append(eval_hypothesis("52w High Sustained Volume Surge (3d Vol>2x + Ret20>15%)", h7, h=10))

# 8. Post-Earnings / Massive Volume Gap Momentum Drift (Gap > 3% + Vol > 4x on day t-1 to t-3, now consolidating)
# Look for 1-3 days after a 4x volume surge
d['vol_surge_4x'] = (d['vol_ratio1'] > 4.0) & (d['ret1'] > 3.0)
vol_surge_past3 = d.groupby('ticker')['vol_surge_4x'].transform(lambda x: x.rolling(3).max().shift(1)).fillna(0).astype(bool)
h8 = vol_surge_past3 & (d['ret1'].between(-1.5, 1.5)) & (d['vol_ratio1'] < 1.0) & (d['close'] > d['sma_20'])
cands.append(eval_hypothesis("Post-Institutional Surge Flag Consolidation (Surge 4x vol within 3d + Low vol rest)", h8, h=10))

res_df = pd.DataFrame([c for c in cands if c is not None])
print("\n--- Innovative Swing Hypothesis Results ---")
print(res_df.to_string(index=False))
