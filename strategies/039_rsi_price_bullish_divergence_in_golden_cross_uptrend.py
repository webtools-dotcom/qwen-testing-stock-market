"""Strategy 039 — RSI-Price Bullish Divergence in Golden Cross Uptrend (8d Swing).

HYPOTHESIS: When a stock in a golden-cross uptrend makes a new 20-day price low, but its 
RSI(14) is HIGHER than it was at the previous 20-day price low, it signals bullish divergence.
Momentum is improving even as price still declines — the selling pressure is exhausting.

This is structurally DIFFERENT from RSI<30:
- RSI<30 measures absolute oversold LEVEL
- Bullish divergence measures the TREND of momentum (improving vs worsening)
- A stock can show bullish divergence at RSI 40 (never reaching 30) if its RSI bottomed at 25
  on the previous low and is now at 40 on a lower price low
- Captures "selling exhaustion" through momentum non-confirmation, not absolute extremes

WHY IT MIGHT WORK:
- Classical technical analysis principle — momentum leads price
- In golden cross, the structural bid is intact, so the divergence is likely resolved upward
- It should fire at different times than RSI<30 (different mechanism)

WHY IT WILL PROBABLY FAIL:
- "Shallow vs deep pullback" was rejected (but that's different — it didn't measure divergence)
- Divergence detection is inherently noisy (how to define "previous low"?)
- May fire too infrequently in golden cross stocks (which are strong)
- KILL if stable mean z_paired < 2.0
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pickle
from backtest_engine import (
    simulate_trades, day_clustered_edge, round_trip_cost_pct
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_TURNOVER = 25e7
HORIZON = 8

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}


def load_data():
    master_path = os.path.join(BASE, "cache", "master_10y.pkl")
    raw = pickle.load(open(master_path, "rb"))
    panel = raw["data"] if isinstance(raw, dict) and "data" in raw else raw

    stocks = {}
    pre_2017 = set()

    for t, df in panel.items():
        if df["date"].min() <= pd.Timestamp("2016-12-31"):
            pre_2017.add(t)
        d = df.dropna(subset=["close", "volume", "rsi", "sma_200", "sma_50", "atr"]).reset_index(drop=True).copy()
        if len(d) < 300:
            continue
        d["ticker"] = t
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        d["uptrend_200"] = (d["close"] > d["sma_200"]).fillna(False)
        d["golden_cross"] = (d["sma_50"] > d["sma_200"]).fillna(False)

        # Detect bullish divergence: price makes new 20-day low, RSI is higher than at prev 20-day low
        close = d["close"].values
        rsi = d["rsi"].values
        n = len(d)
        
        # Rolling 20-day low
        d["low_20d"] = d["close"].rolling(20).min()
        # Is today a new 20-day low?
        d["is_20d_low"] = (d["close"] <= d["low_20d"] * 1.001)  # within 0.1% of 20d low
        
        # For each new 20d low, find the RSI at the PREVIOUS 20d low
        # We need to track the RSI at the previous 20-day low event
        divergence = np.zeros(n, dtype=bool)
        prev_low_rsi = np.nan
        prev_low_price = np.nan
        last_low_idx = -30  # avoid clustering
        
        for i in range(20, n):
            if d["is_20d_low"].iat[i] and i - last_low_idx >= 5:
                # This is a new 20-day low event
                if np.isfinite(prev_low_rsi) and np.isfinite(rsi[i]):
                    # Bullish divergence: price is equal or lower, RSI is HIGHER
                    if close[i] <= prev_low_price * 1.01 and rsi[i] > prev_low_rsi + 2:
                        # RSI must be meaningfully higher (>2 points)
                        divergence[i] = True
                prev_low_rsi = rsi[i]
                prev_low_price = close[i]
                last_low_idx = i
        
        d["bullish_divergence"] = divergence

        if t not in NIFTY_50:
            stocks[t] = d

    return stocks, pre_2017


def signal_mask(d):
    """Bullish divergence in golden cross uptrend, liquid."""
    return (d["bullish_divergence"] & d["uptrend_200"] & d["golden_cross"] & d["liq"]).values


def run():
    print("=" * 80)
    print("STRATEGY 039: RSI-Price Bullish Divergence in Golden Cross (8d Swing)")
    print("=" * 80)

    stocks, pre_2017_all = load_data()
    tickers = sorted(stocks.keys())
    pre_2017 = pre_2017_all.intersection(set(tickers))

    half = len(tickers) // 2
    half_A = set(tickers[:half])
    half_B = set(tickers[half:])

    print(f"Panel: {len(tickers)} Mid/Small liquid stocks")

    # === 1. Strategy trades ===
    strat_trades = []
    for t, d in stocks.items():
        sig = signal_mask(d)
        trs = simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        for tr in trs:
            tr["ticker"] = t
        strat_trades += trs

    print(f"\n[1] Strategy Trades: {len(strat_trades)}")
    if not strat_trades or len(strat_trades) < 30:
        print("    TOO FEW TRADES. ABORT.")
        return
    gross_ret = np.mean([tr["gross_pct"] for tr in strat_trades])
    net_ret = np.mean([tr["net_pct"] for tr in strat_trades])
    cost_ret = np.mean([tr["cost_pct"] for tr in strat_trades])
    win_rate = np.mean([tr["net_pct"] > 0 for tr in strat_trades]) * 100
    print(f"    Gross Return / Trade : {gross_ret:+.3f}%")
    print(f"    Round-Trip Cost      : {cost_ret:.3f}%")
    print(f"    NET Return / Trade   : {net_ret:+.3f}%")
    print(f"    Win Rate             : {win_rate:.1f}%")

    entry_dates = pd.to_datetime([tr['entry_date'] for tr in strat_trades])
    n_unique_days = entry_dates.nunique()
    print(f"    Unique entry days    : {n_unique_days}")
    print(f"    Trades/day (avg)     : {len(strat_trades) / max(n_unique_days, 1):.1f}")

    # === 2. Stable z_paired vs 20 random control seeds ===
    print("\n[2] Stable z_paired vs 20 Random Controls...")
    t0 = time.time()
    controls = []
    for s in range(20):
        rng = np.random.default_rng(s)
        ctrl = []
        for t, d in stocks.items():
            liq = d["liq"].values
            rnd = (rng.random(len(d)) < 0.05) & liq
            trs = simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
            for tr in trs:
                tr["ticker"] = t
            ctrl += trs
        controls.append(ctrl)
    print(f"    Controls generated in {time.time() - t0:.1f}s")

    zs_rnd = []
    edges_rnd = []
    for c in controls:
        dc = day_clustered_edge(strat_trades, c)
        if dc:
            zs_rnd.append(dc['z_paired'])
            edges_rnd.append(dc['day_edge'])
    mean_z_rnd = np.mean(zs_rnd) if zs_rnd else 0
    pass_rate_rnd = np.mean([z >= 2.0 for z in zs_rnd]) * 100 if zs_rnd else 0
    mean_edge_rnd = np.mean(edges_rnd) if edges_rnd else 0
    print(f"    Stable Mean z_paired : {mean_z_rnd:+.2f} (min {np.min(zs_rnd):+.2f}, max {np.max(zs_rnd):+.2f})")
    print(f"    Pass Rate (z >= 2.0) : {pass_rate_rnd:.1f}%")
    print(f"    Net Day Edge vs Ctrl : {mean_edge_rnd:+.3f}%")

    if mean_z_rnd < 1.5:
        print(f"\n*** EARLY KILL: stable mean z = {mean_z_rnd:+.2f} < 1.5. REJECT. ***")
        return

    # === 3. Head-to-Head vs AR-001 (§10) ===
    print("\n[3] Head-to-Head vs AR-001 (Golden Cross + RSI<30):")
    ar001_trades = []
    for t, d in stocks.items():
        liq = d["liq"].values
        sig = ((d["rsi"] < 30) & d["uptrend_200"] & d["golden_cross"] & liq).values
        trs = simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        for tr in trs:
            tr["ticker"] = t
        ar001_trades += trs
    dc_ar001 = day_clustered_edge(strat_trades, ar001_trades)
    if dc_ar001:
        print(f"    AR-001 Trades          : {len(ar001_trades)}")
        print(f"    z_paired vs AR-001     : {dc_ar001['z_paired']:+.2f}")
        print(f"    Day Edge vs AR-001     : {dc_ar001['day_edge']:+.3f}%")

    # === 4. Subgroup Tests (§8) ===
    print("\n[4] Subgroup Robustness (§8):")
    strat_A = [tr for tr in strat_trades if tr["ticker"] in half_A]
    strat_B = [tr for tr in strat_trades if tr["ticker"] in half_B]
    for label, sub, name_set in [("Half A", strat_A, half_A), ("Half B", strat_B, half_B)]:
        zs = []
        for c in controls:
            dc = day_clustered_edge(sub, [tr for tr in c if tr["ticker"] in name_set])
            if dc:
                zs.append(dc['z_paired'])
        if zs:
            print(f"    {label} (n={len(sub):3d}) : stable mean z = {np.mean(zs):+.2f} (pass {np.mean([z >= 2.0 for z in zs]) * 100:.0f}%)")

    # === 5. Survivorship ===
    print("\n[5] Survivorship:")
    strat_pre17 = [tr for tr in strat_trades if tr["ticker"] in pre_2017]
    if strat_pre17:
        zs_pre17 = []
        for c in controls:
            dc_p = day_clustered_edge(strat_pre17, [tr for tr in c if tr["ticker"] in pre_2017])
            if dc_p:
                zs_pre17.append(dc_p['z_paired'])
        if zs_pre17:
            print(f"    Pre-2017 (n={len(strat_pre17):3d}) : stable mean z = {np.mean(zs_pre17):+.2f} (pass {np.mean([z >= 2.0 for z in zs_pre17]) * 100:.0f}%)")

    # === 6. Walk-Forward ===
    print("\n[6] Walk-Forward Folds (5 Chronological):")
    dates = pd.to_datetime([tr['entry_date'] for tr in strat_trades])
    fold_edges = pd.date_range(dates.min(), dates.max(), periods=6)
    ctrl_sample = controls[0]
    fold_zs = []
    for f_idx in range(5):
        d0, d1 = fold_edges[f_idx], fold_edges[f_idx + 1]
        f_s = [tr for tr in strat_trades if d0 <= pd.to_datetime(tr['entry_date']) < d1]
        f_c = [tr for tr in ctrl_sample if d0 <= pd.to_datetime(tr['entry_date']) < d1]
        dc_f = day_clustered_edge(f_s, f_c)
        z_f = dc_f['z_paired'] if dc_f else 0.0
        edge_f = dc_f['day_edge'] if dc_f else 0.0
        fold_zs.append(z_f)
        print(f"    Fold {f_idx + 1} ({d0.strftime('%Y-%m')} to {d1.strftime('%Y-%m')}) : Trades={len(f_s):3d}, z_paired={z_f:+5.2f}, day_edge={edge_f:+.3f}%")
    print(f"    Mean Fold z: {np.mean(fold_zs):+.2f}")

    # === 7. What overlap with RSI<30? ===
    print("\n[7] Overlap Analysis with RSI<30:")
    div_dates = set(pd.to_datetime(tr['entry_date']).date() for tr in strat_trades)
    ar001_dates = set(pd.to_datetime(tr['entry_date']).date() for tr in ar001_trades)
    overlap = div_dates & ar001_dates
    print(f"    Divergence signal days : {len(div_dates)}")
    print(f"    RSI<30+GC signal days  : {len(ar001_dates)}")
    print(f"    Overlapping days       : {len(overlap)} ({len(overlap)/max(len(div_dates),1)*100:.0f}%)")
    print(f"    Unique to divergence   : {len(div_dates - ar001_dates)} ({len(div_dates - ar001_dates)/max(len(div_dates),1)*100:.0f}%)")

    # === SUMMARY ===
    print("\n" + "=" * 80)
    print(f"FINAL SUMMARY:")
    print(f"  Stable Mean z vs Random : {mean_z_rnd:+.2f} (pass {pass_rate_rnd:.0f}%)")
    print(f"  Net Day Edge vs Random  : {mean_edge_rnd:+.3f}%")
    if dc_ar001:
        print(f"  z vs AR-001 GC+RSI<30   : {dc_ar001['z_paired']:+.2f}")
    print(f"  Mean Fold z             : {np.mean(fold_zs):+.2f}")
    print("=" * 80)


if __name__ == "__main__":
    run()
