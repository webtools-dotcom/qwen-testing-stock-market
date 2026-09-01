"""Comprehensive validation of Strategy 029: Regime-Protected 52-Week High Trend Compounder.
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

# 1. Features
d['dist_52w'] = d['dist_high250'] # proximity to 52w high

# 252-day t-statistic of trend
d['ret1_std252'] = d.groupby('ticker')['ret1'].transform(lambda x: x.rolling(252).std())
d['ret1_mean252'] = d.groupby('ticker')['ret1'].transform(lambda x: x.rolling(252).mean())
d['t_stat_252'] = (d['ret1_mean252'] / (d['ret1_std252'] + 1e-6)) * np.sqrt(252)

# Cross-sectional ranks
d['rank_52w'] = d.groupby('date')['dist_52w'].transform(lambda x: x.rank(pct=True))
d['rank_tstat'] = d.groupby('date')['t_stat_252'].transform(lambda x: x.rank(pct=True))

# Composite Score
d['composite'] = 0.5 * d['rank_52w'] + 0.5 * d['rank_tstat']
d['composite_rank'] = d.groupby('date')['composite'].transform(lambda x: x.rank(pct=True))

# Market Regime Filter: % of liquid mid/small caps above 50 SMA
d['above_50'] = d['close'] > d['sma_50']
breadth = d.groupby('date')['above_50'].mean()
d['mkt_breadth'] = d['date'].map(breadth)
d['regime_ok'] = d['mkt_breadth'] >= 0.35 # sit in cash only during severe broad market breakdowns

# Signal: Composite Top Decile (>= 0.90) + Regime OK + Close > SMA50
d['sig'] = (d['composite_rank'] >= 0.90) & (d['close'] > d['sma_50']) & d['regime_ok']

pre2017_set = set(df[df['date'] <= '2017-01-01']['ticker'].unique())
panel = {t: grp.sort_values('date').reset_index(drop=True) for t, grp in d.groupby('ticker')}

rng = np.random.default_rng(42)
strat_trades, ctrl_trades = [], []
strat_B, ctrl_B = [], []
strat_pre, ctrl_pre = [], []

for t, data in panel.items():
    if len(data) < 300: continue
    sig = data['sig'].fillna(False).values
    liq = data['is_liquid_midsmall'].fillna(False).values
    
    st = simulate_trades(data, sig, horizon_days=42, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
    strat_trades += st
    ct = simulate_trades(data, (rng.random(len(data)) < 0.10) & liq, horizon_days=42, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
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

def cf_pool(seed):
    r = np.random.default_rng(seed)
    return [item for t_c, data in panel.items() if len(data) >= 300
            for item in simulate_trades(data, (r.random(len(data)) < 0.10) & data['is_liquid_midsmall'].fillna(False).values, horizon_days=42, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)]

def cf_B(seed):
    r = np.random.default_rng(seed)
    return [item for t_c, data in panel.items() if len(data) >= 300 and data['half'].iloc[0]=='B'
            for item in simulate_trades(data, (r.random(len(data)) < 0.10) & data['is_liquid_midsmall'].fillna(False).values, horizon_days=42, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)]

def cf_pre(seed):
    r = np.random.default_rng(seed)
    return [item for t_c, data in panel.items() if len(data) >= 300 and t_c in pre2017_set
            for item in simulate_trades(data, (r.random(len(data)) < 0.10) & data['is_liquid_midsmall'].fillna(False).values, horizon_days=42, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)]

stable_pool = stable_day_clustered_z(strat_trades, cf_pool, n_seeds=20)
stable_B = stable_day_clustered_z(strat_B, cf_B, n_seeds=20)
stable_pre = stable_day_clustered_z(strat_pre, cf_pre, n_seeds=20)

net_avg = np.mean([x['net_pct'] for x in strat_trades])

print("="*80)
print("STRATEGY 029 CANDIDATE: REGIME-PROTECTED 52W HIGH TREND COMPOUNDER")
print("="*80)
print(f"Trades (non-overlapping): {len(strat_trades)} | Paired Days: {dc_pool['n_days']}")
print(f"Gross avg return/trade: {np.mean([x['gross_pct'] for x in strat_trades]):+.3f}% | Net avg return/trade: {net_avg:+.3f}%")
print(f"Day Edge (Seed 42): {dc_pool['day_edge']:+.3f}% | Single z_paired: {dc_pool['z_paired']:.2f}")
print(f"POOLED Stable Mean z_paired (20 seeds): {stable_pool['mean_z']:.2f} (Pass Rate: {stable_pool['pass_rate']*100:.0f}%, Min: {stable_pool['min_z']:.2f}, Max: {stable_pool['max_z']:.2f})")
print(f"HOLDOUT HALF B Stable Mean z_paired: {stable_B['mean_z']:.2f} (Pass Rate: {stable_B['pass_rate']*100:.0f}%)")
print(f"PRE-2017 LISTINGS Stable Mean z_paired: {stable_pre['mean_z']:.2f} (Pass Rate: {stable_pre['pass_rate']*100:.0f}%)")

# Decile Ladder
print("\n--- Decile Ladder ---")
for q in [0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20, 0.10, 0.00]:
    q_high = q + 0.10 if q < 0.90 else 1.01
    st_q = []
    for t, data in panel.items():
        if len(data) < 300: continue
        sig_q = (data['composite_rank'] >= q) & (data['composite_rank'] < q_high) & (data['close'] > data['sma_50'])
        st_q += simulate_trades(data, sig_q.fillna(False).values, horizon_days=42, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
    dc_q = day_clustered_edge(st_q, ctrl_trades)
    print(f"Decile [{q*100:2.0f}% - {q_high*100:2.0f}%]: Trades={len(st_q):4d}, Net/tr={np.mean([x['net_pct'] for x in st_q]):+.2f}%, DayEdge={dc_q['day_edge']:+.3f}%, z={dc_q['z_paired']:.2f}")

# Next-Open Execution Check
print("\n--- Execution Fragility: Next-Open Fill ---")
st_open = []
for t, data in panel.items():
    if len(data) < 300: continue
    sig = data['sig'].fillna(False).values
    st_open += simulate_trades(data, sig, horizon_days=42, entry_on_open=True, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
dc_open = day_clustered_edge(st_open, ctrl_trades)
stable_open = stable_day_clustered_z(st_open, cf_pool, n_seeds=10)
print(f"Next-Open Entry: Trades={len(st_open)}, Net/tr={np.mean([x['net_pct'] for x in st_open]):+.2f}%, DayEdge={dc_open['day_edge']:+.3f}%, Stable Mean z={stable_open['mean_z']:.2f} ({stable_open['pass_rate']*100:.0f}% pass)")

# 20-Slot Cash-Constrained Portfolio Simulation (1.0x, 1.5x, 2.0x costs)
print("\n--- 20-Slot Portfolio Simulation ---")
piv_close = df.pivot(index='date', columns='ticker', values='close')
all_dates = sorted(df['date'].unique())

sig_dict = {}
rank_dict = {}
for dt, grp in d.groupby('date'):
    sub_sig = (grp['composite_rank'] >= 0.90) & (grp['close'] > grp['sma_50']) & (grp['mkt_breadth'] >= 0.35)
    sig_dict[dt] = set(grp[sub_sig]['ticker'])
    rank_dict[dt] = grp.set_index('ticker')['composite_rank'].to_dict()

def sim_port(cost_rt=0.0050, n_slots=20, horizon=42):
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
        today_cands = [c for c in sig_dict.get(dt, set()) if c not in {p['ticker'] for p in positions} and not np.isnan(curr_prices.get(c, np.nan))]
        if open_slots > 0 and cash > 0.01 and today_cands:
            today_ranks = rank_dict.get(dt, {})
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
    return {'cagr': cagr, 'sharpe': sharpe_val, 'max_dd': max_dd, 'trades_yr': trade_count / (len(res_df)/252.0), 'df': res_df}

p10 = sim_port(cost_rt=0.0050)
p15 = sim_port(cost_rt=0.0075)
p20 = sim_port(cost_rt=0.0100)

bh_daily = piv_close.pct_change().mean(axis=1).fillna(0)
bh_nav = (1 + bh_daily).cumprod()
bh_cagr = (bh_nav.iloc[-1] ** (252.0 / len(bh_nav)) - 1) * 100
bh_sharpe = bh_daily.mean() / bh_daily.std() * np.sqrt(252)
bh_max_dd = (bh_nav / bh_nav.cummax() - 1).min() * 100

print(f"Benchmark Equal-Weight Universe Buy & Hold: CAGR = +{bh_cagr:.2f}%, Sharpe = {bh_sharpe:.2f}, MaxDD = {bh_max_dd:.2f}%")
print(f"Strategy 029 (1.0x costs, 0.50% RT): CAGR = +{p10['cagr']:.2f}%, Sharpe = {p10['sharpe']:.2f}, MaxDD = {p10['max_dd']:.2f}%, Trades/yr = {p10['trades_yr']:.1f}")
print(f"Strategy 029 (1.5x costs, 0.75% RT): CAGR = +{p15['cagr']:.2f}%, Sharpe = {p15['sharpe']:.2f}, MaxDD = {p15['max_dd']:.2f}%")
print(f"Strategy 029 (2.0x costs, 1.00% RT): CAGR = +{p20['cagr']:.2f}%, Sharpe = {p20['sharpe']:.2f}, MaxDD = {p20['max_dd']:.2f}%")

# Calendar year breakdown
p_df = p10['df'].copy()
p_df['year'] = pd.to_datetime(p_df.index).year
y_strat = p_df.groupby('year')['nav'].apply(lambda x: (x.iloc[-1]/x.iloc[0] - 1)*100)

bh_df = pd.DataFrame({'nav': bh_nav, 'year': pd.to_datetime(bh_nav.index).year})
y_bh = bh_df.groupby('year')['nav'].apply(lambda x: (x.iloc[-1]/x.iloc[0] - 1)*100)

print("\n--- Calendar Year Returns ---")
y_comb = pd.DataFrame({'Strategy 029': y_strat, 'Buy & Hold': y_bh})
y_comb['Excess'] = y_comb['Strategy 029'] - y_comb['Buy & Hold']
print(y_comb.round(2).to_string())
