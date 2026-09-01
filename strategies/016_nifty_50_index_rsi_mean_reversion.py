"""Strategy 016 — Nifty 50 Index RSI Mean Reversion.

Run:  python strategies/016_nifty_50_index_rsi_mean_reversion.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from data_loader import get_panel
from backtest_engine import simulate_trades, day_clustered_edge, report

UNIVERSE = ['^NSEI']
HORIZON = 6
MIN_TURNOVER = 0


def signal_mask(d):
    """Return a boolean numpy array — True where the strategy ENTERS."""
    return (d['rsi'] < 30).fillna(False).values


def run():
    panel = get_panel(UNIVERSE, period="5y", cache_name="nifty50_index_5y")
    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    for ticker, df in panel.items():
        d = df.dropna(subset=["rsi", "close"]).reset_index(drop=True)
        if len(d) < 300:
            continue
        liq = np.ones(len(d), dtype=bool) # Index is always liquid
        sig = signal_mask(d) & liq
        rnd = (rng.random(len(d)) < 0.10) & liq         # matched random-entry control
        strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl  += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(report("Nifty 50 Index RSI Mean Reversion", strat, ctrl))
    dc = day_clustered_edge(strat, ctrl)
    if dc:
        verdict = "ADOPT-eligible" if dc["z_paired"] >= 2.0 and dc["day_edge"] > 0 else "REJECT"
        print(f"\nheadline z_paired {dc['z_paired']:.2f}, day_edge {dc['day_edge']:+.3f}%  ->  {verdict}")
        print("Then walk-forward it, and log the verdict: python ledger.py reject/adopt \"...\" \"...\"")


if __name__ == "__main__":
    run()
