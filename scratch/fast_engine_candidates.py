"""Fast backtest engine runner using pre-computed master panel.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import numpy as np
import pandas as pd
from backtest_engine import simulate_trades, day_clustered_edge, stable_day_clustered_z, report

print("Loading _master_flat.pkl...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

print(f"Master flat loaded: {len(df)} rows, {df['ticker'].nunique()} tickers.")

df['is_liquid_midsmall'] = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
df['dist_high52w'] = df['dist_high250']

# Compute cross-sectional ranks by date
df['sharpe60_rank'] = df.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))
df['dist_high52w_rank'] = df.groupby('date')['dist_high52w'].transform(lambda x: x.rank(pct=True))
df['comp_raw'] = (df['sharpe60_rank'] + df['dist_high52w_rank']) / 2.0
df['comp_rank'] = df.groupby('date')['comp_raw'].transform(lambda x: x.rank(pct=True))

# Re-group by ticker
panel_feat = {t: grp.sort_values('date').reset_index(drop=True) for t, grp in df.groupby('ticker')}

def test_engine_strategy(name, signal_func, horizon=8, stop_atr=2.0, target_atr=2.0):
    print(f"\n=======================================================")
    print(f"Testing Candidate: {name} (horizon={horizon})")
    print(f"=======================================================")
    
    rng = np.random.default_rng(42)
    strat_trades, ctrl_trades = [], []
    per_ticker_sig = {}
    per_ticker_liq = {}
    
    for t, d in panel_feat.items():
        if len(d) < 300:
            continue
        liq = d['is_liquid_midsmall'].fillna(False).values
        sig = signal_func(d) & liq
        per_ticker_sig[t] = sig
        per_ticker_liq[t] = liq
        
        st = simulate_trades(d, sig, horizon_days=horizon, stop_atr_mult=stop_atr, 
                             target_atr_mult=target_atr, charge_costs=True, allow_overlap=False)
        strat_trades += st
        
        ctrl_mask = (rng.random(len(d)) < 0.10) & liq
        ct = simulate_trades(d, ctrl_mask, horizon_days=horizon, stop_atr_mult=stop_atr, 
                             target_atr_mult=target_atr, charge_costs=True, allow_overlap=False)
        ctrl_trades += ct
        
    print(report(name, strat_trades, ctrl_trades, holding_days=horizon))
    
    def ctrl_factory(seed):
        r = np.random.default_rng(seed)
        c_trades = []
        for t, d in panel_feat.items():
            if t not in per_ticker_liq:
                continue
            liq = per_ticker_liq[t]
            ctrl_mask = (r.random(len(d)) < 0.10) & liq
            c_trades += simulate_trades(d, ctrl_mask, horizon_days=horizon, stop_atr_mult=stop_atr, 
                                        target_atr_mult=target_atr, charge_costs=True, allow_overlap=False)
        return c_trades

    stable = stable_day_clustered_z(strat_trades, ctrl_factory, n_seeds=20)
    print(f"Stable Control (20 seeds): Mean z_paired = {stable['mean_z']:.2f} (min {stable['min_z']:.2f}, max {stable['max_z']:.2f}), Pass Rate = {stable['pass_rate']*100:.1f}%")
    return strat_trades, ctrl_trades, stable

# C1: Sharpe60 Top15% + 3d Pullback + Vol Dryup
def sig_c1(d):
    return (d['sharpe60_rank'] >= 0.85) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])

# C2: Composite Top15% + 3d Pullback + Vol Dryup
def sig_c2(d):
    return (d['comp_rank'] >= 0.85) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])

# C3: 52w High Nearness (<8%) + 3d Pullback + Vol Dryup
def sig_c3(d):
    return (d['dist_high52w'] > -0.08) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])

test_engine_strategy("C1: Sharpe60 Top15% + 3d PB (<-1%) + VolDryup (<0.7) > SMA50", sig_c1, horizon=8)
test_engine_strategy("C2: Composite Top15% + 3d PB (<-1%) + VolDryup (<0.7) > SMA50", sig_c2, horizon=8)
test_engine_strategy("C3: 52w High Nearness (<8%) + 3d PB (<-1%) + VolDryup (<0.7) > SMA50", sig_c3, horizon=8)
