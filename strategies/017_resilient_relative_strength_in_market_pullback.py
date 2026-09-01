"""Strategy 017 — Resilient Relative Strength in Market Pullback.

Hypothesis:
In liquid Indian equities (turnover >= Rs 25cr/day), when the broader market index experiences
a multi-day pullback (5-day market return <= -1.0%), stocks in a confirmed structural uptrend
(Close > SMA 50 and SMA 50 > SMA 200) that demonstrate strong relative strength divergence
(5-day return outperforming the market by >= 4.0%) reflect aggressive institutional accumulation
and supply absorption. When the broader market selling pressure abates, these resilient leaders
experience continuation momentum over the subsequent 6-10 trading days.

Run:  python strategies/017_resilient_relative_strength_in_market_pullback.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import numpy as np
import pandas as pd
from data_loader import get_panel
from backtest_engine import (
    simulate_trades, day_clustered_edge, edge_vs_control,
    stable_day_clustered_z, walk_forward_splits, deflated_sharpe,
    effective_trials, sharpe, report
)

UNIVERSE = [
    'ABB.NS', 'ABBOTINDIA.NS', 'ABCAPITAL.NS', 'ABFRL.NS', 'ACC.NS', 'ADANIENT.NS', 'ADANIPORTS.NS', 'ADANIPOWER.NS',
    'ALKEM.NS', 'AMBER.NS', 'AMBUJACEM.NS', 'APLAPOLLO.NS', 'APOLLOHOSP.NS', 'APOLLOTYRE.NS', 'ASHOKLEY.NS',
    'ASIANPAINT.NS', 'ASTRAL.NS', 'AUBANK.NS', 'AUROPHARMA.NS', 'AXISBANK.NS', 'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS',
    'BAJFINANCE.NS', 'BALKRISIND.NS', 'BANDHANBNK.NS', 'BANKBARODA.NS', 'BATAINDIA.NS', 'BEL.NS', 'BEML.NS',
    'BERGEPAINT.NS', 'BHARATFORG.NS', 'BHARTIARTL.NS', 'BHEL.NS', 'BIOCON.NS', 'BPCL.NS', 'BRITANNIA.NS',
    'BSE.NS', 'BSOFT.NS', 'CANBK.NS', 'CANFINHOME.NS', 'CDSL.NS', 'CHOLAFIN.NS', 'CIPLA.NS', 'COALINDIA.NS',
    'COFORGE.NS', 'COLPAL.NS', 'CONCOR.NS', 'COROMANDEL.NS', 'CROMPTON.NS', 'CUB.NS', 'CUMMINSIND.NS',
    'CYIENT.NS', 'DABUR.NS', 'DALBHARAT.NS', 'DEEPAKNTR.NS', 'DIVISLAB.NS', 'DIXON.NS', 'DLF.NS',
    'DRREDDY.NS', 'EICHERMOT.NS', 'GRASIM.NS', 'HCLTECH.NS', 'HDFCBANK.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS',
    'HINDUNILVR.NS', 'ICICIBANK.NS', 'INDUSINDBK.NS', 'INFY.NS', 'ITC.NS', 'JSWSTEEL.NS', 'KOTAKBANK.NS',
    'LALPATHLAB.NS', 'LT.NS', 'M&M.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'NTPC.NS', 'ONGC.NS', 'POWERGRID.NS',
    'RELIANCE.NS', 'SBILIFE.NS', 'SBIN.NS', 'SHRIRAMFIN.NS', 'SUNPHARMA.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS',
    'TCS.NS', 'TECHM.NS', 'TITAN.NS', 'TRENT.NS', 'ULTRACEMCO.NS', 'WIPRO.NS'
]

NIFTY_50 = {
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'SBIN.NS', 'AXISBANK.NS', 'LT.NS', 'ITC.NS',
    'HINDUNILVR.NS', 'MARUTI.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS', 'CIPLA.NS', 'DRREDDY.NS', 'WIPRO.NS',
    'TECHM.NS', 'HCLTECH.NS', 'BAJFINANCE.NS', 'ASIANPAINT.NS', 'ULTRACEMCO.NS', 'GRASIM.NS',
    'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'ADANIPORTS.NS', 'TITAN.NS', 'NESTLEIND.NS', 'BRITANNIA.NS',
    'DIVISLAB.NS', 'EICHERMOT.NS', 'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'BPCL.NS',
    'HEROMOTOCO.NS', 'HINDALCO.NS', 'INDUSINDBK.NS', 'KOTAKBANK.NS', 'M&M.NS', 'SBILIFE.NS',
    'SHRIRAMFIN.NS', 'TRENT.NS', 'APOLLOHOSP.NS'
}

HORIZON = 8
MIN_TURNOVER = 25e7
MKT_DROP_THRESH = -1.0
RS_THRESH = 4.0


def compute_market_proxy(panel):
    """Compute benchmark equal-weight market return series from large cap stocks."""
    large_dfs = [panel[t] for t in NIFTY_50 if t in panel]
    all_dates = sorted(list(set().union(*[set(df['date']) for df in panel.values()])))
    mkt_df = pd.DataFrame({'date': all_dates}).sort_values('date').reset_index(drop=True)
    mkt_rets = []
    for dt in mkt_df['date']:
        rets = []
        for df in large_dfs:
            sub = df[df['date'] == dt]
            if len(sub) > 0 and 'close' in sub.columns and 'open' in sub.columns:
                rets.append(sub['close'].values[0] / sub['open'].values[0] - 1)
        mkt_rets.append(np.mean(rets) if len(rets) > 5 else 0.0)
    mkt_df['mkt_ret_1d'] = mkt_rets
    mkt_df['mkt_close'] = (1 + mkt_df['mkt_ret_1d']).cumprod()
    mkt_df['mkt_ret_5d'] = mkt_df['mkt_close'].pct_change(5) * 100
    return mkt_df[['date', 'mkt_ret_5d']]


def enrich_features(panel, mkt_df):
    """Add relative strength features against the market proxy."""
    enriched = {}
    for ticker, df in panel.items():
        d = df.copy().sort_values('date').reset_index(drop=True)
        d = pd.merge(d, mkt_df, on='date', how='left')
        d['ret_5d'] = d['close'].pct_change(5) * 100
        d['rs_5d'] = d['ret_5d'] - d['mkt_ret_5d']
        enriched[ticker] = d
    return enriched


def signal_mask(d, mkt_drop_thresh=MKT_DROP_THRESH, rs_thresh=RS_THRESH):
    """Identify bars matching the resilient relative strength condition in uptrend."""
    uptrend = (d['close'] > d['sma_50']) & (d['sma_50'] > d['sma_200'])
    mkt_drop = d['mkt_ret_5d'] <= mkt_drop_thresh
    rs_strong = d['rs_5d'] >= rs_thresh
    return (uptrend & mkt_drop & rs_strong).values


def run():
    print(f"Loading {len(UNIVERSE)} names (5y)...")
    panel = get_panel(UNIVERSE, period="5y", cache_name="nifty_research_150_5y")
    print(f"Got {len(panel)} usable stocks\n")

    mkt_df = compute_market_proxy(panel)
    enriched_panel = enrich_features(panel, mkt_df)

    # 1. POOLED EVALUATION
    rng = np.random.default_rng(42)
    strat_pooled, ctrl_pooled = [], []
    for ticker, df in enriched_panel.items():
        d = df.dropna(subset=['close', 'atr', 'sma_200', 'mkt_ret_5d']).reset_index(drop=True)
        if len(d) < 300:
            continue
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        strat_pooled += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl_pooled  += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(report(f"Resilient RS in Market Pullback (POOLED, {HORIZON}d, costs charged)",
                 strat_pooled, ctrl_pooled, holding_days=HORIZON))

    def pooled_ctrl_fac(seed):
        trades = []
        r = np.random.default_rng(seed)
        for ticker, df in enriched_panel.items():
            d = df.dropna(subset=['close', 'atr', 'sma_200', 'mkt_ret_5d']).reset_index(drop=True)
            if len(d) < 300:
                continue
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (r.random(len(d)) < 0.08) & liq
            trades += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
        return trades

    stable_pooled = stable_day_clustered_z(strat_pooled, pooled_ctrl_fac, n_seeds=20)
    if stable_pooled:
        print(f"  STABLE MEAN z_paired (20 seeds): {stable_pooled['mean_z']:.2f} "
              f"(min {stable_pooled['min_z']:.2f}, max {stable_pooled['max_z']:.2f})")
        print(f"  PASS RATE (seeds with z >= 2.0) : {stable_pooled['pass_rate']*100:.1f}%\n")

    # 2. SUBGROUP ANALYSIS: Mid/Small Caps vs Large Caps (Section 8 Check)
    mid_small_tickers = [t for t in enriched_panel.keys() if t not in NIFTY_50]
    large_tickers = [t for t in enriched_panel.keys() if t in NIFTY_50]

    print("==================================================")
    print("SUBGROUP ANALYSIS (§8): Mid/Small vs Large Caps")
    print("==================================================")

    for scope_name, target_tickers in [("Mid/Small Caps", mid_small_tickers), ("Large Caps (Nifty 50)", large_tickers)]:
        strat_sub = []
        def sub_ctrl_fac(seed):
            trades = []
            r = np.random.default_rng(seed)
            for t in target_tickers:
                d = enriched_panel[t].dropna(subset=['close', 'atr', 'sma_200', 'mkt_ret_5d']).reset_index(drop=True)
                if len(d) < 300:
                    continue
                liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
                rnd = (r.random(len(d)) < 0.08) & liq
                trades += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
            return trades

        for t in target_tickers:
            d = enriched_panel[t].dropna(subset=['close', 'atr', 'sma_200', 'mkt_ret_5d']).reset_index(drop=True)
            if len(d) < 300:
                continue
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            sig = signal_mask(d) & liq
            strat_sub += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)

        ctrl_sub_sample = sub_ctrl_fac(42)
        print(report(f"Subgroup: {scope_name}", strat_sub, ctrl_sub_sample, holding_days=HORIZON))
        stable_sub = stable_day_clustered_z(strat_sub, sub_ctrl_fac, n_seeds=20)
        if stable_sub:
            print(f"  STABLE MEAN z_paired (20 seeds): {stable_sub['mean_z']:.2f} "
                  f"(min {stable_sub['min_z']:.2f}, max {stable_sub['max_z']:.2f})")
            print(f"  PASS RATE (seeds with z >= 2.0) : {stable_sub['pass_rate']*100:.1f}%\n")

    # 3. WALK-FORWARD 4-FOLD ANALYSIS (Mid/Small Caps)
    print("==================================================")
    print("WALK-FORWARD 4-FOLD ANALYSIS (Mid/Small Caps)")
    print("==================================================")
    sample_df = next(iter(enriched_panel.values())).dropna(subset=['close', 'atr', 'sma_200', 'mkt_ret_5d'])
    n_bars = len(sample_df)
    splits = list(walk_forward_splits(n_bars, n_splits=4, horizon_days=HORIZON))
    for fold_idx, (train_slice, test_slice) in enumerate(splits, 1):
        t_start, t_end = test_slice
        f_strat, f_ctrl = [], []
        r_f = np.random.default_rng(42 + fold_idx)
        for t in mid_small_tickers:
            d = enriched_panel[t].dropna(subset=['close', 'atr', 'sma_200', 'mkt_ret_5d']).reset_index(drop=True)
            if t_end > len(d):
                continue
            fold_df = d.iloc[t_start:t_end].reset_index(drop=True)
            liq = (fold_df['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            sig = signal_mask(fold_df) & liq
            rnd = (r_f.random(len(fold_df)) < 0.08) & liq
            f_strat += simulate_trades(fold_df, sig, horizon_days=HORIZON, charge_costs=True)
            f_ctrl += simulate_trades(fold_df, rnd, horizon_days=HORIZON, charge_costs=True)
        
        ev = edge_vs_control([t['net_pct'] for t in f_strat], [t['net_pct'] for t in f_ctrl])
        dc = day_clustered_edge(f_strat, f_ctrl)
        if ev and dc:
            print(f"  Fold {fold_idx} ({len(f_strat)} trades, {dc['n_paired_days']} paired days): "
                  f"Net avg {ev['strategy_avg']:+.2f}%, Net edge {ev['edge']:+.2f}%, "
                  f"z_paired {dc['z_paired']:+.2f}, day_edge {dc['day_edge']:+.2f}%")

    # 4. SENSITIVITY GRID
    print("\n==================================================")
    print("PARAMETER SENSITIVITY GRID (Mid/Small Caps)")
    print("==================================================")
    for mkt_th in [-0.5, -1.0, -1.5]:
        for rs_th in [3.0, 4.0, 5.0]:
            strat_trades = []
            for t in mid_small_tickers:
                d = enriched_panel[t].dropna(subset=['close', 'atr', 'sma_200', 'mkt_ret_5d']).reset_index(drop=True)
                liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
                sig = signal_mask(d, mkt_drop_thresh=mkt_th, rs_thresh=rs_th) & liq
                strat_trades += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
            
            def s_ctrl(seed):
                trades = []
                r = np.random.default_rng(seed)
                for t in mid_small_tickers:
                    d = enriched_panel[t].dropna(subset=['close', 'atr', 'sma_200', 'mkt_ret_5d']).reset_index(drop=True)
                    liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
                    rnd = (r.random(len(d)) < 0.08) & liq
                    trades += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
                return trades
            
            stable = stable_day_clustered_z(strat_trades, s_ctrl, n_seeds=10)
            print(f"  Mkt Drop <= {mkt_th:.1f}%, RS >= {rs_th:.1f}% -> Trades: {len(strat_trades):3d}, Mean z_paired: {stable['mean_z'] if stable else 0.0:+.2f}, Pass: {stable['pass_rate']*100 if stable else 0:.0f}%")


if __name__ == "__main__":
    run()
