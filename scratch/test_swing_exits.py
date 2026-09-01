"""Compare exit mechanisms for swing trading (6-10 days).
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

df['is_liquid_midsmall'] = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
df['dist_high52w'] = df['dist_high250']

df['sharpe60_rank'] = df.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))
df['dist_high52w_rank'] = df.groupby('date')['dist_high52w'].transform(lambda x: x.rank(pct=True))
df['comp_raw'] = (df['sharpe60_rank'] + df['dist_high52w_rank']) / 2.0
df['comp_rank'] = df.groupby('date')['comp_raw'].transform(lambda x: x.rank(pct=True))

panel_feat = {t: grp.sort_values('date').reset_index(drop=True) for t, grp in df.groupby('ticker')}

def evaluate_setup(name, sig_func, horizon=8, stop_atr=None, target_atr=None):
    rng = np.random.default_rng(42)
    strat_trades, ctrl_trades = [], []
    per_ticker_sig = {}
    per_ticker_liq = {}
    
    for t, d in panel_feat.items():
        if len(d) < 300:
            continue
        liq = d['is_liquid_midsmall'].fillna(False).values
        sig = sig_func(d) & liq
        per_ticker_sig[t] = sig
        per_ticker_liq[t] = liq
        
        # Stop / target kwargs
        s_mult = stop_atr if stop_atr is not None else 999.0
        t_mult = target_atr if target_atr is not None else 999.0
        
        st = simulate_trades(d, sig, horizon_days=horizon, stop_atr_mult=s_mult, 
                             target_atr_mult=t_mult, charge_costs=True, allow_overlap=False)
        strat_trades += st
        
        ctrl_mask = (rng.random(len(d)) < 0.10) & liq
        ct = simulate_trades(d, ctrl_mask, horizon_days=horizon, stop_atr_mult=s_mult, 
                             target_atr_mult=t_mult, charge_costs=True, allow_overlap=False)
        ctrl_trades += ct
        
    dc = day_clustered_edge(strat_trades, ctrl_trades)
    s_net = [t['net_pct'] for t in strat_trades]
    c_net = [t['net_pct'] for t in ctrl_trades]
    
    # 10 control seeds
    def ctrl_factory(seed):
        r = np.random.default_rng(seed)
        c_trades = []
        for t, d in panel_feat.items():
            if t not in per_ticker_liq:
                continue
            liq = per_ticker_liq[t]
            ctrl_mask = (r.random(len(d)) < 0.10) & liq
            c_trades += simulate_trades(d, ctrl_mask, horizon_days=horizon, stop_atr_mult=s_mult, 
                                        target_atr_mult=t_mult, charge_costs=True, allow_overlap=False)
        return c_trades

    stable = stable_day_clustered_z(strat_trades, ctrl_factory, n_seeds=10)
    
    return {
        'name': name,
        'horizon': horizon,
        'stop': stop_atr,
        'target': target_atr,
        'trades': len(strat_trades),
        'net_avg': np.mean(s_net) if s_net else 0,
        'ctrl_avg': np.mean(c_net) if c_net else 0,
        'edge': (np.mean(s_net) - np.mean(c_net)) if s_net and c_net else 0,
        'win_rate': (np.array(s_net) > 0).mean() * 100 if s_net else 0,
        'z_paired_seed42': dc['z_paired'] if dc else 0,
        'stable_mean_z': stable['mean_z'] if stable else 0,
        'pass_rate': stable['pass_rate'] if stable else 0,
    }

# Signals to test
def s_sharpe_pb(d):
    return (d['sharpe60_rank'] >= 0.85) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])

def s_comp_pb(d):
    return (d['comp_rank'] >= 0.85) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])

def s_52w_pb(d):
    return (d['dist_high52w'] > -0.08) & (d['ret3'] < -1.0) & (d['vol_ratio1'] < 0.70) & (d['close'] > d['sma_50'])

configs = [
    # Signal, Horizon, Stop, Target
    ("Sharpe_PB (Time Exit h=8)", s_sharpe_pb, 8, None, None),
    ("Sharpe_PB (Time Exit h=6)", s_sharpe_pb, 6, None, None),
    ("Sharpe_PB (Time Exit h=10)", s_sharpe_pb, 10, None, None),
    ("Sharpe_PB (Stop 3xATR, Target None, h=8)", s_sharpe_pb, 8, 3.0, None),
    ("Sharpe_PB (Stop 2xATR, Target 3xATR, h=8)", s_sharpe_pb, 8, 2.0, 3.0),
    
    ("Comp_PB (Time Exit h=8)", s_comp_pb, 8, None, None),
    ("Comp_PB (Time Exit h=6)", s_comp_pb, 6, None, None),
    ("Comp_PB (Time Exit h=10)", s_comp_pb, 10, None, None),
    ("Comp_PB (Stop 3xATR, Target None, h=8)", s_comp_pb, 8, 3.0, None),
    
    ("52w_PB (Time Exit h=8)", s_52w_pb, 8, None, None),
    ("52w_PB (Time Exit h=6)", s_52w_pb, 6, None, None),
    ("52w_PB (Time Exit h=10)", s_52w_pb, 10, None, None),
    ("52w_PB (Stop 3xATR, Target None, h=8)", s_52w_pb, 8, 3.0, None),
]

res = []
for name, s_fn, h, st, tg in configs:
    r = evaluate_setup(name, s_fn, horizon=h, stop_atr=st, target_atr=tg)
    print(f"{name:45s} | Trades: {r['trades']:4d} | Net: {r['net_avg']:+.2f}% | Edge: {r['edge']:+.2f}% | Win: {r['win_rate']:.1f}% | z_pair: {r['z_paired_seed42']:+.2f} | stable_z: {r['stable_mean_z']:+.2f} ({r['pass_rate']*100:.0f}%)")
    res.append(r)

df_res = pd.DataFrame(res)
print("\nSummary:")
print(df_res[['name', 'trades', 'net_avg', 'edge', 'win_rate', 'stable_mean_z', 'pass_rate']].to_string(index=False))
