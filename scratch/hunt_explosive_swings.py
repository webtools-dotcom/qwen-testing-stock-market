"""Explore explosive swing triggers (>2% net per 6-10 day trade).
"""
import pickle
import numpy as np
import pandas as pd

print("Loading _master_flat.pkl...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

mask_liq = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
d = df[mask_liq].copy().reset_index(drop=True)

# Engineer features
d['dist_high52w'] = d['dist_high250']
d['sharpe60_rank'] = d.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))
d['ret60_rank'] = d.groupby('date')['ret60'].transform(lambda x: x.rank(pct=True))
d['ret20_rank'] = d.groupby('date')['ret20'].transform(lambda x: x.rank(pct=True))

# Idiosyncratic daily move: ret1 - mkt1
d['idio_ret1'] = d['ret1'] - d['mkt1']
d['idio_ret3'] = d['ret3'] - d['mkt5']*0.6

# 52w high breakout today (dist_high52w >= -0.005 and prev dist_high52w < -0.02)
d['prev_dist_high52w'] = d.groupby('ticker')['dist_high52w'].shift(1)
d['new_52w_high'] = (d['dist_high52w'] >= -0.005) & (d['prev_dist_high52w'] < -0.02)

# 20d high breakout today
d['prev_dist_high20'] = d.groupby('ticker')['dist_high20'].shift(1)
d['new_20d_high'] = (d['dist_high20'] >= -0.005) & (d['prev_dist_high20'] < -0.02)

d['co_ret'] = (d['close'] - d['open']) / d['open'] * 100
d['hl_atr'] = (d['high'] - d['low']) / d['atr']

print(f"Dataset ready: {len(d)} rows.")

def test_cand(name, cond, h=8):
    target_col = f'fwd{h}_dm'
    raw_col = f'fwd{h}'
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
    net_ret = raw_ret - 0.50
    
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
        'raw_fwd%': raw_ret,
        'net_fwd%': net_ret,
        'day_edge%': edge,
        't_stat': t_stat,
        't_A': t_A, 't_B': t_B,
        't_P1': t_p1, 't_P2': t_p2, 't_P3': t_p3
    }

cands = []

# 1. Idiosyncratic 1-day thrust: idio_ret1 > 4% and mkt1 <= 0 and vol_ratio1 > 2.0 and close > sma50
c1 = (d['idio_ret1'] > 4.0) & (d['mkt1'] <= 0.0) & (d['vol_ratio1'] > 2.0) & (d['close'] > d['sma_50'])
cands.append(test_cand("Idiosyncratic 1d Thrust (>4% vs Mkt<=0) + Vol>2.0x > SMA50", c1))

# 2. Idiosyncratic 1-day thrust in Top Decile Momentum: idio_ret1 > 3% and ret60_rank > 0.85 and vol_ratio1 > 1.5
c2 = (d['idio_ret1'] > 3.0) & (d['ret60_rank'] >= 0.85) & (d['vol_ratio1'] > 1.5) & (d['close'] > d['sma_50'])
cands.append(test_cand("Idiosyncratic Thrust (>3%) in 60d Mom Top15% + Vol>1.5x", c2))

# 3. New 52-Week High Breakout on High Volume: new_52w_high & vol_ratio1 > 2.0 & ret1 > 2%
c3 = d['new_52w_high'] & (d['vol_ratio1'] > 2.0) & (d['ret1'] > 2.0)
cands.append(test_cand("Fresh 52w High Breakout + Vol>2.0x + Ret1>2%", c3))

# 4. New 52-Week High Breakout after 20-day Base: new_52w_high & sharpe60_rank > 0.80
c4 = d['new_52w_high'] & (d['sharpe60_rank'] >= 0.80)
cands.append(test_cand("Fresh 52w High Breakout in Sharpe60 Top20%", c4))

# 5. New 20-Day High Breakout on Volume Surge in Quality Uptrend: new_20d_high & vol_ratio1 > 2.5 & sharpe60_rank > 0.80
c5 = d['new_20d_high'] & (d['vol_ratio1'] > 2.5) & (d['sharpe60_rank'] >= 0.80) & (d['close'] > d['sma_50'])
cands.append(test_cand("Fresh 20d High Breakout + Vol>2.5x in Sharpe60 Top20%", c5))

# 6. Gap-and-Go Breakout above 50 SMA: gap > 2.0% & ret1 > 2.0% & vol_ratio1 > 2.0 & close > sma50 & prev_close < sma50
prev_close = d.groupby('ticker')['close'].shift(1)
prev_sma50 = d.groupby('ticker')['sma_50'].shift(1)
c6 = (d['gap'] > 2.0) & (d['ret1'] > 2.0) & (d['vol_ratio1'] > 2.0) & (d['close'] > d['sma_50']) & (prev_close < prev_sma50)
cands.append(test_cand("Gap & Go 50 SMA Breakout (Gap>2% + Vol>2x cross SMA50)", c6))

# 7. Multi-Timeframe Confluence Breakout: 20d High + 60d Mom Top Decile + 252d Trend > 30% + Vol Surge > 2x
c7 = (d['close'] >= d['high20']) & (d['ret60_rank'] >= 0.90) & (d['change_252d'] > 30) & (d['vol_ratio1'] > 2.0)
cands.append(test_cand("Multi-Timeframe Momentum Breakout (20d High + Mom60 D10 + 252d>30% + Vol>2x)", c7))

# 8. Turtle / Donchian 20d High Breakout with ATR expansion: new_20d_high & (hl_atr > 1.5) & (vol_ratio1 > 1.5) & (close > sma200)
c8 = d['new_20d_high'] & (d['hl_atr'] > 1.5) & (d['vol_ratio1'] > 1.5) & (d['close'] > d['sma_200'])
cands.append(test_cand("Donchian 20d Breakout + Wide Expansion Bar (HL/ATR>1.5 & Vol>1.5x > SMA200)", c8))

# 9. Pocket Pivot (Signature institutional buy in base): dist_high52w > -0.15 & vol_ratio1 > 2.0 & ret1 > 3.0% & rsi between 50 and 65
c9 = (d['dist_high52w'] > -0.15) & (d['vol_ratio1'] > 2.0) & (d['ret1'] > 3.0) & (d['rsi'].between(50, 65)) & (d['close'] > d['sma_50'])
cands.append(test_cand("Pocket Pivot Base Thrust (Within 15% 52w High + Vol>2x + Ret1>3% + RSI 50-65)", c9))

# 10. Low Volatility Consolidation Breakout (BB BW Rank < 0.15 + Ret1 > 2.5% + Vol Ratio > 1.5 + Close > SMA50)
c10 = (d['bb_bw_rank'] < 0.15) & (d['ret1'] > 2.5) & (d['vol_ratio1'] > 1.5) & (d['close'] > d['sma_50'])
cands.append(test_cand("Low-Vol Compression Breakout (BW<15% + Ret1>2.5% + Vol>1.5x > SMA50)", c10))

res_df = pd.DataFrame([c for c in cands if c is not None])
print("\n--- Explosive Swing Triggers Results (h=8 sessions) ---")
print(res_df.to_string(index=False))
