"""Strategy 037 — MACD Histogram Reversal Below Zero in Structural Uptrend (8d Swing).

HYPOTHESIS: When MACD histogram (MACD - signal) crosses from negative to positive while
the MACD line itself is below zero, it signals the END of a pullback within a structural
uptrend. The short-term momentum is recovering (12-EMA catching up to 26-EMA) while the
stock is still "below equilibrium" — this is a momentum convergence signal, structurally
different from RSI oversold levels.

WHY IT MIGHT WORK:
- MACD histogram reversal is a leading indicator of trend resumption
- Below-zero constraint ensures we're buying pullbacks, not chasing overbought
- Structural uptrend (close > sma_200) ensures we're in a bull regime
- Different from RSI: measures momentum convergence, not absolute oversold levels

WHY IT WILL PROBABLY FAIL (pre-registered kill criteria):
- MACD signals fire FREQUENTLY — expect heavy day clustering
- The "below zero" constraint may be too loose — too many trades
- It's a moving-average derivative — may be too slow for 8-day swing
- KILL if: stable mean z_paired < 2.0, or subgroups fail, or dies in recent fold

Run: python strategies/037_macd_histogram_reversal_below_zero_in_structural_uptrend.py
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pickle
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z,
    edge_vs_control, report, round_trip_cost_pct, walk_forward_splits
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
    large_caps = {}

    for t, df in panel.items():
        if df["date"].min() <= pd.Timestamp("2016-12-31"):
            pre_2017.add(t)
        d = df.dropna(subset=["close", "volume", "rsi", "sma_200", "atr", "macd", "macd_signal"]).reset_index(drop=True).copy()
        if len(d) < 300:
            continue
        d["ticker"] = t
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        d["uptrend_200"] = (d["close"] > d["sma_200"]).fillna(False)
        # MACD histogram
        d["macd_hist"] = d["macd"] - d["macd_signal"]
        d["macd_hist_prev"] = d["macd_hist"].shift(1)

        if t in NIFTY_50:
            large_caps[t] = d
        else:
            stocks[t] = d

    return stocks, pre_2017, large_caps


def signal_mask(d):
    """MACD histogram crosses from negative to positive, while MACD < 0 and close > sma_200."""
    hist_cross = (d["macd_hist"] > 0) & (d["macd_hist_prev"] <= 0)
    macd_below_zero = d["macd"] < 0
    uptrend = d["uptrend_200"]
    liq = d["liq"]
    return (hist_cross & macd_below_zero & uptrend & liq).values


def run():
    print("=" * 80)
    print("STRATEGY 037: MACD Histogram Reversal Below Zero in Structural Uptrend (8d)")
    print("=" * 80)

    stocks, pre_2017_all, large_caps = load_data()
    tickers = sorted(stocks.keys())
    pre_2017 = pre_2017_all.intersection(set(tickers))
    later_listed = set(tickers) - pre_2017

    half = len(tickers) // 2
    half_A = set(tickers[:half])
    half_B = set(tickers[half:])

    print(f"Panel: {len(tickers)} Mid/Small liquid stocks, {len(large_caps)} Large caps")
    print(f"Survivorship: {len(pre_2017)} Pre-2017, {len(later_listed)} Later")
    print(f"Subgroups: {len(half_A)} Half A, {len(half_B)} Half B")

    # === 1. Strategy trades ===
    strat_trades = []
    for t, d in stocks.items():
        sig = signal_mask(d)
        trs = simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        for tr in trs:
            tr["ticker"] = t
        strat_trades += trs

    print(f"\n[1] Strategy Trades: {len(strat_trades)}")
    if not strat_trades:
        print("    NO TRADES. Signal fires too rarely. ABORT.")
        return
    gross_ret = np.mean([tr["gross_pct"] for tr in strat_trades])
    net_ret = np.mean([tr["net_pct"] for tr in strat_trades])
    cost_ret = np.mean([tr["cost_pct"] for tr in strat_trades])
    win_rate = np.mean([tr["net_pct"] > 0 for tr in strat_trades]) * 100
    print(f"    Gross Return / Trade : {gross_ret:+.3f}%")
    print(f"    Round-Trip Cost      : {cost_ret:.3f}%")
    print(f"    NET Return / Trade   : {net_ret:+.3f}%")
    print(f"    Win Rate             : {win_rate:.1f}%")

    # Entry date distribution
    entry_dates = pd.to_datetime([tr['entry_date'] for tr in strat_trades])
    n_unique_days = entry_dates.nunique()
    trades_per_day = len(strat_trades) / max(n_unique_days, 1)
    print(f"    Unique entry days    : {n_unique_days}")
    print(f"    Trades/day (avg)     : {trades_per_day:.1f}")

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

    # EARLY KILL: if stable mean z < 1.5, no point continuing
    if mean_z_rnd < 1.5:
        print(f"\n*** EARLY KILL: stable mean z = {mean_z_rnd:+.2f} < 1.5. Not worth further tests. REJECT. ***")
        return

    # === 3. Head-to-Head vs Incumbent RSI<30 (§10) ===
    print("\n[3] Head-to-Head vs Incumbent RSI<30 (§10):")
    inc_trades = []
    for t, d in stocks.items():
        liq = d["liq"].values
        sig = (d["rsi"] < 30) & liq
        trs = simulate_trades(d, sig.values, horizon_days=HORIZON, charge_costs=True)
        for tr in trs:
            tr["ticker"] = t
        inc_trades += trs
    dc_inc = day_clustered_edge(strat_trades, inc_trades)
    if dc_inc:
        print(f"    Incumbent RSI<30 Trades : {len(inc_trades)}")
        print(f"    Incumbent Net Return   : {np.mean([tr['net_pct'] for tr in inc_trades]):+.3f}%")
        print(f"    Day-Clustered z_paired : {dc_inc['z_paired']:+.2f}")
        print(f"    Net Day Edge vs Incumb : {dc_inc['day_edge']:+.3f}%")
        print(f"    Paired Days            : {dc_inc['n_paired_days']}")

    # === 4. Subgroup Tests (§8) ===
    print("\n[4] Subgroup Robustness (§8):")
    strat_A = [tr for tr in strat_trades if tr["ticker"] in half_A]
    strat_B = [tr for tr in strat_trades if tr["ticker"] in half_B]
    zs_A, zs_B = [], []
    for c in controls:
        dc_a = day_clustered_edge(strat_A, [tr for tr in c if tr["ticker"] in half_A])
        dc_b = day_clustered_edge(strat_B, [tr for tr in c if tr["ticker"] in half_B])
        if dc_a:
            zs_A.append(dc_a['z_paired'])
        if dc_b:
            zs_B.append(dc_b['z_paired'])
    if zs_A:
        print(f"    Half A (n={len(strat_A):3d}) : stable mean z = {np.mean(zs_A):+.2f} (pass {np.mean([z >= 2.0 for z in zs_A]) * 100:.0f}%)")
    if zs_B:
        print(f"    Half B (n={len(strat_B):3d}) : stable mean z = {np.mean(zs_B):+.2f} (pass {np.mean([z >= 2.0 for z in zs_B]) * 100:.0f}%)")

    # === 5. Survivorship Check (Pre-2017 listings) ===
    print("\n[5] Survivorship Check (Pre-2017 Listings):")
    strat_pre17 = [tr for tr in strat_trades if tr["ticker"] in pre_2017]
    if strat_pre17:
        zs_pre17 = []
        for c in controls:
            dc_p = day_clustered_edge(strat_pre17, [tr for tr in c if tr["ticker"] in pre_2017])
            if dc_p:
                zs_pre17.append(dc_p['z_paired'])
        if zs_pre17:
            print(f"    Pre-2017 (n={len(strat_pre17):3d}) : stable mean z = {np.mean(zs_pre17):+.2f} (pass {np.mean([z >= 2.0 for z in zs_pre17]) * 100:.0f}%)")

    # === 6. Execution Fragility: Next-Open Entry ===
    print("\n[6] Execution Fragility (Next-Open Entry):")
    strat_no = []
    for t, d in stocks.items():
        sig = signal_mask(d)
        open_ = d["open"].values
        close = d["close"].values
        turnover = d["turnover_60d"].values
        n = len(d)
        last_exit = -1
        for i in range(n - HORIZON - 2):
            if not sig[i] or i <= last_exit:
                continue
            nxt = i + 1
            if nxt + HORIZON >= n:
                break
            entry_price = open_[nxt]
            if entry_price <= 0 or not np.isfinite(entry_price):
                continue
            exit_price = close[nxt + HORIZON]
            gross = (exit_price - entry_price) / entry_price * 100
            cost = round_trip_cost_pct(turnover[nxt])
            strat_no.append({
                'entry_date': d['date'].iat[nxt],
                'gross_pct': gross,
                'net_pct': gross - cost,
                'cost_pct': cost,
                'ticker': t,
            })
            last_exit = nxt + HORIZON

    if strat_no:
        controls_no = []
        for s in range(20):
            rng = np.random.default_rng(s)
            ctrl_no = []
            for t, d in stocks.items():
                liq = d["liq"].values
                rnd = (rng.random(len(d)) < 0.05) & liq
                open_ = d["open"].values
                close = d["close"].values
                turnover = d["turnover_60d"].values
                n = len(d)
                last_exit = -1
                for i in range(n - HORIZON - 2):
                    if not rnd[i] or i <= last_exit:
                        continue
                    nxt = i + 1
                    if nxt + HORIZON >= n:
                        break
                    entry_price = open_[nxt]
                    if entry_price <= 0 or not np.isfinite(entry_price):
                        continue
                    exit_price = close[nxt + HORIZON]
                    gross = (exit_price - entry_price) / entry_price * 100
                    cost = round_trip_cost_pct(turnover[nxt])
                    ctrl_no.append({
                        'entry_date': d['date'].iat[nxt],
                        'net_pct': gross - cost,
                        'ticker': t,
                    })
                    last_exit = nxt + HORIZON
            controls_no.append(ctrl_no)

        zs_no = []
        for c_no in controls_no:
            dc_no = day_clustered_edge(strat_no, c_no)
            if dc_no:
                zs_no.append(dc_no['z_paired'])
        net_no = np.mean([tr["net_pct"] for tr in strat_no])
        print(f"    Next-Open Trades       : {len(strat_no)}")
        print(f"    Next-Open Net Return   : {net_no:+.3f}%")
        if zs_no:
            print(f"    Next-Open Stable Mean z: {np.mean(zs_no):+.2f} (pass {np.mean([z >= 2.0 for z in zs_no]) * 100:.0f}%)")

    # === 7. Walk-Forward Folds (§7) ===
    print("\n[7] Walk-Forward Folds (5 Chronological Folds):")
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
        n_f = len(f_s)
        fold_zs.append(z_f)
        print(f"    Fold {f_idx + 1} ({d0.strftime('%Y-%m')} to {d1.strftime('%Y-%m')}) : Trades={n_f:3d}, z_paired={z_f:+5.2f}, day_edge={edge_f:+.3f}%")
    print(f"    Mean Fold z: {np.mean(fold_zs):+.2f}")

    # === 8. Large-Cap Contrast ===
    print("\n[8] Large-Cap Contrast (Nifty 50):")
    strat_large = []
    ctrl_large = []
    rng_l = np.random.default_rng(42)
    for t, d in large_caps.items():
        sig = signal_mask(d)
        liq = d["liq"].values
        rnd = (rng_l.random(len(d)) < 0.05) & liq
        strat_large += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl_large += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
    if strat_large and ctrl_large:
        dc_large = day_clustered_edge(strat_large, ctrl_large)
        large_net = np.mean([tr["net_pct"] for tr in strat_large])
        print(f"    Large Cap Trades  : {len(strat_large)}, Net Return: {large_net:+.3f}%")
        if dc_large:
            print(f"    Large Cap z_paired: {dc_large['z_paired']:+.2f}, Day Edge: {dc_large['day_edge']:+.3f}%")

    # === SUMMARY ===
    print("\n" + "=" * 80)
    print(f"FINAL SUMMARY:")
    print(f"  Stable Mean z vs Random : {mean_z_rnd:+.2f} (pass {pass_rate_rnd:.0f}%)")
    print(f"  Net Day Edge vs Random  : {mean_edge_rnd:+.3f}%")
    if dc_inc:
        print(f"  z vs Incumbent RSI<30   : {dc_inc['z_paired']:+.2f}")
    print(f"  Mean Fold z             : {np.mean(fold_zs):+.2f}")
    print("=" * 80)


if __name__ == "__main__":
    run()
