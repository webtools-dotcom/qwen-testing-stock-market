"""Test Panic-Conditioned Deep Mean Reversion in Mid/Small Caps (2016-2026).
Exploits liquidity-tiered panic flushes with oversold gradient.
"""
import sys, os
sys.path.insert(0, '.')
import pickle
import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z,
    report, walk_forward_splits, sharpe
)

print("Loading dataset...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

# Liquid mid/small caps
df['is_liquid_midsmall'] = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
d = df[df['is_liquid_midsmall']].copy().reset_index(drop=True)

# Features
# Market panic: 5-day market return < -2.0% or 20d volatility in top 20%
d['mkt_panic'] = d['mkt5'] < -1.5

# Deep oversold: RSI < 25 or RSI < 28 with 3-day drop < -6%
d['ret3'] = (d['close'] - d.groupby('ticker')['close'].shift(3)) / d.groupby('ticker')['close'].shift(3) * 100
d['ret5'] = (d['close'] - d.groupby('ticker')['close'].shift(5)) / d.groupby('ticker')['close'].shift(5) * 100

# Consecutive down days
d['down1'] = d['ret1'] < 0
d['down2'] = d.groupby('ticker')['down1'].shift(1).fillna(False) & d['down1']
d['down3'] = d.groupby('ticker')['down1'].shift(2).fillna(False) & d['down2']
d['down4'] = d.groupby('ticker')['down1'].shift(3).fillna(False) & d['down3']

# Volume climax on down day (Volume > 1.5x 20d SMA while down >= 3%)
d['vol_flush'] = (d['vol_ratio1'] > 1.5) & (d['ret1'] < -3.0)

# Structural trend context: Close > 200 SMA (long-term uptrend dip)
d['above_200'] = d['close'] > d['sma_200']

# Signal 1: Deep RSI < 25 in liquid mid/small caps (holding 4-6 days)
s1 = (d['rsi'] < 25) & d['is_liquid_midsmall']

# Signal 2: RSI < 30 + 3 consecutive down days + Ret3 < -5% in long-term uptrend (Close > SMA200)
s2 = (d['rsi'] < 30) & d['down3'] & (d['ret3'] < -5.0) & d['above_200']

# Signal 3: Volume Flush in Uptrend (Close > SMA200 + Ret3 < -6% + Vol Ratio > 1.8 + RSI < 30)
s3 = d['above_200'] & (d['ret3'] < -6.0) & (d['vol_ratio1'] > 1.8) & (d['rsi'] < 30)

# Signal 4: Market Panic Reversion (Mkt Panic + Stock RSI < 28 + Stock Ret3 < -5%)
s4 = d['mkt_panic'] & (d['rsi'] < 28) & (d['ret3'] < -5.0)

pre2017_set = set(df[df['date'] <= '2017-01-01']['ticker'].unique())

panel = {t: grp.sort_values('date').reset_index(drop=True) for t, grp in d.groupby('ticker')}

def test_signal_engine(name, mask_series, h=5):
    d['sig'] = mask_series
    sig_panel = {t: grp.sort_values('date').reset_index(drop=True) for t, grp in d.groupby('ticker')}
    
    rng = np.random.default_rng(42)
    strat_trades, ctrl_trades = [], []
    strat_B, ctrl_B = [], []
    strat_pre, ctrl_pre = [], []
    
    for t, data in sig_panel.items():
        if len(data) < 300: continue
        sig = data['sig'].fillna(False).values
        liq = data['is_liquid_midsmall'].fillna(False).values
        
        st = simulate_trades(data, sig, horizon_days=h, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        strat_trades += st
        ct = simulate_trades(data, (rng.random(len(data)) < 0.10) & liq, horizon_days=h, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        ctrl_trades += ct
        
        if data['half'].iloc[0] == 'B':
            strat_B += st
            ctrl_B += ct
        if t in pre2017_set:
            strat_pre += st
            ctrl_pre += ct
            
    dc_pool = day_clustered_edge(strat_trades, ctrl_trades)
    dc_B = day_clustered_edge(strat_B, ctrl_B)
    dc_pre = day_clustered_edge(strat_pre, ctrl_pre)
    
    def cf(seed):
        r = np.random.default_rng(seed)
        return [item for t_c, data in sig_panel.items() if len(data) >= 300
                for item in simulate_trades(data, (r.random(len(data)) < 0.10) & data['is_liquid_midsmall'].fillna(False).values, horizon_days=h, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)]
    
    stable = stable_day_clustered_z(strat_trades, cf, n_seeds=10)
    net_avg = np.mean([x['net_pct'] for x in strat_trades]) if len(strat_trades)>0 else 0
    
    print(f"\n[{name}] (h={h} sessions):")
    print(f"  Trades: {len(strat_trades):4d} | Paired Days: {dc_pool['n_days'] if dc_pool else 0} | Net/trade: {net_avg:+.2f}% | DayEdge: {dc_pool['day_edge'] if dc_pool else 0:+.3f}%")
    print(f"  Stable Mean z_paired: {stable['mean_z']:.2f} (Pass Rate: {stable['pass_rate']*100:.0f}%, Min: {stable['min_z']:.2f}, Max: {stable['max_z']:.2f})")
    print(f"  Holdout Half B: Trades={len(strat_B)}, DayEdge={dc_B['day_edge'] if dc_B else 0:+.3f}%, z_paired={dc_B['z_paired'] if dc_B else 0:.2f}")
    print(f"  Pre-2017 Listings: Trades={len(strat_pre)}, DayEdge={dc_pre['day_edge'] if dc_pre else 0:+.3f}%, z_paired={dc_pre['z_paired'] if dc_pre else 0:.2f}")

test_signal_engine("Signal 1: Deep RSI < 25 in Liquid Mid/Small", s1, h=5)
test_signal_engine("Signal 1: Deep RSI < 25 in Liquid Mid/Small", s1, h=8)
test_signal_engine("Signal 2: 3 Down Days + Ret3 < -5% + RSI < 30 > SMA200", s2, h=5)
test_signal_engine("Signal 2: 3 Down Days + Ret3 < -5% + RSI < 30 > SMA200", s2, h=8)
test_signal_engine("Signal 3: Volume Flush in Uptrend (Vol>1.8x, Ret3<-6%, RSI<30 > SMA200)", s3, h=5)
test_signal_engine("Signal 3: Volume Flush in Uptrend (Vol>1.8x, Ret3<-6%, RSI<30 > SMA200)", s3, h=8)
test_signal_engine("Signal 4: Market Panic Reversion (Mkt Panic + RSI<28 + Ret3<-5%)", s4, h=5)
test_signal_engine("Signal 4: Market Panic Reversion (Mkt Panic + RSI<28 + Ret3<-5%)", s4, h=8)
