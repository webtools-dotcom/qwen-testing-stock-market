"""Strategy 002 — 10-day RoC mean reversion in mid-small caps.

Hypothesis:
In liquid Mid & Small Cap Indian stocks (turnover >= ₹25cr/day), sharp 2-week pullbacks
(10-day Rate-of-Change < -10%) occurring within an intermediate structural uptrend
(Close > 200-day SMA) create liquidity exhaustion. Selling pressure exhausts as retail stop-losses
trigger, allowing institutional dip-buyers to absorb shares and generate a positive mean-reversion
swing over the subsequent 6-10 days.

Run:  python strategies/002_10_day_roc_mean_reversion_in_mid_small_caps.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from data_loader import get_panel
from backtest_engine import (
    simulate_trades, day_clustered_edge, edge_vs_control,
    walk_forward_splits, deflated_sharpe, effective_trials,
    sharpe, report
)

# 128 Liquid Mid & Small Cap NSE stocks (excluding Nifty 50 large caps)
UNIVERSE = [
    '360ONE.NS', '3MINDIA.NS', 'AADHARHFC.NS', 'AARTIIND.NS', 'AAVAS.NS', 'ABB.NS', 'ABBOTINDIA.NS',
    'ABCAPITAL.NS', 'ABDL.NS', 'ABFRL.NS', 'ABLBL.NS', 'ABREL.NS', 'ABSLAMC.NS', 'ACC.NS', 'ACE.NS',
    'ACMESOLAR.NS', 'ACUTAAS.NS', 'ADANIENSOL.NS', 'ADANIENT.NS', 'ADANIGREEN.NS', 'ADANIPOWER.NS',
    'AEGISLOG.NS', 'AEGISVOPAK.NS', 'AFCONS.NS', 'AFFLE.NS', 'AIAENG.NS', 'AIIL.NS', 'AJANTPHARM.NS',
    'ALKEM.NS', 'AMBER.NS', 'AMBUJACEM.NS', 'ANANDRATHI.NS', 'ANANTRAJ.NS', 'ANTHEM.NS', 'APARINDS.NS',
    'APLAPOLLO.NS', 'APOLLOTYRE.NS', 'APTUS.NS', 'ARE&M.NS', 'ASAHIINDIA.NS', 'ASHOKLEY.NS', 'ASTERDM.NS',
    'ASTRAL.NS', 'ATGL.NS', 'ATHERENERG.NS', 'ATUL.NS', 'AUBANK.NS', 'AUROPHARMA.NS', 'BAJAJ-AUTO.NS',
    'BAJAJHFL.NS', 'BAJAJHLDNG.NS', 'BALKRISIND.NS', 'BALRAMCHIN.NS', 'BANDHANBNK.NS', 'BANKBARODA.NS',
    'BANKINDIA.NS', 'BATAINDIA.NS', 'BAYERCROP.NS', 'BBTC.NS', 'BDL.NS', 'BEL.NS', 'BELRISE.NS', 'BEML.NS',
    'BERGEPAINT.NS', 'BHARATFORG.NS', 'BHARTIHEXA.NS', 'BHEL.NS', 'BIKAJI.NS', 'BIOCON.NS', 'BLS.NS',
    'BLUEDART.NS', 'BLUEJET.NS', 'BLUESTARCO.NS', 'BRIGADE.NS', 'BSE.NS', 'BSOFT.NS', 'CAMS.NS', 'CANBK.NS',
    'CANFINHOME.NS', 'CAPLIPOINT.NS', 'CARBORUNIV.NS', 'CARTRADE.NS', 'CASTROLIND.NS', 'CCL.NS', 'CDSL.NS',
    'CEATLTD.NS', 'CEMPRO.NS', 'CENTRALBK.NS', 'CESC.NS', 'CGCL.NS', 'CGPOWER.NS', 'CHALET.NS',
    'CHAMBLFERT.NS', 'CHENNPETRO.NS', 'CHOICEIN.NS', 'CHOLAFIN.NS', 'CHOLAHLDNG.NS', 'CLEAN.NS',
    'COCHINSHIP.NS', 'COFORGE.NS', 'COHANCE.NS', 'COLPAL.NS', 'CONCOR.NS', 'CONCORDBIO.NS', 'COROMANDEL.NS',
    'CPPLUS.NS', 'CRAFTSMAN.NS', 'CREDITACC.NS', 'CRISIL.NS', 'CROMPTON.NS', 'CUB.NS', 'CUMMINSIND.NS',
    'CYIENT.NS', 'DABUR.NS', 'DALBHARAT.NS', 'DATAPATTNS.NS', 'DCMSHRIRAM.NS', 'DEEPAKFERT.NS',
    'DEEPAKNTR.NS', 'DEVYANI.NS', 'DIXON.NS', 'DLF.NS', 'DMART.NS', 'DOMS.NS', 'EIDPARRY.NS',
    'LALPATHLAB.NS', 'MAHABANK.NS', 'MAPMYINDIA.NS'
]

ROC_THRESHOLD = -10.0    # 10-day Rate of Change cutoff (-10%)
HORIZON = 6              # 6-day swing holding period
MIN_TURNOVER = 25e7      # ₹25cr/day liquidity floor


def signal_mask(d):
    """10-day Rate-of-Change < -10% within a long-term structural uptrend (Close > SMA 200)."""
    roc_10 = d['close'].pct_change(10) * 100
    return (roc_10 < ROC_THRESHOLD) & (d['close'] > d['sma_200'])


def run():
    print(f"Loading {len(UNIVERSE)} Mid/Small cap stocks (5y)...")
    panel = get_panel(UNIVERSE, period="5y", cache_name="nifty_research_150_5y")
    print(f"Got {len(panel)} usable stocks\n")

    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    valid_dfs = []
    
    for ticker, df in panel.items():
        d = df.dropna(subset=['rsi', 'atr', 'close', 'sma_200']).reset_index(drop=True)
        if len(d) < 300:
            continue
        valid_dfs.append(d)
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq       # matched random-entry control
        strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl  += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(report(f"10-Day RoC < {ROC_THRESHOLD}% Mean Reversion (Mid/Small, {HORIZON}d, costs charged)",
                 strat, ctrl))

    dc = day_clustered_edge(strat, ctrl)
    print("\n--- DAY-CLUSTERED HEADLINE VERDICT ---")
    if dc and dc['z_paired'] >= 2.0 and dc['day_edge'] > 0:
        print(f"  z_paired = {dc['z_paired']:.2f} >= 2.0 (day_edge = {dc['day_edge']:+.3f}%)  ->  ADOPT-ELIGIBLE")
    elif dc:
        print(f"  z_paired = {dc['z_paired']:.2f} < 2.0  ->  REJECT")

    # Walk-forward validation across 4 chronological folds
    if valid_dfs:
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
            d_start = valid_dfs[0]['date'].iat[min(te0, sample_len-1)].strftime('%Y-%m-%d')
            d_end = valid_dfs[0]['date'].iat[min(te1-1, sample_len-1)].strftime('%Y-%m-%d')
            if f_res and f_dc:
                print(f"  Fold {fold_idx} ({d_start} to {d_end}): Trades {f_res['n_strategy']:3d} | "
                      f"Net: {f_res['strategy_avg']:+5.2f}% | Edge: {f_res['edge']:+5.2f}% | "
                      f"z_paired: {f_dc['z_paired']:+5.2f} | DayEdge: {f_dc['day_edge']:+5.2f}%")


if __name__ == "__main__":
    run()
