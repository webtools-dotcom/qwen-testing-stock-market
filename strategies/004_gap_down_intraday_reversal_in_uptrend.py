"""Strategy 004 — Gap-Down Intraday Reversal in Structural Uptrend.

Hypothesis:
In liquid NSE equities (turnover >= ₹25cr/day), when an overnight sentiment shock causes a stock
in an established long-term uptrend (Close > SMA 200) to open with a significant gap-down (Open <= Close[1] * 0.985),
intraday institutional absorption that drives the close above the open and into the upper portion of the
daily range ((Close - Low) / (High - Low) >= 0.60) signals liquidity exhaustion of panicked retail sellers,
creating a 6-10 day mean-reversion swing opportunity.

Run:  python strategies/004_gap_down_intraday_reversal_in_uptrend.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from data_loader import get_panel
from backtest_engine import (
    simulate_trades, day_clustered_edge, edge_vs_control,
    stable_day_clustered_z, walk_forward_splits, deflated_sharpe,
    effective_trials, sharpe, report
)

UNIVERSE = [
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'AXISBANK.NS',
    'LT.NS', 'ITC.NS', 'HINDUNILVR.NS', 'MARUTI.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS',
    'SUNPHARMA.NS', 'CIPLA.NS', 'DRREDDY.NS', 'WIPRO.NS', 'TECHM.NS', 'HCLTECH.NS', 'BAJFINANCE.NS',
    'ASIANPAINT.NS', 'ULTRACEMCO.NS', 'GRASIM.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'COALINDIA.NS',
    'ADANIPORTS.NS', 'TITAN.NS', 'NESTLEIND.NS', 'BRITANNIA.NS', 'DIVISLAB.NS', 'EICHERMOT.NS',
    'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'BPCL.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS',
    'INDUSINDBK.NS', 'KOTAKBANK.NS', 'M&M.NS', 'SBILIFE.NS', 'SHRIRAMFIN.NS', 'TRENT.NS', 'APOLLOHOSP.NS',
    'ABB.NS', 'ABBOTINDIA.NS', 'ABCAPITAL.NS', 'ABFRL.NS', 'ACC.NS', 'ADANIENT.NS', 'ADANIPOWER.NS',
    'ALKEM.NS', 'AMBER.NS', 'AMBUJACEM.NS', 'APLAPOLLO.NS', 'APOLLOTYRE.NS', 'ASHOKLEY.NS', 'ASTRAL.NS',
    'AUBANK.NS', 'AUROPHARMA.NS', 'BALKRISIND.NS', 'BANDHANBNK.NS', 'BANKBARODA.NS', 'BATAINDIA.NS',
    'BEL.NS', 'BEML.NS', 'BERGEPAINT.NS', 'BHARATFORG.NS', 'BHEL.NS', 'BIOCON.NS', 'BSE.NS', 'BSOFT.NS',
    'CANBK.NS', 'CANFINHOME.NS', 'CDSL.NS', 'CHOLAFIN.NS', 'COFORGE.NS', 'COLPAL.NS', 'CONCOR.NS',
    'COROMANDEL.NS', 'CROMPTON.NS', 'CUB.NS', 'CUMMINSIND.NS', 'CYIENT.NS', 'DABUR.NS', 'DALBHARAT.NS',
    'DEEPAKNTR.NS', 'DIXON.NS', 'DLF.NS', 'LALPATHLAB.NS'
]

HORIZON = 7
MIN_TURNOVER = 25e7
GAP_PCT = 0.015       # 1.5% gap down below prior close
RANGE_POS_MIN = 0.60  # close in top 40% of daily range


def signal_mask(d, gap_pct=GAP_PCT, range_pos_min=RANGE_POS_MIN):
    """Gap down at open + intraday absorption closing near high + long-term uptrend."""
    prev_close = d['close'].shift(1)
    gap_down = (d['open'] <= prev_close * (1 - gap_pct))
    bar_range = (d['high'] - d['low']).replace(0, np.nan)
    pos_in_range = (d['close'] - d['low']) / bar_range
    bullish_close = (d['close'] > d['open']) & (pos_in_range >= range_pos_min)
    uptrend = (d['close'] > d['sma_200'])
    return (gap_down & bullish_close & uptrend).fillna(False).values


def run():
    print(f"Loading panel for {len(UNIVERSE)} liquid NSE stocks (5y)...")
    panel = get_panel(UNIVERSE, period="5y", cache_name="nifty_research_150_5y")
    print(f"Loaded {len(panel)} usable stock series.\n")

    valid_dfs = []
    for ticker, df in panel.items():
        d = df.dropna(subset=['rsi', 'atr', 'close', 'sma_200']).reset_index(drop=True)
        if len(d) >= 300:
            valid_dfs.append(d)

    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    for d in valid_dfs:
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(report(f"Strategy 004: Gap-Down Intraday Reversal ({HORIZON}d hold, costs charged)", strat, ctrl, holding_days=HORIZON))

    dc = day_clustered_edge(strat, ctrl)
    print("\n--- DAY-CLUSTERED SINGLE-DRAW HEADLINE ---")
    if dc:
        print(f"  z_paired = {dc['z_paired']:.2f}, paired_days = {dc['n_paired_days']}, day_edge = {dc['day_edge']:+.3f}%")

    # Stable 20-seed control
    def control_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for d in valid_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
        return c_trades

    stable = stable_day_clustered_z(strat, control_factory, n_seeds=20)
    print("\n--- STABLE 20-SEED DAY-CLUSTERED CONTROL (METHODOLOGY RULE) ---")
    if stable:
        print(f"  mean_z: {stable['mean_z']:.2f} | min_z: {stable['min_z']:.2f} | max_z: {stable['max_z']:.2f} | pass_rate: {stable['pass_rate']*100:.1f}% (n_seeds={stable['n_seeds']})")

    # Walk-forward validation
    sample_len = len(valid_dfs[0])
    splits = list(walk_forward_splits(sample_len, n_splits=4, horizon_days=HORIZON))
    print(f"\n--- WALK-FORWARD VALIDATION ({len(splits)} purged folds) ---")
    for fold_idx, ((tr0, tr1), (te0, te1)) in enumerate(splits, 1):
        f_rng = np.random.default_rng(42 + fold_idx)
        f_strat, f_ctrl = [], []
        for d in valid_dfs:
            test_df = d.iloc[te0:te1].reset_index(drop=True)
            if len(test_df) < HORIZON + 2:
                continue
            liq = (test_df['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            sig = signal_mask(test_df) & liq
            rnd = (f_rng.random(len(test_df)) < 0.08) & liq
            f_strat += simulate_trades(test_df, sig, horizon_days=HORIZON, charge_costs=True)
            f_ctrl += simulate_trades(test_df, rnd, horizon_days=HORIZON, charge_costs=True)

        f_res = edge_vs_control([t['net_pct'] for t in f_strat], [t['net_pct'] for t in f_ctrl])
        f_dc = day_clustered_edge(f_strat, f_ctrl)
        net_edge = f_res['edge'] if f_res else 0.0
        zp = f_dc['z_paired'] if f_dc else 0.0
        print(f"  Fold {fold_idx} ({te0}:{te1}): trades={len(f_strat):3d}, net_edge={net_edge:+.2f}%, z_paired={zp:+.2f}")

    # Parameter sensitivity grid
    print("\n--- PARAMETER SENSITIVITY GRID ---")
    gap_tests = [0.010, 0.015, 0.020]
    pos_tests = [0.50, 0.60, 0.70]
    all_srs = []
    trial_rets = []
    
    print(f"{'Gap %':<8} {'Pos Ratio':<10} {'Trades':<8} {'Net Avg%':<10} {'z_naive':<10} {'z_paired':<10}")
    for g in gap_tests:
        for p in pos_tests:
            s_tr = []
            for d in valid_dfs:
                liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
                sig = signal_mask(d, gap_pct=g, range_pos_min=p) & liq
                s_tr += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
            
            s_rets = [t['net_pct'] for t in s_tr]
            trial_rets.append(s_rets)
            sr = sharpe(s_rets, holding_days=HORIZON)
            all_srs.append(sr)
            
            res = edge_vs_control(s_rets, [t['net_pct'] for t in ctrl])
            dc_t = day_clustered_edge(s_tr, ctrl)
            n_t = len(s_tr)
            net_avg = np.mean(s_rets) if s_rets else 0.0
            z_n = res['z'] if res else 0.0
            z_p = dc_t['z_paired'] if dc_t else 0.0
            print(f"{g*100:<8.1f} {p:<10.2f} {n_t:<8d} {net_avg:<+10.3f} {z_n:<10.2f} {z_p:<10.2f}")

    eff_trials = effective_trials(trial_rets)
    dsr = deflated_sharpe(max(all_srs), all_srs, n_obs=len(strat))
    print(f"\nEffective trials: {eff_trials:.2f} (from {len(all_srs)} grid points)")
    if dsr:
        print(f"Deflated Sharpe: DSR = {dsr['dsr']:.4f} (Observed SR: {dsr['observed_sr']:.2f}, Noise ceiling: {dsr['noise_ceiling_sr']:.2f})")

    # Final verdict assessment
    print("\n--- SUMMARY VERDICT ---")
    if stable and stable['mean_z'] >= 2.0 and stable['pass_rate'] >= 0.8:
        print("VERDICT: ADOPT")
    elif stable and (stable['mean_z'] >= 1.5 or (dc and dc['z_paired'] >= 2.0)):
        print("VERDICT: INCONCLUSIVE (Borderline / Underpowered)")
    else:
        print("VERDICT: REJECT")


if __name__ == "__main__":
    run()
