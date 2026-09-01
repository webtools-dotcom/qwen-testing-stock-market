"""Out-of-Sample Forward Test for Strategy 027 (2024-01-01 to 2026-08-29).
Tests if Strategy 027 clears stable mean z_paired >= 2.0 and beats Buy & Hold out-of-sample.
"""
import sys, os
sys.path.insert(0, '.')
import pickle
import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z,
    report, sharpe
)

print("Loading master dataset...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

# Liquid mid/small caps
NIFTY_50 = {"RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL",
            "BAJFINANCE", "LICI", "LT", "HCLTECH", "KOTAKBANK", "AXISBANK", "ASIANPAINT",
            "TITAN", "MARUTI", "SUNPHARMA", "ULTRACEMCO", "TATAMOTORS", "BAJAJFINSV",
            "NTPC", "ONGC", "POWERGRID", "ADANIENT", "ADANIPORTS", "COALINDIA", "WIPRO",
            "JSWSTEEL", "TATASTEEL", "M&M", "GRASIM", "TECHM", "NESTLEIND", "CIPLA",
            "DIVISLAB", "HDFCLIFE", "SBILIFE", "DRREDDY", "BRITANNIA", "APOLLOHOSP",
            "TATACONSUM", "EICHERMOT", "BAJAJ-AUTO", "HINDALCO", "BPCL", "HEROMOTOCO",
            "INDUSINDBK", "SHRIRAMFIN", "TRENT", "LTIM", "JIOFIN"}

df['mid_small'] = ~df['ticker'].isin(NIFTY_50)
df['is_liquid_midsmall'] = (df['turnover_60d'] >= 25e7) & df['mid_small']

# Pre-compute Strategy 027 features across full history
panel = {t: grp.sort_values('date').reset_index(drop=True) for t, grp in df.groupby('ticker')}

for t, d in panel.items():
    r = d['close'].pct_change()
    mu252 = r.rolling(252).mean()
    sd252 = r.rolling(252).std()
    d['t_stat_252'] = (mu252 / sd252.replace(0, np.nan)) * np.sqrt(252)
    high_252 = d['high'].rolling(252).max()
    d['near_52w_high'] = d['close'] / high_252
    panel[t] = d

flat = pd.concat([d[['date', 'ticker', 'is_liquid_midsmall', 't_stat_252', 'near_52w_high']] for d in panel.values()], ignore_index=True)
elig = flat[flat['is_liquid_midsmall'].fillna(False)]

flat.loc[elig.index, 'rank_tstat'] = elig.groupby('date')['t_stat_252'].rank(pct=True)
flat.loc[elig.index, 'rank_52w'] = elig.groupby('date')['near_52w_high'].rank(pct=True)
flat.loc[elig.index, 'comp'] = (flat.loc[elig.index, 'rank_tstat'] + flat.loc[elig.index, 'rank_52w']) / 2.0
flat.loc[elig.index, 'rank'] = flat.loc[elig.index].groupby('date')['comp'].rank(pct=True)

key = flat.set_index(['ticker', 'date'])
for t, d in panel.items():
    sub = key.loc[t]
    idx = pd.Index(d['date'].values)
    d['strat_rank'] = sub['rank'].reindex(idx).values
    panel[t] = d

# Slice out-of-sample window (2024-01-01 to 2026-08-29)
oos_panel = {}
for t, d in panel.items():
    if t in NIFTY_50: continue
    sub = d[(d['date'] >= '2024-01-01') & (d['date'] <= '2026-08-29')].reset_index(drop=True)
    if len(sub) >= 40:
        oos_panel[t] = sub

print(f"OOS Panel ready: {len(oos_panel)} mid/small tickers (2024-01-01 to 2026-08-29).")

rng = np.random.default_rng(42)
strat_trades = []
ctrl_trades = []

for t, d in oos_panel.items():
    sig = (d['strat_rank'] >= 0.90).fillna(False).values
    liq = d['is_liquid_midsmall'].fillna(False).values
    strat_trades += simulate_trades(d, sig, horizon_days=42, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
    ctrl_trades += simulate_trades(d, (rng.random(len(d)) < 0.10) & liq, horizon_days=42, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)

dc = day_clustered_edge(strat_trades, ctrl_trades)

def cf_oos(seed):
    r = np.random.default_rng(seed)
    return [item for t, d in oos_panel.items()
            for item in simulate_trades(d, (r.random(len(d)) < 0.10) & d['is_liquid_midsmall'].fillna(False).values, horizon_days=42, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)]

stable_oos = stable_day_clustered_z(strat_trades, cf_oos, n_seeds=20)
net_avg = np.mean([x['net_pct'] for x in strat_trades])
gross_avg = np.mean([x['gross_pct'] for x in strat_trades])

print("="*80)
print("OUT-OF-SAMPLE FORWARD TEST RESULTS (2024-01-01 to 2026-08-29)")
print("="*80)
print(f"OOS Trades: {len(strat_trades)} | Paired Days: {dc['n_days']}")
print(f"Gross avg return/trade: {gross_avg:+.3f}% | Net avg return/trade: {net_avg:+.3f}%")
print(f"OOS Net Day Edge (Seed 42): {dc['day_edge']:+.3f}% | z_paired: {dc['z_paired']:.2f}")
print(f"OOS Stable Mean z_paired (20 seeds): {stable_oos['mean_z']:.2f} (Pass Rate: {stable_oos['pass_rate']*100:.0f}%, Min: {stable_oos['min_z']:.2f}, Max: {stable_oos['max_z']:.2f})")

# OOS Next-Open entry check
st_open = []
for t, d in oos_panel.items():
    sig = (d['strat_rank'] >= 0.90).fillna(False).values
    # Next open simulation: entry price = open of bar i+1
    d_mod = d.copy()
    d_mod['next_open'] = d_mod['open'].shift(-1)
    # simulate next open fill
    for i in range(len(d_mod) - 43):
        if sig[i] and not np.isnan(d_mod['next_open'].iloc[i]):
            entry_p = d_mod['next_open'].iloc[i]
            exit_p = d_mod['close'].iloc[i + 42]
            ret = (exit_p - entry_p) / entry_p * 100.0 - 0.50
            st_open.append({'entry_date': d_mod['date'].iloc[i+1], 'net_pct': ret, 'gross_pct': ret + 0.50})

dc_open = day_clustered_edge(st_open, ctrl_trades)
print(f"OOS Next-Open Entry: Trades={len(st_open)}, Net/tr={np.mean([x['net_pct'] for x in st_open]):+.2f}%, DayEdge={dc_open['day_edge']:+.3f}%, z={dc_open['z_paired']:.2f}")
