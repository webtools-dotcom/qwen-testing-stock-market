"""Strategy 011 — Momentum Pullback 15 Percent.

Fill in UNIVERSE, the entry signal, and exits. Model on strategies/001_rsi_mean_reversion.py.
Run:  python strategies/011_momentum_pullback_15_percent.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from data_loader import get_panel
from backtest_engine import simulate_trades, day_clustered_edge, report

UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS",
    "LT.NS", "ITC.NS", "HINDUNILVR.NS", "MARUTI.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "JSWSTEEL.NS",
    "SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "WIPRO.NS", "TECHM.NS", "HCLTECH.NS", "BAJFINANCE.NS",
    "ASIANPAINT.NS", "ULTRACEMCO.NS", "GRASIM.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS", "COALINDIA.NS",
    "ADANIPORTS.NS", "TITAN.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DIVISLAB.NS", "EICHERMOT.NS",
]
HORIZON = 6
MIN_TURNOVER = 25e7


def signal_mask(d):
    """Return a boolean numpy array — True where the strategy ENTERS."""
    # Strong momentum over the last year
    strong_momentum = d['change_252d'] > 30
    
    # Uptrend still intact
    uptrend = d['close'] > d['sma_200']
    
    # 15% to 25% pullback from 50-day high
    pullback = (d['distance_from_high_50'] <= -0.15) & (d['distance_from_high_50'] > -0.25)
    
    return (strong_momentum & uptrend & pullback).values


def run():
    panel = get_panel(UNIVERSE, period="5y", cache_name="momentum_pullback_15_percent_5y")
    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    for ticker, df in panel.items():
        d = df.dropna(subset=["change_252d", "sma_200", "distance_from_high_50", "close"]).reset_index(drop=True)
        if len(d) < 300:
            continue
        liq = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d) & liq
        rnd = (rng.random(len(d)) < 0.10) & liq         # matched random-entry control
        strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl  += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(report("Momentum Pullback 15 Percent", strat, ctrl))
    dc = day_clustered_edge(strat, ctrl)
    if dc:
        verdict = "ADOPT-eligible" if dc["z_paired"] >= 2.0 and dc["day_edge"] > 0 else "REJECT"
        print(f"\nheadline z_paired {dc['z_paired']:.2f}, day_edge {dc['day_edge']:+.3f}%  ->  {verdict}")
        print("Then walk-forward it, and log the verdict: python ledger.py reject/adopt \"...\" \"...\"")


if __name__ == "__main__":
    run()
