"""Strategy 001 — RSI(14) < 30 mean reversion (the worked example).

This is the reference implementation new strategies should look like. It shows the full honest
loop end to end: build a panel, generate NON-OVERLAPPING signal trades AND a matched random
control, charge costs, and headline the DAY-CLUSTERED z_paired — not the flattering trade-level z.

Run:  python strategies/001_rsi_mean_reversion.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from data_loader import get_panel
from backtest_engine import simulate_trades, edge_vs_control, day_clustered_edge, report

# A small liquid NSE universe for the example. For real research use a proper list (Nifty 500).
UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS",
    "LT.NS", "ITC.NS", "HINDUNILVR.NS", "MARUTI.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "JSWSTEEL.NS",
    "SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "WIPRO.NS", "TECHM.NS", "HCLTECH.NS", "BAJFINANCE.NS",
    "ASIANPAINT.NS", "ULTRACEMCO.NS", "GRASIM.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS", "COALINDIA.NS",
    "ADANIPORTS.NS", "TITAN.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DIVISLAB.NS", "EICHERMOT.NS",
]

RSI_THRESHOLD = 30       # pre-committed (Wilder's number) — NOT tuned, so no search penalty
HORIZON = 6
MIN_TURNOVER = 25e7      # ₹25cr/day liquidity floor (validated in the sister project)


def run():
    print(f"Downloading {len(UNIVERSE)} names (5y)...")
    panel = get_panel(UNIVERSE, period="5y", cache_name="nifty_large_5y")
    print(f"got {len(panel)} usable stocks\n")

    rng = np.random.default_rng(42)
    strat, ctrl, total_bars = [], [], 0
    for ticker, df in panel.items():
        d = df.dropna(subset=['rsi', 'atr', 'close']).reset_index(drop=True)
        if len(d) < 300:
            continue
        total_bars += len(d)
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        signal = ((d['rsi'] < RSI_THRESHOLD) & liq).values
        random_entry = (rng.random(len(d)) < 0.10) & liq       # control: same liquidity, random days
        strat += simulate_trades(d, signal, horizon_days=HORIZON, charge_costs=True)
        ctrl  += simulate_trades(d, random_entry, horizon_days=HORIZON, charge_costs=True)

    print(report(f"RSI<{RSI_THRESHOLD} mean reversion (liquid, {HORIZON}d, costs charged)",
                 strat, ctrl))

    dc = day_clustered_edge(strat, ctrl)
    print("\nVERDICT GUIDE: headline is DAY-CLUSTERED z_paired above.")
    if dc and dc['z_paired'] >= 2.0 and dc['day_edge'] > 0:
        print(f"  → z_paired {dc['z_paired']:.2f} ≥ 2.0 and net edge positive: ADOPT-eligible "
              f"(still walk-forward it before trusting).")
    elif dc:
        print(f"  → z_paired {dc['z_paired']:.2f}: NOT demonstrated on this universe. "
              f"If this were a new idea, that's a REJECT (log it with ledger.py).")


if __name__ == "__main__":
    run()
