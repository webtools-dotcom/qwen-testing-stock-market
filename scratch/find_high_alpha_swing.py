"""Search for high-alpha swing setups (>1.5% net per 6-10 day hold).
"""
import pickle
import numpy as np
import pandas as pd

print("Loading _master_flat.pkl...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

# Filter liquid mid/small
mask_liq = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
d = df[mask_liq].copy().reset_index(drop=True)

# Add custom features
d['dist_high52w'] = d['dist_high250']
d['sharpe60_rank'] = d.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))
d['ret60_rank'] = d.groupby('date')['ret60'].transform(lambda x: x.rank(pct=True))
d['turnover_z_rank'] = d.groupby('date')['turnover_z'].transform(lambda x: x.rank(pct=True))
d['amihud_z_rank'] = d.groupby('date')['amihud_z'].transform(lambda x: x.rank(pct=True))
d['dist_high52w_rank'] = d.groupby('date')['dist_high52w'].transform(lambda x: x.rank(pct=True))

# 3-day and 5-day return ranks
d['ret3_rank'] = d.groupby('date')['ret3'].transform(lambda x: x.rank(pct=True))
d['ret5_rank'] = d.groupby('date')['ret5'].transform(lambda x: x.rank(pct=True))

# Intraday thrust
d['co_ret'] = (d['close'] - d['open']) / d['open'] * 100

# High-low range relative to ATR
d['hl_atr'] = (d['high'] - d['low']) / d['atr']

print(f"Dataset ready: {len(d)} rows.")

def scan_setup(name, cond, horizon=8):
    target_col = f'fwd{horizon}_dm'
    raw_col = f'fwd{horizon}'
    sub = d[cond & d[target_col].notna()].copy()
    if len(sub) < 100:
        return None
    daily = sub.groupby('date')[target_col].mean()
    if len(daily) < 30:
        return None
    edge = daily.mean()
    se = daily.std(ddof=1) / np.sqrt(len(daily))
    t_stat = edge / se if se > 0 else 0
    raw_ret = sub[raw_col].mean()
    
    # Net return after 0.50% cost
    net_ret = raw_ret - 0.50
    
    # Subgroup stability
    hA = sub[sub['half'] == 'A'].groupby('date')[target_col].mean()
    hB = sub[sub['half'] == 'B'].groupby('date')[target_col].mean()
    t_A = hA.mean() / (hA.std(ddof=1) / np.sqrt(len(hA))) if len(hA) > 10 and hA.std(ddof=1)>0 else 0
    t_B = hB.mean() / (hB.std(ddof=1) / np.sqrt(len(hB))) if len(hB) > 10 and hB.std(ddof=1)>0 else 0
    
    p1 = sub[sub['period'] == 'P1'].groupby('date')[target_col].mean()
    p2 = sub[sub['period'] == 'P2'].groupby('date')[target_col].mean()
    p3 = sub[sub['period'] == 'P3'].groupby('date')[target_col].mean()
    t_p1 = p1.mean() / (p1.std(ddof=1) / np.sqrt(len(p1))) if len(p1) > 10 and p1.std(ddof=1)>0 else 0
    t_p2 = p2.mean() / (p2.std(ddof=1) / np.sqrt(len(p2))) if len(p2) > 10 and p2.std(ddof=1)>0 else 0
    t_p3 = p3.mean() / (p3.std(ddof=1) / np.sqrt(len(p3))) if len(p3) > 10 and p3.std(ddof=1)>0 else 0
    
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

results = []

# S1: Extreme oversold panic flush in 252d institutional uptrend (RSI < 25 & change_252d > 50% & close > sma200)
c1 = (d['rsi'] < 25) & (d['change_252d'] > 50) & (d['close'] > d['sma_200'])
results.append(scan_setup("Panic Flush in Strong 252d Compounder (RSI<25 & 252d>50% > SMA200)", c1))

# S2: 3-day crash in uptrend (ret3 < -8% & change_252d > 40% & close > sma200)
c2 = (d['ret3'] < -8.0) & (d['change_252d'] > 40) & (d['close'] > d['sma_200'])
results.append(scan_setup("3-Day Sharp Pullback (<-8%) in 252d Leader (>40% > SMA200)", c2))

# S3: 5-day sharp pullback in 60d momentum top decile (ret5 < -7% & ret60_rank > 0.90 & close > sma50)
c3 = (d['ret5'] < -7.0) & (d['ret60_rank'] >= 0.90) & (d['close'] > d['sma_50'])
results.append(scan_setup("5-Day Pullback (<-7%) in 60d Mom Top Decile > SMA50", c3))

