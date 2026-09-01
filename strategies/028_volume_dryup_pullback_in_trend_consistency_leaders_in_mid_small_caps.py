"""Strategy 028 — Volume-Dryup Pullback in Trend Consistency Leaders in Mid-Small Caps.

Tests whether volume-dryup pullbacks in high-Sharpe trend leaders produce a robust 6-10 day swing edge.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import numpy as np
import pandas as pd
from scipy import stats
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z, 
    report, walk_forward_splits, sharpe, deflated_sharpe
)

print("Loading master flat dataset (10y NSE mid/small panel)...")
with open("cache/_master_flat.pkl", "rb") as f:
    df = pickle.load(f)

# Filter universe: liquid mid/small caps
df['is_liquid_midsmall'] = (df['turnover_60d'] >= 25e7) & (df['mid_small'] == True)
df['dist_high52w'] = df['dist_high250']

# Compute cross-sectional ranks by date
df['sharpe60_rank'] = df.groupby('date')['sharpe60'].transform(lambda x: x.rank(pct=True))

# Signal function: Quality Trend + Pullback + Volume Dryup > SMA50
def get_signal_mask(d, sharpe_q=0.85, pb_thresh=-1.0, vol_thresh=0.70):
    return (
        (d['sharpe60_rank'] >= sharpe_q) & 
        (d['ret3'] < pb_thresh) & 
        (d['vol_ratio1'] < vol_thresh) & 
        (d['close'] > d['sma_50']) & 
        d['is_liquid_midsmall']
    )

# Re-group by ticker
panel = {t: grp.sort_values('date').reset_index(drop=True) for t, grp in df.groupby('ticker')}

def run_backtest():
    print("\n" + "="*70)
    print("STRATEGY 028 — VOLUME-DRYUP PULLBACK IN TREND LEADERS (MID/SMALL CAPS)")
    print("="*70)
    
    # 1. Headline Engine Statistics (Baseline: h=8 sessions, time exit)
    rng = np.random.default_rng(42)
    strat_trades, ctrl_trades = [], []
    per_ticker_sig = {}
    per_ticker_liq = {}
    
    for t, d in panel.items():
        if len(d) < 300:
            continue
        liq = d['is_liquid_midsmall'].fillna(False).values
        sig = get_signal_mask(d).values
        per_ticker_sig[t] = sig
        per_ticker_liq[t] = liq
        
        st = simulate_trades(d, sig, horizon_days=8, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        strat_trades += st
        
        ctrl_mask = (rng.random(len(d)) < 0.10) & liq
        ct = simulate_trades(d, ctrl_mask, horizon_days=8, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        ctrl_trades += ct
        
    print("\n--- 1. Headline Engine Report (8-Session Hold) ---")
    print(report("Strategy 028 (h=8 Time Exit)", strat_trades, ctrl_trades, holding_days=8))
    
    def ctrl_factory(seed):
        r = np.random.default_rng(seed)
        c_trades = []
        for t, d in panel.items():
            if t not in per_ticker_liq:
                continue
            liq = per_ticker_liq[t]
            ctrl_mask = (r.random(len(d)) < 0.10) & liq
            c_trades += simulate_trades(d, ctrl_mask, horizon_days=8, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        return c_trades

    stable = stable_day_clustered_z(strat_trades, ctrl_factory, n_seeds=20)
    print(f"POOLED Stable Control (20 seeds): Mean z_paired = {stable['mean_z']:.2f} (min {stable['min_z']:.2f}, max {stable['max_z']:.2f}), Pass Rate = {stable['pass_rate']*100:.1f}%")

    # 2. Hold-out Half B of Names
    strat_B, ctrl_B = [], []
    for t, d in panel.items():
        if len(d) < 300 or d['half'].iloc[0] != 'B':
            continue
        liq = d['is_liquid_midsmall'].fillna(False).values
        sig = get_signal_mask(d).values
        strat_B += simulate_trades(d, sig, horizon_days=8, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        ctrl_B += simulate_trades(d, (rng.random(len(d)) < 0.10) & liq, horizon_days=8, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        
    def ctrl_factory_B(seed):
        r = np.random.default_rng(seed)
        c_trades = []
        for t, d in panel.items():
            if len(d) < 300 or d['half'].iloc[0] != 'B':
                continue
            liq = d['is_liquid_midsmall'].fillna(False).values
            c_trades += simulate_trades(d, (r.random(len(d)) < 0.10) & liq, horizon_days=8, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        return c_trades
        
    stable_B = stable_day_clustered_z(strat_B, ctrl_factory_B, n_seeds=20)
    dc_B = day_clustered_edge(strat_B, ctrl_B)
    print(f"\nHoldout Half B: Trades={len(strat_B)}, Seed 42 z_paired={dc_B['z_paired']:.2f}, Stable Mean z_paired = {stable_B['mean_z']:.2f} (Pass Rate = {stable_B['pass_rate']*100:.1f}%)")

    # 3. Pre-2017 Listings Alone (Survivorship test)
    pre2017_tickers = set(df[df['date'] <= '2017-01-01']['ticker'].unique())
    strat_pre, ctrl_pre = [], []
    for t, d in panel.items():
        if t not in pre2017_tickers or len(d) < 300:
            continue
        liq = d['is_liquid_midsmall'].fillna(False).values
        sig = get_signal_mask(d).values
        strat_pre += simulate_trades(d, sig, horizon_days=8, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        ctrl_pre += simulate_trades(d, (rng.random(len(d)) < 0.10) & liq, horizon_days=8, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        
    def ctrl_factory_pre(seed):
        r = np.random.default_rng(seed)
        c_trades = []
        for t, d in panel.items():
            if t not in pre2017_tickers or len(d) < 300:
                continue
            liq = d['is_liquid_midsmall'].fillna(False).values
            c_trades += simulate_trades(d, (r.random(len(d)) < 0.10) & liq, horizon_days=8, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        return c_trades

    stable_pre = stable_day_clustered_z(strat_pre, ctrl_factory_pre, n_seeds=20)
    dc_pre = day_clustered_edge(strat_pre, ctrl_pre)
    print(f"\nPre-2017 Listings Only ({len(pre2017_tickers)} names): Trades={len(strat_pre)}, Seed 42 z_paired={dc_pre['z_paired']:.2f}, Stable Mean z_paired = {stable_pre['mean_z']:.2f} (Pass Rate = {stable_pre['pass_rate']*100:.1f}%)")

    # 4. Holding Period Sensitivity
    print("\n--- 2. Holding Period Sensitivity (±1 Step) ---")
    for h in [6, 8, 10, 12]:
        st_h, ct_h = [], []
        for t, d in panel.items():
            if len(d) < 300: continue
            liq = d['is_liquid_midsmall'].fillna(False).values
            sig = get_signal_mask(d).values
            st_h += simulate_trades(d, sig, horizon_days=h, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
            ct_h += simulate_trades(d, (rng.random(len(d)) < 0.10) & liq, horizon_days=h, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
        
        def cf_h(seed):
            r = np.random.default_rng(seed)
            return [t_item for t_code, d in panel.items() if len(d) >= 300
                    for t_item in simulate_trades(d, (r.random(len(d)) < 0.10) & d['is_liquid_midsmall'].fillna(False).values, horizon_days=h, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)]
        sc_h = stable_day_clustered_z(st_h, cf_h, n_seeds=10)
        dc_h = day_clustered_edge(st_h, ct_h)
        print(f"  Horizon {h:2d} sessions: Trades={len(st_h):4d} | Net/tr={np.mean([x['net_pct'] for x in st_h]):+.3f}% | DayEdge={dc_h['day_edge']:+.3f}% | Stable z_paired={sc_h['mean_z']:.2f} ({sc_h['pass_rate']*100:.0f}%)")

    # 5. Parameter Sensitivity Matrix (Plateau vs Spike check)
    print("\n--- 3. Parameter Sensitivity Matrix (Plateau Check) ---")
    for sq in [0.80, 0.85, 0.90]:
        for vt in [0.60, 0.70, 0.80]:
            for pb in [-0.5, -1.0, -1.5]:
                st_p, ct_p = [], []
                for t, d in panel.items():
                    if len(d) < 300: continue
                    liq = d['is_liquid_midsmall'].fillna(False).values
                    sig = get_signal_mask(d, sharpe_q=sq, pb_thresh=pb, vol_thresh=vt).values
                    st_p += simulate_trades(d, sig, horizon_days=8, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
                    ct_p += simulate_trades(d, (rng.random(len(d)) < 0.10) & liq, horizon_days=8, stop_atr_mult=999.0, target_atr_mult=999.0, charge_costs=True, allow_overlap=False)
                dc_p = day_clustered_edge(st_p, ct_p)
                if dc_p and len(st_p) > 100:
                    print(f"  Sharpe Top {int((1-sq)*100)}% | Vol < {vt:.2f} | PB < {pb:+.1f}%: Trades={len(st_p):4d} | Net={np.mean([x['net_pct'] for x in st_p]):+.2f}% | z_paired={dc_p['z_paired']:.2f} | DayEdge={dc_p['day_edge']:+.3f}%")

    # 6. Next-Session Entry Fill Check (Execution Fragility)
    strat_nxt = []
    for t, d in panel.items():
        if len(d) < 300: continue
        liq = d['is_liquid_midsmall'].fillna(False).values
        sig = get_signal_mask(d).values
        n = len(d)
        close = d['close'].values
        open_ = d['open'].values
        last_exit = -1
        for i in np.where(sig)[0]:
            if i >= n - 9: break
            if i <= last_exit: continue
            nxt_open = open_[i+1]
            exit_close = close[i+8]
            gross = (exit_close - nxt_open) / nxt_open * 100
            cost = 0.50
            strat_nxt.append({
                'entry_idx': i+1, 'exit_idx': i+8, 'entry_date': d['date'].iat[i+1],
                'gross_pct': gross, 'net_pct': gross - cost, 'cost_pct': cost
            })
            last_exit = i+8
    
    ctrl_nxt = []
    for t, d in panel.items():
        if len(d) < 300: continue
        liq = d['is_liquid_midsmall'].fillna(False).values
        rnd = (rng.random(len(d)) < 0.10) & liq
        n = len(d)
        close = d['close'].values
        open_ = d['open'].values
        last_exit = -1
        for i in np.where(rnd)[0]:
            if i >= n - 9: break
            if i <= last_exit: continue
            nxt_open = open_[i+1]
            exit_close = close[i+8]
            gross = (exit_close - nxt_open) / nxt_open * 100
            cost = 0.50
            ctrl_nxt.append({
                'entry_idx': i+1, 'exit_idx': i+8, 'entry_date': d['date'].iat[i+1],
                'gross_pct': gross, 'net_pct': gross - cost, 'cost_pct': cost
            })
            last_exit = i+8
            
    dc_nxt = day_clustered_edge(strat_nxt, ctrl_nxt)
    print(f"\nNext-Session Entry (Next Open Fill): Trades={len(strat_nxt)}, Net={np.mean([x['net_pct'] for x in strat_nxt]):+.3f}%, Day Edge={dc_nxt['day_edge']:+.3f}%, z_paired={dc_nxt['z_paired']:.2f}")

    # 7. Walk-Forward Folds (Purged & Embargoed)
    print("\n--- 4. Chronological Walk-Forward Folds ---")
    dates_sorted = np.array(sorted(df['date'].unique()))
    n_total_dates = len(dates_sorted)
    fold_zs = []
    for f_idx, ((tr0, tr1), (te0, te1)) in enumerate(walk_forward_splits(n_total_dates, n_splits=4, horizon_days=8)):
        test_dates = set(dates_sorted[te0:te1])
        st_fold = [t_item for t_item in strat_trades if t_item['entry_date'] in test_dates]
        ct_fold = [t_item for t_item in ctrl_trades if t_item['entry_date'] in test_dates]
        dc_fold = day_clustered_edge(st_fold, ct_fold)
        z_f = dc_fold['z_paired'] if dc_fold else 0.0
        edge_f = dc_fold['day_edge'] if dc_fold else 0.0
        fold_zs.append(z_f)
        d_start = dates_sorted[te0].strftime('%Y-%m')
        d_end = dates_sorted[min(te1-1, n_total_dates-1)].strftime('%Y-%m')
        print(f"  Fold {f_idx+1} ({d_start} to {d_end}): Trades={len(st_fold):3d} | Day Edge={edge_f:+.3f}% | z_paired={z_f:+.2f}")
    
    print(f"  Mean Fold z: {np.mean(fold_zs):.2f}, Fold z spread: {np.std(fold_zs):.2f}")

    # 8. Portfolio Simulation & Cost Stress Test
    print("\n--- 5. The Portfolio Tool Test (20 Concurrent Slots) ---")
    piv_close = df.pivot(index='date', columns='ticker', values='close')
    all_dates = sorted(df['date'].unique())
    
    sig_series = {}
    rank_series = {}
    for dt, grp in df.groupby('date'):
        sub_sig = get_signal_mask(grp)
        sig_series[dt] = set(grp[sub_sig]['ticker'])
        rank_series[dt] = grp.set_index('ticker')['sharpe60_rank'].to_dict()
        
    def sim_portfolio(cost_rt=0.0050, n_slots=20, horizon=8):
        cash = 1.0
        positions = []
        nav_hist = []
        trade_count = 0
        
        for dt in all_dates:
            curr_prices = piv_close.loc[dt]
            
            # 1. Update positions & exits
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
            
            # 2. Check candidate entries
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
        return {'cagr': cagr, 'sharpe': sharpe_val, 'max_dd': max_dd, 'trades_yr': trade_count / (len(res_df)/252.0), 'nav': res_df['nav']}

    bh_daily = piv_close.pct_change().mean(axis=1).fillna(0)
    bh_nav = (1 + bh_daily).cumprod()
    bh_cagr = (bh_nav.iloc[-1] ** (252.0 / len(bh_nav)) - 1) * 100
    bh_sharpe = bh_daily.mean() / bh_daily.std() * np.sqrt(252)
    bh_max_dd = (bh_nav / bh_nav.cummax() - 1).min() * 100
    
    p10 = sim_portfolio(cost_rt=0.0050)
    p15 = sim_portfolio(cost_rt=0.0075)
    p20 = sim_portfolio(cost_rt=0.0100)
    
    print(f"  Benchmark Equal-Weight Universe Buy & Hold: CAGR = +{bh_cagr:.2f}%, Sharpe = {bh_sharpe:.2f}, MaxDD = {bh_max_dd:.2f}%")
    print(f"  Strategy 028 (1.0x costs, 0.50% RT): CAGR = +{p10['cagr']:.2f}%, Sharpe = {p10['sharpe']:.2f}, MaxDD = {p10['max_dd']:.2f}%, Trades/yr = {p10['trades_yr']:.1f}")
    print(f"  Strategy 028 (1.5x costs, 0.75% RT): CAGR = +{p15['cagr']:.2f}%, Sharpe = {p15['sharpe']:.2f}, MaxDD = {p15['max_dd']:.2f}%")
    print(f"  Strategy 028 (2.0x costs, 1.00% RT): CAGR = +{p20['cagr']:.2f}%, Sharpe = {p20['sharpe']:.2f}, MaxDD = {p20['max_dd']:.2f}%")

if __name__ == "__main__":
    run_backtest()
