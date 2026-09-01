"""Strategy 029 — Intraday Absorption Pullback in Trend Consistency Leaders.

Hypothesis:
In Indian mid/small caps, institutional trend leaders (top 15% of 252-day Trend Consistency / Sharpe)
experience brief multi-day pullbacks (RSI < 40) due to broad market noise or sector rotation. When buyers
absorb the selling intraday (lower wick >= 35% of bar range or green close), the underlying institutional
drift reasserts itself over a 6-10 day swing horizon (baseline h=8 sessions).

Rules and kill criteria are pre-registered in strategies/029_intraday_absorption_pullback_in_trend_consistency_leaders.md.
Run:  python strategies/029_intraday_absorption_pullback_in_trend_consistency_leaders.py
"""

import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z,
    walk_forward_splits, round_trip_cost_pct
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
    path = os.path.join(BASE, "cache", "broad_nse_10y.pkl")
    p = pickle.load(open(path, "rb"))
    panel = p["data"] if isinstance(p, dict) and "data" in p else p
    return panel


def prepare_panel(panel):
    records = []
    for t, df in panel.items():
        if t in NIFTY_50:
            continue
        d = df.copy().reset_index(drop=True)
        if len(d) < 260:
            continue
        d["ticker"] = t
        d["ret1"] = d["close"].pct_change()
        d["vol60"] = d["ret1"].rolling(60).std() * 100
        d["sharpe252"] = (d["ret1"].rolling(252).mean() / d["ret1"].rolling(252).std().replace(0, np.nan)) * np.sqrt(252)
        
        # Intraday range & wick
        rng = (d["high"] - d["low"]).replace(0, np.nan)
        d["lower_wick"] = (np.minimum(d["open"], d["close"]) - d["low"]) / rng
        d["body_pct"] = (d["close"] - d["open"]) / d["open"] * 100
        
        records.append(d)

    all_df = pd.concat(records, ignore_index=True)
    liq_mask = (all_df["turnover_60d"] >= MIN_TURNOVER).fillna(False)

    elig = all_df[liq_mask].copy()
    all_df.loc[elig.index, "rank_trend"] = elig.groupby("date")["sharpe252"].rank(pct=True)

    stocks = {}
    for t, group in all_df.groupby("ticker"):
        g = group.sort_values("date").reset_index(drop=True)
        g["liq"] = (g["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        stocks[t] = g
    return stocks


def signal_mask(d, trend_q=0.85, rsi_th=40, wick_th=0.35):
    m = (
        (d["rank_trend"] >= trend_q) &
        (d["rsi"] < rsi_th) &
        ((d["lower_wick"] >= wick_th) | (d["close"] > d["open"])) &
        (d["close"] > d["sma_200"])
    )
    return m.fillna(False).values & d["liq"].values


def run_set(sub_stocks, trend_q=0.85, rsi_th=40, wick_th=0.35, horizon=HORIZON, next_open=False, seeds=20):
    strat = []
    for t, d in sub_stocks.items():
        sig = signal_mask(d, trend_q, rsi_th, wick_th)
        if next_open:
            sig = np.roll(sig, 1)
            sig[0] = False
        strat += simulate_trades(d, sig, horizon_days=horizon, charge_costs=True)

    if len(strat) < 20:
        return None

    def control_factory(seed):
        r = np.random.default_rng(1000 + seed)
        ctrl = []
        for t, d in sub_stocks.items():
            rnd = d["liq"].values & (r.random(len(d)) < 0.10)
            ctrl += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        return ctrl

    st = stable_day_clustered_z(strat, control_factory, n_seeds=seeds)
    c0 = control_factory(0)
    dc = day_clustered_edge(strat, c0)

    s_net = np.array([tr["net_pct"] for tr in strat])
    c_net = np.array([tr["net_pct"] for tr in c0])

    return {
        "n": len(strat),
        "days": dc["n_paired_days"] if dc else 0,
        "gross": float(np.mean([t["gross_pct"] for t in strat])),
        "cost": float(np.mean([t["cost_pct"] for t in strat])),
        "net": float(s_net.mean()),
        "ctrl_net": float(c_net.mean()),
        "edge": float(s_net.mean() - c_net.mean()),
        "win": float((s_net > 0).mean() * 100),
        "mean_z": st["mean_z"] if st else 0.0,
        "pass_rate": st["pass_rate"] if st else 0.0,
        "min_z": st["min_z"] if st else 0.0,
        "max_z": st["max_z"] if st else 0.0,
        "day_edge": dc["day_edge"] if dc else 0.0,
    }


def simulate_portfolio(stocks, max_slots=20, horizon=8, cost_mult=1.0):
    all_events = []
    for t, d in stocks.items():
        sig = signal_mask(d)
        trades = simulate_trades(d, sig, horizon_days=horizon, charge_costs=False)
        for tr in trades:
            c_pct = round_trip_cost_pct(d["turnover_60d"].iloc[tr["entry_idx"]]) * cost_mult
            all_events.append({
                "ticker": t,
                "entry_date": tr["entry_date"],
                "exit_idx": tr["exit_idx"],
                "gross_pct": tr["gross_pct"],
                "net_pct": tr["gross_pct"] - c_pct,
                "held": tr["held"],
            })

    if not all_events:
        return None

    ev_df = pd.DataFrame(all_events).sort_values("entry_date").reset_index(drop=True)
    dates = sorted(list({d for s in stocks.values() for d in s["date"]}))
    date_to_idx = {d: i for i, d in enumerate(dates)}

    slots = [None] * max_slots
    daily_values = []
    nav = 100.0

    events_by_date = ev_df.groupby("entry_date")

    for dt in dates:
        for s_i in range(max_slots):
            if slots[s_i] is not None:
                pos = slots[s_i]
                if dt >= pos["exit_date"]:
                    slot_ret = pos["net_pct"] / 100.0
                    pos_alloc = pos["nav_at_entry"] / max_slots
                    pnl = pos_alloc * slot_ret
                    nav += pnl
                    slots[s_i] = None

        if dt in events_by_date.groups:
            day_evs = events_by_date.get_group(dt)
            for _, row in day_evs.iterrows():
                empty_slot = None
                for s_i in range(max_slots):
                    if slots[s_i] is None:
                        empty_slot = s_i
                        break
                if empty_slot is not None:
                    curr_idx = date_to_idx.get(dt, 0)
                    exit_d = dates[min(curr_idx + row["held"], len(dates) - 1)]
                    slots[empty_slot] = {
                        "ticker": row["ticker"],
                        "nav_at_entry": nav,
                        "exit_date": exit_d,
                        "net_pct": row["net_pct"],
                    }

        daily_values.append(nav)

    nav_series = pd.Series(daily_values, index=dates)
    years = (dates[-1] - dates[0]).days / 365.25
    cagr = ((nav_series.iloc[-1] / nav_series.iloc[0]) ** (1.0 / max(years, 0.5)) - 1.0) * 100.0
    daily_rets = nav_series.pct_change().dropna()
    sharpe = (daily_rets.mean() / daily_rets.std() * np.sqrt(252)) if daily_rets.std() > 0 else 0.0
    cum_max = nav_series.cummax()
    max_dd = ((nav_series - cum_max) / cum_max).min() * 100.0

    return {
        "cagr": cagr,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "total_trades": len(ev_df),
        "final_nav": nav_series.iloc[-1],
    }


def main():
    print("Loading data...", flush=True)
    stocks = prepare_panel(load_data())

    names = sorted(stocks.keys())
    rng = np.random.default_rng(23)
    half_A = set(rng.permutation(names)[: len(names) // 2])
    half_B = set(names) - half_A
    pre_2017 = {t for t, d in stocks.items() if d["date"].min() <= pd.Timestamp("2017-01-01")}

    print(f"Panel: {len(stocks)} stocks, Half A: {len(half_A)}, Half B: {len(half_B)}, Pre-2017: {len(pre_2017)}\n", flush=True)

    print("=== 1. Headline Engine Run (Full 10y Pooled) ===", flush=True)
    res = run_set(stocks, seeds=20)
    if res:
        print(f"Trades              : {res['n']}")
        print(f"Paired Days         : {res['days']}")
        print(f"Gross avg / trade   : {res['gross']:+.3f}%")
        print(f"Round-trip cost     : {res['cost']:.3f}%")
        print(f"NET avg / trade     : {res['net']:+.3f}%")
        print(f"Control avg / trade : {res['ctrl_net']:+.3f}%")
        print(f"Net edge vs control : {res['edge']:+.3f}%")
        print(f"Win rate            : {res['win']:.1f}%")
        print(f"Stable Mean z_paired: {res['mean_z']:+5.2f} (pass rate: {res['pass_rate']*100:.0f}%, range [{res['min_z']:+.2f}, {res['max_z']:+.2f}])")
        print(f"Day edge            : {res['day_edge']:+.3f}%\n", flush=True)

    print("=== 2. Kill Checks: Half B & Survivorship ===", flush=True)
    res_B = run_set({t: stocks[t] for t in half_B}, seeds=10)
    if res_B:
        print(f"Holdout Half B : N={res_B['n']:4d} Days={res_B['days']:4d} Net={res_B['net']:+.3f}% Mean_z={res_B['mean_z']:+5.2f} (pass {res_B['pass_rate']*100:.0f}%)", flush=True)

    res_pre = run_set({t: stocks[t] for t in pre_2017}, seeds=10)
    if res_pre:
        print(f"Pre-2017 Only  : N={res_pre['n']:4d} Days={res_pre['days']:4d} Net={res_pre['net']:+.3f}% Mean_z={res_pre['mean_z']:+5.2f} (pass {res_pre['pass_rate']*100:.0f}%)\n", flush=True)

    print("=== 3. Execution Fragility: Next-Open Fill ===", flush=True)
    res_next = run_set(stocks, next_open=True, seeds=10)
    if res_next:
        print(f"Next-Open Entry: N={res_next['n']:4d} Days={res_next['days']:4d} Net={res_next['net']:+.3f}% Mean_z={res_next['mean_z']:+5.2f} (pass {res_next['pass_rate']*100:.0f}%)\n", flush=True)

    print("=== 4. Holding Horizon Sensitivity ===", flush=True)
    for h in [6, 8, 10, 12]:
        rh = run_set(stocks, horizon=h, seeds=10)
        if rh:
            print(f"Horizon {h:2d}d: N={rh['n']:4d} Net={rh['net']:+.3f}% Day_edge={rh['day_edge']:+.3f}% Mean_z={rh['mean_z']:+5.2f} (pass {rh['pass_rate']*100:.0f}%)", flush=True)

    print("\n=== 5. Walk-Forward 5 Folds ===", flush=True)
    dates = sorted({d for dd in stocks.values() for d in dd["date"]})
    for k, (tr, te) in enumerate(walk_forward_splits(len(dates), n_splits=5, horizon_days=HORIZON)):
        if len(te) == 0:
            continue
        f_lo, f_hi = dates[te[0]], dates[te[-1]]
        f_sub = {t: d[(d["date"] >= f_lo) & (d["date"] <= f_hi)].reset_index(drop=True) for t, d in stocks.items()}
        rf = run_set(f_sub, seeds=10)
        if rf:
            print(f"Fold {k+1} ({f_lo.date()}..{f_hi.date()}): N={rf['n']:4d} Days={rf['days']:4d} Net={rf['net']:+.3f}% Day_edge={rf['day_edge']:+.3f}% Mean_z={rf['mean_z']:+5.2f}", flush=True)

    print("\n=== 6. Portfolio Tool Test (20 Slots) ===", flush=True)
    p_10 = simulate_portfolio(stocks, max_slots=20, horizon=8, cost_mult=1.0)
    p_15 = simulate_portfolio(stocks, max_slots=20, horizon=8, cost_mult=1.5)
    p_20 = simulate_portfolio(stocks, max_slots=20, horizon=8, cost_mult=2.0)
    if p_10:
        print(f"Portfolio (1.0x costs): CAGR={p_10['cagr']:+.2f}%, Sharpe={p_10['sharpe']:.2f}, MaxDD={p_10['max_dd']:.2f}%, Trades={p_10['total_trades']}", flush=True)
    if p_15:
        print(f"Portfolio (1.5x costs): CAGR={p_15['cagr']:+.2f}%, Sharpe={p_15['sharpe']:.2f}, MaxDD={p_15['max_dd']:.2f}%", flush=True)
    if p_20:
        print(f"Portfolio (2.0x costs): CAGR={p_20['cagr']:+.2f}%, Sharpe={p_20['sharpe']:.2f}, MaxDD={p_20['max_dd']:.2f}%", flush=True)


if __name__ == "__main__":
    main()

