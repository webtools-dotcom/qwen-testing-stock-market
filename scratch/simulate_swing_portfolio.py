"""Realistic portfolio backtest for Volume-Dryup Pullback Swing Strategy.
20 equal-weight concurrent positions, cash-constrained, selective entry, 8-day / 10-day hold.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import numpy as np
import pandas as pd

print("Loading _master_flat.pkl...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

df['is_liquid_midsmall'] = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
df['dist_high52w'] = df['dist_high250']
df['sharpe60_rank'] = df.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))
df['comp_raw'] = (df['sharpe60_rank'] + df.groupby('date')['dist_high52w'].transform(lambda x: x.rank(pct=True))) / 2.0
df['comp_rank'] = df.groupby('date')['comp_raw'].transform(lambda x: x.rank(pct=True))

# Setup signal: Volume Dry-Up Pullback in Quality Trend Leaders
# S1: Sharpe60 >= 0.85 & ret3 < -1.0 & vol_ratio1 < 0.70 & close > sma_50
df['sig_s1'] = (df['sharpe60_rank'] >= 0.85) & (df['ret3'] < -1.0) & (df['vol_ratio1'] < 0.70) & (df['close'] > df['sma_50']) & df['is_liquid_midsmall']

# S2: Comp_rank >= 0.85 & ret3 < -1.0 & vol_ratio1 < 0.70 & close > sma_50
df['sig_s2'] = (df['comp_rank'] >= 0.85) & (df['ret3'] < -1.0) & (df['vol_ratio1'] < 0.70) & (df['close'] > df['sma_50']) & df['is_liquid_midsmall']

# Unique trading dates
all_dates = sorted(df['date'].unique())
dates_dt = pd.to_datetime(all_dates)

# Build date-indexed lookup
piv_close = df.pivot(index='date', columns='ticker', values='close')
piv_s1 = df.pivot(index='date', columns='ticker', values='sig_s1').fillna(False)
piv_s2 = df.pivot(index='date', columns='ticker', values='sig_s2').fillna(False)
piv_sharpe_rank = df.pivot(index='date', columns='ticker', values='sharpe60_rank').fillna(0)
piv_comp_rank = df.pivot(index='date', columns='ticker', values='comp_rank').fillna(0)

# Buy and hold benchmark of liquid universe
bh_daily = piv_close.pct_change().mean(axis=1).fillna(0)
bh_nav = (1 + bh_daily).cumprod()

def run_portfolio_sim(sig_piv, rank_piv, horizon=8, cost_rt=0.0050, n_slots=20):
    nav = 1.0
    cash = 1.0
    # positions: list of dicts: {'ticker': t, 'entry_price': p, 'entry_date': d, 'held': 0, 'weight': w, 'cost_basis': c}
    positions = []
    nav_history = []
    trade_log = []
    
    for dt in all_dates:
        curr_prices = piv_close.loc[dt]
        
        # 1. Update existing positions & check exits
        new_positions = []
        for pos in positions:
            t = pos['ticker']
            pos['held'] += 1
            curr_p = curr_prices.get(t, np.nan)
            
            if pos['held'] >= horizon or np.isnan(curr_p):
                # Exit position
                exit_p = curr_p if not np.isnan(curr_p) else pos['entry_price']
                ret = (exit_p - pos['entry_price']) / pos['entry_price']
                # Cost paid on exit
                cash_rec = pos['allocated_capital'] * (1 + ret) * (1 - cost_rt / 2.0)
                cash += cash_rec
                trade_log.append({
                    'ticker': t, 'entry_date': pos['entry_date'], 'exit_date': dt,
                    'gross_pct': ret * 100,
                    'net_pct': (ret - cost_rt) * 100
                })
            else:
                new_positions.append(pos)
        positions = new_positions
        
        # 2. Check candidate entries
        open_slots = n_slots - len(positions)
        if open_slots > 0 and cash > 0.01:
            today_sigs = sig_piv.loc[dt]
            candidates = today_sigs[today_sigs].index.tolist()
            # Exclude tickers already in positions
            current_tickers = {p['ticker'] for p in positions}
            candidates = [c for c in candidates if c not in current_tickers and not np.isnan(curr_prices.get(c, np.nan))]
            
            if candidates:
                # Rank candidates by score
                scores = rank_piv.loc[dt, candidates]
                sorted_cands = scores.sort_values(ascending=False).index.tolist()
                picked = sorted_cands[:open_slots]
                
                capital_per_slot = cash / (open_slots + (n_slots - open_slots)*0) # allocate available cash evenly across open slots up to 1/n_slots of current NAV
                target_alloc = min(cash / len(picked), (nav / n_slots))
                
                for t in picked:
                    entry_p = curr_prices[t]
                    alloc = min(target_alloc, cash)
                    if alloc > 0.001:
                        # Pay entry cost
                        alloc_net = alloc * (1 - cost_rt / 2.0)
                        cash -= alloc
                        positions.append({
                            'ticker': t, 'entry_price': entry_p, 'entry_date': dt,
                            'held': 0, 'allocated_capital': alloc_net
                        })
        
        # 3. Calculate portfolio NAV
        pos_val = sum(pos['allocated_capital'] * (curr_prices.get(pos['ticker'], pos['entry_price']) / pos['entry_price']) for pos in positions)
        nav = cash + pos_val
        nav_history.append({'date': dt, 'nav': nav})
        
    res_df = pd.DataFrame(nav_history).set_index('date')
    cagr = (res_df['nav'].iloc[-1] ** (252.0 / len(res_df)) - 1) * 100
    daily_ret = res_df['nav'].pct_change().dropna()
    sharpe_val = daily_ret.mean() / daily_ret.std() * np.sqrt(252) if daily_ret.std() > 0 else 0
    max_dd = (res_df['nav'] / res_df['nav'].cummax() - 1).min() * 100
    
    return {
        'cagr': cagr,
        'sharpe': sharpe_val,
        'max_dd': max_dd,
        'total_trades': len(trade_log),
        'trades_per_year': len(trade_log) / (len(res_df) / 252.0),
        'nav_series': res_df['nav'],
        'trade_log': trade_log
    }

bh_cagr = (bh_nav.iloc[-1] ** (252.0 / len(bh_nav)) - 1) * 100
bh_sharpe = bh_daily.mean() / bh_daily.std() * np.sqrt(252)
bh_max_dd = (bh_nav / bh_nav.cummax() - 1).min() * 100

print(f"\nBenchmark Buy & Hold: CAGR = +{bh_cagr:.2f}%, Sharpe = {bh_sharpe:.2f}, MaxDD = {bh_max_dd:.2f}%")

print("\n--- Portfolio Simulations (20 Slots) ---")
for name, sig_p, rank_p, h in [
    ("S1: Sharpe60 PB (h=8)", piv_s1, piv_sharpe_rank, 8),
    ("S1: Sharpe60 PB (h=10)", piv_s1, piv_sharpe_rank, 10),
    ("S2: Comp PB (h=8)", piv_s2, piv_comp_rank, 8),
    ("S2: Comp PB (h=10)", piv_s2, piv_comp_rank, 10),
]:
    p10 = run_portfolio_sim(sig_p, rank_p, horizon=h, cost_rt=0.0050)
    p15 = run_portfolio_sim(sig_p, rank_p, horizon=h, cost_rt=0.0075)
    p20 = run_portfolio_sim(sig_p, rank_p, horizon=h, cost_rt=0.0100)
    print(f"\nStrategy: {name}")
    print(f"  1.0x Costs (0.50% RT): CAGR = +{p10['cagr']:.2f}%, Sharpe = {p10['sharpe']:.2f}, MaxDD = {p10['max_dd']:.2f}%, Trades/yr = {p10['trades_per_year']:.1f}")
    print(f"  1.5x Costs (0.75% RT): CAGR = +{p15['cagr']:.2f}%, Sharpe = {p15['sharpe']:.2f}, MaxDD = {p15['max_dd']:.2f}%")
    print(f"  2.0x Costs (1.00% RT): CAGR = +{p20['cagr']:.2f}%, Sharpe = {p20['sharpe']:.2f}, MaxDD = {p20['max_dd']:.2f}%")
