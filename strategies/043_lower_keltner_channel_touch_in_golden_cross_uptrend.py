"""Strategy 043 — Lower Keltner Channel Touch in Golden Cross Uptrend (8d Swing).

HYPOTHESIS: When a stock in a golden cross uptrend touches or crosses below its lower 
Keltner Channel (EMA_20 - 2×ATR), it has pulled back by 2×ATR from its smoothed trend.
This is a volatility-adjusted "oversold" measure that captures DEPTH OF PULLBACK relative 
to the stock's own volatility, unlike RSI which measures momentum persistence.

HOW IT DIFFERS FROM RSI<30:
- RSI measures: "how many of the last 14 closes were down" (momentum persistence)
- Keltner Channel measures: "how far has price dropped from its trend in volatility units"
- A sharp one-day crash can touch the lower KC without RSI hitting 30 (too sudden)
- A gradual steady decline can push RSI<30 without touching KC (small daily drops)
- These should fire on partially DIFFERENT days, making them complementary signals

WHY THE KELTNER CHANNEL:
- Uses ATR instead of standard deviation (Bollinger Bands) — responsive to true range
- The 2×ATR multiplier means a touch requires a meaningful pullback (not noise)
- Pre-committed multiplier from technical analysis convention (2.0 is standard)
- Captures the physics: "how many standard moves has price deviated from trend?"

KILL CRITERIA:
- KILL if stable mean z_paired < 2.0
- KILL if subgroups fail
- KILL if dies in recent fold
- Also compare head-to-head vs AR-001 (Golden Cross + RSI<30)
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
KC_MULT = 2.0  # Standard Keltner Channel multiplier

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
        
        # Compute EMA_20 for Keltner Channel center
        d["ema_20"] = d["close"].ewm(span=20, adjust=False).mean()
        # Lower Keltner Channel
        d["kc_lower"] = d["ema_20"] - KC_MULT * d["atr"]
        # Touch or cross below lower KC
        d["below_kc"] = (d["close"] <= d["kc_lower"]).fillna(False)

        if t not in NIFTY_50:
            stocks[t] = d

    return stocks, pre_2017


def signal_mask(d):
    """Close at or below lower Keltner Channel, in golden cross, liquid."""
    return (d["below_kc"] & d["uptrend_200"] & d["golden_cross"] & d["liq"]).values


def run():
    print("=" * 80)
    print("STRATEGY 043: Lower Keltner Channel Touch in Golden Cross (8d)")
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

    # === 2. Stable z_paired vs 20 random controls ===
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
        # Quick overlap check
        print("\n[3] Quick check vs AR-001:")
        ar001_trades = []
        for t, d in stocks.items():
            liq = d["liq"].values
            sig = ((d["rsi"] < 30) & d["uptrend_200"] & d["golden_cross"] & liq).values
            trs = simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
            for tr in trs: tr["ticker"] = t
            ar001_trades += trs
        dc_ar001 = day_clustered_edge(strat_trades, ar001_trades)
        if dc_ar001:
            print(f"    z vs AR-001: {dc_ar001['z_paired']:+.2f}")
        our_dates = set(pd.to_datetime(tr['entry_date']).date() for tr in strat_trades)
        ar_dates = set(pd.to_datetime(tr['entry_date']).date() for tr in ar001_trades)
        print(f"    Our days: {len(our_dates)}, RSI<30+GC days: {len(ar_dates)}")
        print(f"    Overlap: {len(our_dates & ar_dates)} ({len(our_dates & ar_dates)/max(len(our_dates),1)*100:.0f}%)")
        return

    # === Full battery if passes early kill ===
    # 3. vs AR-001
    print("\n[3] Head-to-Head vs AR-001:")
    ar001_trades = []
    for t, d in stocks.items():
        liq = d["liq"].values
        sig = ((d["rsi"] < 30) & d["uptrend_200"] & d["golden_cross"] & liq).values
        trs = simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        for tr in trs: tr["ticker"] = t
        ar001_trades += trs
    dc_ar001 = day_clustered_edge(strat_trades, ar001_trades)
    if dc_ar001:
        print(f"    z vs AR-001: {dc_ar001['z_paired']:+.2f}, edge: {dc_ar001['day_edge']:+.3f}%")
    our_dates = set(pd.to_datetime(tr['entry_date']).date() for tr in strat_trades)
    ar_dates = set(pd.to_datetime(tr['entry_date']).date() for tr in ar001_trades)
    print(f"    Overlap: {len(our_dates & ar_dates)} / {len(our_dates)} days ({len(our_dates & ar_dates)/max(len(our_dates),1)*100:.0f}%)")

    # 4. Subgroups
    print("\n[4] Subgroups:")
    for label, ns in [("Half A", half_A), ("Half B", half_B)]:
        sub = [tr for tr in strat_trades if tr["ticker"] in ns]
        zs = []
        for c in controls:
            dc = day_clustered_edge(sub, [tr for tr in c if tr["ticker"] in ns])
            if dc: zs.append(dc['z_paired'])
        if zs:
            print(f"    {label} (n={len(sub):3d}): mean z = {np.mean(zs):+.2f} (pass {np.mean([z>=2.0 for z in zs])*100:.0f}%)")

    # 5. Survivorship
    print("\n[5] Survivorship:")
    sub_pre = [tr for tr in strat_trades if tr["ticker"] in pre_2017]
    if sub_pre:
        zs = []
        for c in controls:
            dc = day_clustered_edge(sub_pre, [tr for tr in c if tr["ticker"] in pre_2017])
            if dc: zs.append(dc['z_paired'])
        if zs:
            print(f"    Pre-2017 (n={len(sub_pre):3d}): mean z = {np.mean(zs):+.2f} (pass {np.mean([z>=2.0 for z in zs])*100:.0f}%)")

    # 6. Walk-Forward
    print("\n[6] Walk-Forward:")
    dates = pd.to_datetime([tr['entry_date'] for tr in strat_trades])
    fold_edges = pd.date_range(dates.min(), dates.max(), periods=6)
    ctrl0 = controls[0]
    fold_zs = []
    for fi in range(5):
        d0, d1 = fold_edges[fi], fold_edges[fi+1]
        fs = [tr for tr in strat_trades if d0 <= pd.to_datetime(tr['entry_date']) < d1]
        fc = [tr for tr in ctrl0 if d0 <= pd.to_datetime(tr['entry_date']) < d1]
        dc = day_clustered_edge(fs, fc)
        z = dc['z_paired'] if dc else 0.0
        fold_zs.append(z)
        print(f"    Fold {fi+1} ({d0.strftime('%Y-%m')} to {d1.strftime('%Y-%m')}): n={len(fs):3d}, z={z:+.2f}")
    print(f"    Mean: {np.mean(fold_zs):+.2f}")

    # 7. Next-Open
    print("\n[7] Next-Open:")
    strat_no = []
    for t, d in stocks.items():
        sig = signal_mask(d)
        open_, close, turnover = d["open"].values, d["close"].values, d["turnover_60d"].values
        n = len(d)
        last_exit = -1
        for i in range(n - HORIZON - 2):
            if not sig[i] or i <= last_exit: continue
            nxt = i + 1
            if nxt + HORIZON >= n: break
            ep = open_[nxt]
            if ep <= 0 or not np.isfinite(ep): continue
            xp = close[nxt + HORIZON]
            gross = (xp - ep) / ep * 100
            cost = round_trip_cost_pct(turnover[nxt])
            strat_no.append({'entry_date': d['date'].iat[nxt], 'net_pct': gross - cost, 'ticker': t})
            last_exit = nxt + HORIZON
    if strat_no:
        ctrl_no = controls[0]  # simplified
        dc_no = day_clustered_edge(strat_no, ctrl_no)
        net_no = np.mean([tr['net_pct'] for tr in strat_no])
        print(f"    Next-Open: n={len(strat_no)}, net={net_no:+.3f}%, z={dc_no['z_paired']:+.2f}" if dc_no else f"    n={len(strat_no)}")

    # Summary
    print("\n" + "=" * 80)
    print(f"Stable Mean z: {mean_z_rnd:+.2f} (pass {pass_rate_rnd:.0f}%), Edge: {mean_edge_rnd:+.3f}%")
    print("=" * 80)


if __name__ == "__main__":
    run()
