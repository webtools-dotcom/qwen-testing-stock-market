"""Strategy 014 — High Volatility Oversold Mean Reversion.

Run:  python strategies/014_high_volatility_oversold_mean_reversion.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from data_loader import get_panel
from backtest_engine import simulate_trades, day_clustered_edge, report

UNIVERSE = ['ABB.NS', 'ABBOTINDIA.NS', 'ABCAPITAL.NS', 'ABFRL.NS', 'ACC.NS', 'ADANIENT.NS', 'ADANIPORTS.NS', 'ADANIPOWER.NS', 'ALKEM.NS', 'AMBER.NS', 'AMBUJACEM.NS', 'APLAPOLLO.NS', 'APOLLOHOSP.NS', 'APOLLOTYRE.NS', 'ASHOKLEY.NS', 'ASIANPAINT.NS', 'ASTRAL.NS', 'AUBANK.NS', 'AUROPHARMA.NS', 'AXISBANK.NS', 'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS', 'BAJFINANCE.NS', 'BALKRISIND.NS', 'BANDHANBNK.NS', 'BANKBARODA.NS', 'BATAINDIA.NS', 'BEL.NS', 'BEML.NS', 'BERGEPAINT.NS', 'BHARATFORG.NS', 'BHARTIARTL.NS', 'BHEL.NS', 'BIOCON.NS', 'BPCL.NS', 'BRITANNIA.NS', 'BSE.NS', 'BSOFT.NS', 'CANBK.NS', 'CANFINHOME.NS', 'CDSL.NS', 'CHOLAFIN.NS', 'CIPLA.NS', 'COALINDIA.NS', 'COFORGE.NS', 'COLPAL.NS', 'CONCOR.NS', 'COROMANDEL.NS', 'CROMPTON.NS', 'CUB.NS', 'CUMMINSIND.NS', 'CYIENT.NS', 'DABUR.NS', 'DALBHARAT.NS', 'DEEPAKNTR.NS', 'DIVISLAB.NS', 'DIXON.NS', 'DLF.NS', 'DRREDDY.NS', 'EICHERMOT.NS', 'GRASIM.NS', 'HCLTECH.NS', 'HDFCBANK.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS', 'HINDUNILVR.NS', 'ICICIBANK.NS', 'INDUSINDBK.NS', 'INFY.NS', 'ITC.NS', 'JSWSTEEL.NS', 'KOTAKBANK.NS', 'LALPATHLAB.NS', 'LT.NS', 'M&M.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'NTPC.NS', 'ONGC.NS', 'POWERGRID.NS', 'RELIANCE.NS', 'SBILIFE.NS', 'SBIN.NS', 'SHRIRAMFIN.NS', 'SUNPHARMA.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS', 'TCS.NS', 'TECHM.NS', 'TITAN.NS', 'TRENT.NS', 'ULTRACEMCO.NS', 'WIPRO.NS']
HORIZON = 6
MIN_TURNOVER = 25e7


def signal_mask(d):
    """Return a boolean numpy array — True where the strategy ENTERS."""
    rsi_condition = d['rsi'] < 30
    high_vol = d['atr_pct'] > 3.5
    
    return (rsi_condition & high_vol).fillna(False).values


def run():
    panel = get_panel(UNIVERSE, period="5y", cache_name="nifty_research_150_5y")
    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    for ticker, df in panel.items():
        d = df.dropna(subset=["rsi", "atr_pct", "close"]).reset_index(drop=True)
        if len(d) < 300:
            continue
        liq = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d) & liq
        rnd = (rng.random(len(d)) < 0.10) & liq         # matched random-entry control
        strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl  += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(report("High Volatility Oversold Mean Reversion", strat, ctrl))
    dc = day_clustered_edge(strat, ctrl)
    if dc:
        verdict = "ADOPT-eligible" if dc["z_paired"] >= 2.0 and dc["day_edge"] > 0 else "REJECT"
        print(f"\nheadline z_paired {dc['z_paired']:.2f}, day_edge {dc['day_edge']:+.3f}%  ->  {verdict}")
        print("Then walk-forward it, and log the verdict: python ledger.py reject/adopt \"...\" \"...\"")


if __name__ == "__main__":
    run()