# S4: High Volume Absorption Capitulation (ret1 < -3% & vol_ratio1 > 2.5 & change_252d > 30% > sma200)
c4 = (d['ret1'] < -3.0) & (d['vol_ratio1'] > 2.5) & (d['change_252d'] > 30) & (d['close'] > d['sma_200'])
results.append(scan_setup("High Volume Flush Absorption (ret1<-3% & Vol>2.5x in 252d trend)", c4))

# S5: Post-Breakout Retest / High-Volume Continuation (10d High Breakout yesterday + small pullback today ret1 between -1.5% and 0% on low volume vol_ratio1 < 0.8)
# Shifted breakout
d_prev_break = d.groupby('ticker')['close'].shift(1) >= d.groupby('ticker')['high10'].shift(2)
c5 = d_prev_break & (d['ret1'].between(-1.5, 0.0)) & (d['vol_ratio1'] < 0.8) & (d['close'] > d['sma_50'])
results.append(scan_setup("10d Breakout Retest on Low Volume (ret1 [-1.5, 0] & Vol<0.8)", c5))

# S6: 52-Week High Breakout Thrust with Volume (close >= high52w & vol_ratio1 > 2.0 & ret1 > 3%)
c6 = (d['dist_high52w'] >= -0.01) & (d['vol_ratio1'] > 2.0) & (d['ret1'] > 3.0)
results.append(scan_setup("52w High Volume Thrust (within 1% 52w high & Vol>2.0x & Ret1>3%)", c6))

# S7: Short-Term Range Expansion Thrust after Volatility Contraction (bb_bw_rank < 0.10 yesterday + ret1 > 3% on vol_ratio > 1.5 today)
prev_bw_low = d.groupby('ticker')['bb_bw_rank'].shift(1) < 0.10
c7 = prev_bw_low & (d['ret1'] > 3.0) & (d['vol_ratio1'] > 1.5) & (d['close'] > d['sma_50'])
results.append(scan_setup("BB Squeeze Range Expansion (Prev BW<10% + Ret1>3% + Vol>1.5x)", c7))

# S8: Amihud Liquidity Shock Breakout (amihud_z < -2.0 & ret1 > 3.0 & sharpe60_rank > 0.80)
c8 = (d['amihud_z'] < -2.0) & (d['ret1'] > 3.0) & (d['sharpe60_rank'] >= 0.80)
results.append(scan_setup("Amihud Shock Breakout (Amihud z<-2 + Ret1>3% + Sharpe60>80%)", c8))

# S9: Intraday Institutional Accumulation Surge (co_ret > 3% & turnover_z > 2.0 & close > sma50)
c9 = (d['co_ret'] > 3.0) & (d['turnover_z'] > 2.0) & (d['close'] > d['sma_50'])
results.append(scan_setup("Intraday Institutional Surge (CO>3% + Turn_Z>2.0 > SMA50)", c9))

# S10: Multi-Day Relative Strength Divergence during Nifty Pullback (mkt5 < -2% & ret5 > +3% & change_252d > 30%)
c10 = (d['mkt5'] < -2.0) & (d['ret5'] > 3.0) & (d['change_252d'] > 30) & (d['close'] > d['sma_50'])
results.append(scan_setup("Resilient RS Divergence (Mkt5<-2% & Stock Ret5>+3% in Trend)", c10))

# S11: 52w High Nearness + Consecutive Low Volatility Days (dist_high52w > -0.05 & atr_pct_rank < 0.20 & ret1 > 1%)
c11 = (d['dist_high52w'] > -0.05) & (d['atr_pct_rank'] < 0.20) & (d['ret1'] > 1.0)
results.append(scan_setup("Near 52w High + Low ATR Rank (<20%) + Ret1>1%", c11))

# S12: Trend Leader 2-Day Pullback with Narrow Spread (Sharpe60 Top10% & ret2 between -4% and -1.5% & hl_atr < 1.0)
c12 = (d['sharpe60_rank'] >= 0.90) & (d['ret2'].between(-4.0, -1.5)) & (d['hl_atr'] < 1.0) & (d['close'] > d['sma_50'])
results.append(scan_setup("Sharpe60 Top10% + 2d PB (-4 to -1.5%) + Narrow Bar (HL/ATR<1.0)", c12))

res_df = pd.DataFrame([r for r in results if r is not None])
print("\n--- High-Alpha Swing Setup Results (h=8 sessions) ---")
print(res_df.to_string(index=False))
