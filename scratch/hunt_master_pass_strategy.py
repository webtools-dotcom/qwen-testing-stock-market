"""Master Search for Robust Verdict-Pass Strategy in NSE/BSE.
Tests multi-factor structural anomalies with regime protection across 10 years.
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

print("Loading master dataset...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

# Liquid mid/small caps
df['is_liquid_midsmall'] = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
d = df[df['is_liquid_midsmall']].copy().reset_index(drop=True)

# Engineer Advanced Features
# 1. 52-Week High Proximity
d['dist_high52w'] = d['dist_high250']
d['near_ath'] = d['dist_high52w'] >= -0.05 # within 5% of 52w high

# 2. Dual Timeframe Momentum Acceleration: Ret60 rank vs Ret252 rank
d['ret60_rank'] = d.groupby('date')['ret60'].transform(lambda x: x.rank(pct=True))
d['change_252d_rank'] = d.groupby('date')['change_252d'].transform(lambda x: x.rank(pct=True))
d['ret20_rank'] = d.groupby('date')['ret20'].transform(lambda x: x.rank(pct=True))
d['sharpe60_rank'] = d.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))

# 3. Path Smoothness / Trend Quality: Information Ratio over 120d
d['ret1_std120'] = d.groupby('ticker')['ret1'].transform(lambda x: x.rolling(120).std())
d['ret1_mean120'] = d.groupby('ticker')['ret1'].transform(lambda x: x.rolling(120).mean())
d['trend_ir120'] = (d['ret1_mean120'] / (d['ret1_std120'] + 1e-6)) * np.sqrt(252)
d['trend_ir120_rank'] = d.groupby('date')['trend_ir120'].transform(lambda x: x.rank(pct=True))

# 4. Volatility Contraction / Squeeze: BB Bandwidth Rank
d['squeeze'] = d['bb_bw_rank'] < 0.30

# 5. Market Regime: Nifty 50 surrogate (mean market return > SMA)
# Market breadth: % of stocks above SMA50
d['above_sma50'] = d['close'] > d['sma_50']
breadth = d.groupby('date')['above_sma50'].mean()
d['mkt_breadth'] = d['date'].map(breadth)
d['bull_regime'] = d['mkt_breadth'] >= 0.45

# 6. Composite Score: 52w High Proximity + Sharpe60 + Trend IR120
d['quality_composite'] = (
    0.40 * (1.0 + d['dist_high52w']) + 
    0.35 * d['sharpe60_rank'] + 
    0.25 * d['trend_ir120_rank']
)
d['quality_composite_rank'] = d.groupby('date')['quality_composite'].transform(lambda x: x.rank(pct=True))

# 7. Low-Volatility Momentum Leader Composite
vol50_rank = d.groupby('date')['vol50'].transform(lambda x: x.rank(pct=True))
d['lowvol_mom_composite'] = 0.60 * d['ret60_rank'] + 0.40 * (1.0 - vol50_rank)
d['lowvol_mom_rank'] = d.groupby('date')['lowvol_mom_composite'].transform(lambda x: x.rank(pct=True))

pre2017_set = set(df[df['date'] <= '2017-01-01']['ticker'].unique())

print(f"Features ready. Testing high-conviction candidate engines across horizons...")

# Re-group by ticker
panel = {t: grp.sort_values('date').reset_index(drop=True) for t, grp in d.groupby('ticker')}

def test_engine_candidate(name, get_sig_fn, horizon=25):
    rng = np.random.default_rng(42)
    strat_trades, ctrl_trades = [], []
    strat_B, ctrl_B = [], []
    strat_pre, ctrl_pre = [], []
    
    for t, data in panel.items():
        if len(data) < 300: continue
        sig = get_sig_fn(data).values
        liq = data['is_liquid_midsmall'].fillna(False).values
        
        st = simulate_trades(data, sig, horizon_days=horizon, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        strat_trades += st
        ct = simulate_trades(data, (rng.random(len(data)) < 0.10) & liq, horizon_days=horizon, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
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
        return [item for t_c, data in panel.items() if len(data) >= 300
                for item in simulate_trades(data, (r.random(len(data)) < 0.10) & data['is_liquid_midsmall'].fillna(False).values, horizon_days=horizon, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)]
    
    stable = stable_day_clustered_z(strat_trades, cf, n_seeds=10)
    net_avg = np.mean([x['net_pct'] for x in strat_trades])
    
    print(f"\n[{name}] (h={horizon} sessions):")
    print(f"  Trades: {len(strat_trades):4d} | Paired Days: {dc_pool['n_days']} | Net/trade: {net_avg:+.2f}% | DayEdge: {dc_pool['day_edge']:+.3f}%")
    print(f"  Stable Mean z_paired: {stable['mean_z']:.2f} (Pass Rate: {stable['pass_rate']*100:.0f}%, Min: {stable['min_z']:.2f}, Max: {stable['max_z']:.2f})")
    print(f"  Holdout Half B: Trades={len(strat_B)}, DayEdge={dc_B['day_edge']:+.3f}%, z_paired={dc_B['z_paired']:.2f}")
    print(f"  Pre-2017 Listings: Trades={len(strat_pre)}, DayEdge={dc_pre['day_edge']:+.3f}%, z_paired={dc_pre['z_paired']:.2f}")
    
    return {
        'name': name, 'horizon': horizon, 'trades': len(strat_trades),
        'net_avg': net_avg, 'day_edge': dc_pool['day_edge'],
        'stable_mean_z': stable['mean_z'], 'pass_rate': stable['pass_rate'],
        'z_B': dc_B['z_paired'], 'z_pre': dc_pre['z_paired']
    }

# 1. Quality Trend Consistency & 52w High Nearness Leader (Top 10% Composite > SMA50)
def sig_qcomp(data):
    return (data['quality_composite_rank'] >= 0.90) & (data['close'] > data['sma_50'])

test_engine_candidate("Quality 52w High + Trend Consistency (Top 10%)", sig_qcomp, horizon=25)
test_engine_candidate("Quality 52w High + Trend Consistency (Top 10%)", sig_qcomp, horizon=35)

# 2. Regime-Filtered Quality Leader (Top 10% Composite during Market Breadth >= 45%)
def sig_regime_qcomp(data):
    return (data['quality_composite_rank'] >= 0.90) & (data['close'] > data['sma_50']) & data['bull_regime']

test_engine_candidate("Regime-Filtered Quality Composite (Breadth >= 45%)", sig_regime_qcomp, horizon=25)
test_engine_candidate("Regime-Filtered Quality Composite (Breadth >= 45%)", sig_regime_qcomp, horizon=35)

# 3. Dual Acceleration Leader (Ret60 Top 15% + Ret252 Top 20% + Dist 52w >= -8% > SMA50)
def sig_dual_accel(data):
    return (data['ret60_rank'] >= 0.85) & (data['change_252d_rank'] >= 0.80) & (data['dist_high52w'] >= -0.08) & (data['close'] > data['sma_50'])

test_engine_candidate("Dual-Timeframe Momentum Acceleration (60d & 252d near 52w High)", sig_dual_accel, horizon=25)
test_engine_candidate("Dual-Timeframe Momentum Acceleration (60d & 252d near 52w High)", sig_dual_accel, horizon=35)

# 4. Volatility Squeeze Breakout in 52w High Trend Leaders (Squeeze + Close > High20)
def sig_sqz_trend(data):
    return data['squeeze'] & (data['dist_high52w'] >= -0.05) & (data['ret60_rank'] >= 0.80) & (data['close'] > data['sma_50'])

test_engine_candidate("Volatility Squeeze at 52-Week Highs", sig_sqz_trend, horizon=25)
