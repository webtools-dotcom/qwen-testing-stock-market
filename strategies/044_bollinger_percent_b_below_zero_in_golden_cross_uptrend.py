"""Strategy 044 — Bollinger %B Below Zero in Golden Cross Uptrend (8d Swing).

HYPOTHESIS: When Bollinger %B drops below 0 (close < lower Bollinger Band = SMA_20 - 2σ),
the stock is a statistical outlier from its own recent price distribution. In golden cross
uptrend, this statistical extreme signals a buyable dislocation.

%B = (Close - Lower BB) / (Upper BB - Lower BB)
%B < 0 means Close is below the lower Bollinger Band (a 2-sigma event)

This is DIFFERENT from:
- RSI: measures momentum (close-to-close changes), not statistical deviation
- Keltner Channel (043): uses ATR (true range), %B uses standard deviation (close-to-close)
  They capture different types of extreme events:
  * ATR-based: detects large intraday ranges (gap-and-crash days)
  * StdDev-based: detects close-to-close deviation from trend (persistent drift)

KILL CRITERIA:
- KILL if stable mean z_paired < 2.0
- KILL if fails subgroups
- KILL if fails recent fold
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
BB_WINDOW = 20
BB_STD = 2.0

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
        d = df.dropna(subset=["close", "volume", "rsi", "sma_200", "sma_50", "sma_20", "atr"]).reset_index(drop=True).copy()
        if len(d) < 300:
            continue
        d["ticker"] = t
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        d["uptrend_200"] = (d["close"] > d["sma_200"]).fillna(False)
        d["golden_cross"] = (d["sma_50"] > d["sma_200"]).fillna(False)
        
        # Bollinger Bands
        std_20 = d["close"].rolling(BB_WINDOW).std(ddof=1)
        lower_bb = d["sma_20"] - BB_STD * std_20
        upper_bb = d["sma_20"] + BB_STD * std_20
        bb_width = upper_bb - lower_bb
        d["pct_b"] = (d["close"] - lower_bb) / bb_width.replace(0, np.nan)
        d["below_lower_bb"] = (d["pct_b"] < 0).fillna(False)

        if t not in NIFTY_50:
            stocks[t] = d

    return stocks, pre_2017


def signal_mask(d):
    """%B below zero in golden cross, liquid."""
    return (d["below_lower_bb"] & d["uptrend_200"] & d["golden_cross"] & d["liq"]).values


def run():
    print("=" * 80)
    print("STRATEGY 044: Bollinger %B Below Zero in Golden Cross (8d)")
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
    
    # === Overlap with RSI<30 ===
    rsi30_trades = []
    for t, d in stocks.items():
        liq = d["liq"].values
        sig = ((d["rsi"] < 30) & d["uptrend_200"] & d["golden_cross"] & liq).values
        trs = simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        for tr in trs: tr["ticker"] = t
        rsi30_trades += trs
    our_dates = set(pd.to_datetime(tr['entry_date']).date() for tr in strat_trades)
    rsi_dates = set(pd.to_datetime(tr['entry_date']).date() for tr in rsi30_trades)
    print(f"    Overlap with RSI<30+GC: {len(our_dates & rsi_dates)}/{len(our_dates)} days ({len(our_dates & rsi_dates)/max(len(our_dates),1)*100:.0f}%)")

    # === 2. Stable z_paired ===
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
            for tr in trs: tr["ticker"] = t
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
        dc_ar001 = day_clustered_edge(strat_trades, rsi30_trades)
        if dc_ar001:
            print(f"    z vs AR-001: {dc_ar001['z_paired']:+.2f}")
        return

    # 3. vs AR-001
    print("\n[3] Head-to-Head vs AR-001:")
    dc_ar001 = day_clustered_edge(strat_trades, rsi30_trades)
    if dc_ar001:
        print(f"    z vs AR-001: {dc_ar001['z_paired']:+.2f}, edge: {dc_ar001['day_edge']:+.3f}%")

    # 4. Subgroups
    print("\n[4] Subgroups:")
    for label, ns in [("Half A", half_A), ("Half B", half_B)]:
        sub = [tr for tr in strat_trades if tr["ticker"] in ns]
        zs = [day_clustered_edge(sub, [tr for tr in c if tr["ticker"] in ns])['z_paired'] for c in controls if day_clustered_edge(sub, [tr for tr in c if tr["ticker"] in ns])]
        if zs:
            print(f"    {label} (n={len(sub):3d}): mean z = {np.mean(zs):+.2f} (pass {np.mean([z>=2.0 for z in zs])*100:.0f}%)")

    # 5. Walk-Forward
    print("\n[5] Walk-Forward:")
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
        print(f"    Fold {fi+1}: n={len(fs):3d}, z={z:+.2f}")
    print(f"    Mean: {np.mean(fold_zs):+.2f}")

    # 6. Next-Open
    print("\n[6] Next-Open:")
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
        zs_no = []
        for c in controls[:5]:
            dc_no = day_clustered_edge(strat_no, c)
            if dc_no: zs_no.append(dc_no['z_paired'])
        net_no = np.mean([tr['net_pct'] for tr in strat_no])
        print(f"    n={len(strat_no)}, net={net_no:+.3f}%, mean z={np.mean(zs_no):+.2f}" if zs_no else f"    n={len(strat_no)}")

    # Summary
    print("\n" + "=" * 80)
    print(f"Stable Mean z: {mean_z_rnd:+.2f} (pass {pass_rate_rnd:.0f}%), Edge: {mean_edge_rnd:+.3f}%")
    print("=" * 80)


if __name__ == "__main__":
    run()
