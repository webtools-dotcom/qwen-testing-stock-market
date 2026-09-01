"""Comprehensive validation of Low-Volatility 12-1 Momentum in Mid/Small Caps.
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

print("Loading master flat dataset...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

# Liquid mid/small caps
df['is_liquid_midsmall'] = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)

# Features
df['mom_12_1'] = df['change_252d'] - df['ret20']
df['mom_12_1_rank'] = df.groupby('date')['mom_12_1'].transform(lambda x: x.rank(pct=True))
df['vol50_rank'] = df.groupby('date')['vol50'].transform(lambda x: x.rank(pct=True))

# Signal mask: Mom 12-1 Top 15% + Vol50 lowest 40% + Close > SMA50
def get_sig(d, mom_q=0.85, vol_q=0.40):
    return (
        (d['mom_12_1_rank'] >= mom_q) &
        (d['vol50_rank'] <= vol_q) &
        (d['close'] > d['sma_50']) &
        d['is_liquid_midsmall']
    )

panel = {t: grp.sort_values('date').reset_index(drop=True) for t, grp in df.groupby('ticker')}

for h in [15, 20, 30]:
    rng = np.random.default_rng(42)
    st, ct = [], []
    for t, d in panel.items():
        if len(d) < 300: continue
        liq = d['is_liquid_midsmall'].fillna(False).values
        sig = get_sig(d).values
        st += simulate_trades(d, sig, horizon_days=h, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        ct += simulate_trades(d, (rng.random(len(d)) < 0.10) & liq, horizon_days=h, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        
    def cf(seed):
        r = np.random.default_rng(seed)
        return [t_item for t_code, d in panel.items() if len(d) >= 300
                for t_item in simulate_trades(d, (r.random(len(d)) < 0.10) & d['is_liquid_midsmall'].fillna(False).values, horizon_days=h, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)]
    
    stable = stable_day_clustered_z(st, cf, n_seeds=10)
    dc = day_clustered_edge(st, ct)
    net_avg = np.mean([x['net_pct'] for x in st])
    print(f"\nHorizon {h} sessions: Trades={len(st):4d} | Net/tr={net_avg:+.2f}% | DayEdge={dc['day_edge']:+.3f}% | Single z={dc['z_paired']:.2f} | Stable Mean z={stable['mean_z']:.2f} ({stable['pass_rate']*100:.0f}% pass)")

# Test Holdout Half B and Pre-2017 at h=20
st_B, ct_B = [], []
st_pre, ct_pre = [], []
pre2017_set = set(df[df['date'] <= '2017-01-01']['ticker'].unique())

for t, d in panel.items():
    if len(d) < 300: continue
    liq = d['is_liquid_midsmall'].fillna(False).values
    sig = get_sig(d).values
    if d['half'].iloc[0] == 'B':
        st_B += simulate_trades(d, sig, horizon_days=20, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        ct_B += simulate_trades(d, (rng.random(len(d)) < 0.10) & liq, horizon_days=20, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
    if t in pre2017_set:
        st_pre += simulate_trades(d, sig, horizon_days=20, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        ct_pre += simulate_trades(d, (rng.random(len(d)) < 0.10) & liq, horizon_days=20, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)

dc_B = day_clustered_edge(st_B, ct_B)
dc_pre = day_clustered_edge(st_pre, ct_pre)
print(f"\nHoldout Half B (h=20): Trades={len(st_B)}, Net={np.mean([x['net_pct'] for x in st_B]):+.2f}%, DayEdge={dc_B['day_edge']:+.3f}%, z_paired={dc_B['z_paired']:.2f}")
print(f"Pre-2017 Listings (h=20): Trades={len(st_pre)}, Net={np.mean([x['net_pct'] for x in st_pre]):+.2f}%, DayEdge={dc_pre['day_edge']:+.3f}%, z_paired={dc_pre['z_paired']:.2f}")

# 20-slot Portfolio simulation at h=20
print("\n--- 20-Slot Portfolio Simulation (h=20 sessions) ---")
piv_close = df.pivot(index='date', columns='ticker', values='close')
all_dates = sorted(df['date'].unique())

sig_series = {}
rank_series = {}
for dt, grp in df.groupby('date'):
    sub_sig = get_sig(grp)
    sig_series[dt] = set(grp[sub_sig]['ticker'])
    rank_series[dt] = grp.set_index('ticker')['mom_12_1_rank'].to_dict()

def sim_portfolio(cost_rt=0.0050, n_slots=20, horizon=20):
    cash = 1.0
    positions = []
    nav_hist = []
    trade_count = 0
    
    for dt in all_dates:
        curr_prices = piv_close.loc[dt]
        
        # 1. Exits
        new_pos = []
        for pos in positions:
            t = pos['ticker']
            pos['held'] += 1
            curr_p = curr_prices.get(t, np.nan)
            if pos['held'] >= horizon or np.isnan(curr_p):
                exit_p = curr_p if not np.isnan(curr_p) else pos['entry_p']
                ret = (exit_p - pos['entry_p']) / pos['entry_p']
                cash += pos['alloc'] * (1 + ret) * (1 - cost_rt / 2.0)
                trade_count += 1
            else:
                new_pos.append(pos)
        positions = new_pos
        
        # 2. Entries
        open_slots = n_slots - len(positions)
        today_cands = [c for c in sig_series.get(dt, set()) if c not in {p['ticker'] for p in positions} and not np.isnan(curr_prices.get(c, np.nan))]
        if open_slots > 0 and cash > 0.01 and today_cands:
            today_ranks = rank_series.get(dt, {})
            sorted_cands = sorted(today_cands, key=lambda c: today_ranks.get(c, 0), reverse=True)[:open_slots]
            
            pos_val = sum(pos['alloc'] * (curr_prices.get(pos['ticker'], pos['entry_p']) / pos['entry_p']) for pos in positions)
            nav = cash + pos_val
            target_alloc = min(cash / len(sorted_cands), nav / n_slots)
            
            for t in sorted_cands:
                alloc = min(target_alloc, cash)
                if alloc > 0.001:
                    cash -= alloc
                    positions.append({
                        'ticker': t, 'entry_p': curr_prices[t], 'entry_date': dt,
                        'held': 0, 'alloc': alloc * (1 - cost_rt / 2.0)
                    })
        
        pos_val = sum(pos['alloc'] * (curr_prices.get(pos['ticker'], pos['entry_p']) / pos['entry_p']) for pos in positions)
        nav = cash + pos_val
        nav_hist.append({'date': dt, 'nav': nav})
        
    res_df = pd.DataFrame(nav_hist).set_index('date')
    cagr = (res_df['nav'].iloc[-1] ** (252.0 / len(res_df)) - 1) * 100
    daily_ret = res_df['nav'].pct_change().dropna()
    sharpe_val = daily_ret.mean() / daily_ret.std() * np.sqrt(252) if daily_ret.std() > 0 else 0
    max_dd = (res_df['nav'] / res_df['nav'].cummax() - 1).min() * 100
    return {'cagr': cagr, 'sharpe': sharpe_val, 'max_dd': max_dd, 'trades_yr': trade_count / (len(res_df)/252.0)}

bh_daily = piv_close.pct_change().mean(axis=1).fillna(0)
bh_nav = (1 + bh_daily).cumprod()
bh_cagr = (bh_nav.iloc[-1] ** (252.0 / len(bh_nav)) - 1) * 100
bh_sharpe = bh_daily.mean() / bh_daily.std() * np.sqrt(252)
bh_max_dd = (bh_nav / bh_nav.cummax() - 1).min() * 100

p10 = sim_portfolio(cost_rt=0.0050)
p15 = sim_portfolio(cost_rt=0.0075)
p20 = sim_portfolio(cost_rt=0.0100)

print(f"Benchmark Equal-Weight Buy & Hold: CAGR = +{bh_cagr:.2f}%, Sharpe = {bh_sharpe:.2f}, MaxDD = {bh_max_dd:.2f}%")
print(f"Low-Vol Mom (1.0x costs, 0.50% RT): CAGR = +{p10['cagr']:.2f}%, Sharpe = {p10['sharpe']:.2f}, MaxDD = {p10['max_dd']:.2f}%, Trades/yr = {p10['trades_yr']:.1f}")
print(f"Low-Vol Mom (1.5x costs, 0.75% RT): CAGR = +{p15['cagr']:.2f}%, Sharpe = {p15['sharpe']:.2f}, MaxDD = {p15['max_dd']:.2f}%")
print(f"Low-Vol Mom (2.0x costs, 1.00% RT): CAGR = +{p20['cagr']:.2f}%, Sharpe = {p20['sharpe']:.2f}, MaxDD = {p20['max_dd']:.2f}%")
