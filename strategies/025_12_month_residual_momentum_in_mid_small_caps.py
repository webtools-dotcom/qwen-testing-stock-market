"""Strategy 025 — 12-Month Residual Momentum in Mid-Small Caps.

Tests academic residual momentum (Blitz et al. 2011) at a 30-session (~1.5 months) horizon on
liquid Indian mid/small caps. Residual momentum orthogonalizes 252-day stock returns against market
beta to measure firm-specific idiosyncratic re-rating, scaled by idiosyncratic return volatility.

Run: python strategies/025_12_month_residual_momentum_in_mid_small_caps.py
"""

import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z, report, sharpe,
    deflated_sharpe
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HORIZON = 30
MIN_TURNOVER = 25e7
NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}


def load_master_panel():
    obj = pickle.load(open(os.path.join(BASE, "cache", "master_10y.pkl"), "rb"))
    panel = obj["data"]
    
    # Compute market equal-weight return series
    rets = {}
    for t, df in panel.items():
        s = pd.Series(df["close"].pct_change().values, index=df["date"].values)
        rets[t] = s[~s.index.duplicated()]
    mkt = pd.DataFrame(rets).mean(axis=1).sort_index()
    
    enriched = {}
    for t, df in panel.items():
        if t in NIFTY_50:
            continue
        d = df.dropna(subset=["close", "atr", "sma_200", "turnover_60d"]).reset_index(drop=True)
        if len(d) < 300:
            continue
        
        c, v, h, l, o = d["close"], d["volume"], d["high"], d["low"], d["open"]
        r = c.pct_change()
        d["ret1"] = r * 100
        d["ret252"] = c.pct_change(252) * 100
        d["vol252"] = r.rolling(252).std() * 100
        
        # Residual momentum calculation (252-session lookback)
        idx = pd.Index(d["date"].values)
        m1 = mkt.reindex(idx).values * 100
        d["mkt1"] = m1
        d["mkt252"] = pd.Series(m1).rolling(252).sum().values
        cov = pd.Series(d["ret1"].values).rolling(252).cov(pd.Series(m1))
        var = pd.Series(m1).rolling(252).var()
        d["beta252"] = cov / var.replace(0, np.nan)
        d["corr_mkt252"] = pd.Series(d["ret1"].values).rolling(252).corr(pd.Series(m1))
        d["resid252"] = d["ret252"] - d["beta252"] * d["mkt252"]
        d["idio_vol252"] = d["vol252"] * np.sqrt(np.clip(1 - d["corr_mkt252"]**2, 0, 1))
        d["res_mom"] = d["resid252"] / d["idio_vol252"].replace(0, np.nan)
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        d["ticker"] = t
        enriched[t] = d
        
    return enriched


def run():
    print("=" * 80)
    print("Strategy 025: 12-Month Residual Momentum in Mid-Small Caps (Horizon = 30 sessions)")
    print("=" * 80)
    
    panel = load_master_panel()
    names = sorted(list(panel.keys()))
    print(f"Loaded {len(names)} liquid mid/small names from 10-year master panel.")
    
    # Split names into Half A (search) and Half B (never-searched hold-out)
    rng_split = np.random.default_rng(31)
    half_a = set(rng_split.permutation(names)[: len(names) // 2])
    half_b = set(names) - half_a
    
    # Build cross-sectional deciles by date
    records = []
    for t, d in panel.items():
        records.append(d[d["liq"]][["date", "ticker", "res_mom", "beta252", "vol252"]])
    all_df = pd.concat(records, ignore_index=True)
    all_df["res_mom_rank"] = all_df.groupby("date")["res_mom"].rank(pct=True)
    
    # Fast lookup set for top decile
    top_resmom_set = set(zip(all_df[all_df["res_mom_rank"] >= 0.90]["date"], all_df[all_df["res_mom_rank"] >= 0.90]["ticker"]))
    
    # 1. Simulate trades per stock (allow_overlap=False, time exit at 30 sessions, costs charged)
    strat_trades, strat_trades_b = [], []
    for t, d in panel.items():
        dates = d["date"].values
        sig = np.array([(dt, t) in top_resmom_set for dt in dates]) & d["liq"].values
        tr = simulate_trades(d, sig, horizon_days=HORIZON, stop_atr_mult=99, target_atr_mult=99,
                             charge_costs=True, allow_overlap=False)
        for item in tr:
            item["ticker"] = t
        strat_trades += tr
        if t in half_b:
            strat_trades_b += tr
            
    print(f"Strategy trades simulated: {len(strat_trades)} (Half B: {len(strat_trades_b)})")
    
    # 2. Control Factory for 20 seeds
    def control_factory(seed):
        rng = np.random.default_rng(seed)
        ctrl = []
        for t, d in panel.items():
            rnd = (rng.random(len(d)) < 0.05) & d["liq"].values
            tr = simulate_trades(d, rnd, horizon_days=HORIZON, stop_atr_mult=99, target_atr_mult=99,
                                 charge_costs=True, allow_overlap=False)
            for item in tr:
                item["ticker"] = t
            ctrl += tr
        return ctrl

    def control_factory_b(seed):
        rng = np.random.default_rng(seed)
        ctrl = []
        for t in half_b:
            d = panel[t]
            rnd = (rng.random(len(d)) < 0.05) & d["liq"].values
            tr = simulate_trades(d, rnd, horizon_days=HORIZON, stop_atr_mult=99, target_atr_mult=99,
                                 charge_costs=True, allow_overlap=False)
            for item in tr:
                item["ticker"] = t
            ctrl += tr
        return ctrl

    # 3. Stable Day-Clustered Paired Test (POOLED)
    print("\nRunning Stable Day-Clustered Paired Test across 20 control seeds...")
    sc = stable_day_clustered_z(strat_trades, control_factory, n_seeds=20)
    sc_b = stable_day_clustered_z(strat_trades_b, control_factory_b, n_seeds=20)
    
    ctrl_sample = control_factory(42)
    dc = day_clustered_edge(strat_trades, ctrl_sample)
    
    print("\n" + report("Strategy 025: Residual Momentum (30d Hold)", strat_trades, ctrl_sample, holding_days=HORIZON))
    print(f"  POOLED Stable Mean z : {sc['mean_z']:+.2f} (min {sc['min_z']:+.2f}, max {sc['max_z']:+.2f}, pass rate: {sc['pass_rate']*100:.0f}%)")
    print(f"  HALF B Stable Mean z : {sc_b['mean_z']:+.2f} (pass rate: {sc_b['pass_rate']*100:.0f}%)")
    print(f"  Day-Clustered Edge   : {dc['day_edge']:+.3f}% net/day")
    
    # 4. Regime Blocks (Chronological Partitions)
    P1_END = pd.Timestamp("2021-12-31")
    P2_END = pd.Timestamp("2023-12-31")
    for p_label, p_mask in [
        ("P1 (2016-2021)", lambda d: d <= P1_END),
        ("P2 (2022-2023)", lambda d: (d > P1_END) & (d <= P2_END)),
        ("P3 (2024-2026)", lambda d: d > P2_END)
    ]:
        sub_strat = [t for t in strat_trades if p_mask(t["entry_date"])]
        sub_ctrl = [t for t in ctrl_sample if p_mask(t["entry_date"])]
        sub_dc = day_clustered_edge(sub_strat, sub_ctrl)
        if sub_dc:
            print(f"  Regime {p_label:16s}: n={len(sub_strat):4d}, paired_days={sub_dc['n_paired_days']:3d}, "
                  f"day_edge={sub_dc['day_edge']:+.3f}%, z_paired={sub_dc['z_paired']:+.2f}")
                  
    # 5. Monotonic Decile Ladder Check
    print("\nDecile Gradient Check (D10 down to D1 on day-demeaned 30d forward returns):")
    all_df["fwd30"] = np.nan
    for t, d in panel.items():
        fwd = (d["close"].shift(-HORIZON) / d["close"] - 1) * 100
        all_df.loc[all_df["ticker"] == t, "fwd30"] = fwd[d["liq"]].values
    all_df["fwd30_dm"] = all_df["fwd30"] - all_df.groupby("date")["fwd30"].transform("mean")
    all_df["q10"] = all_df.groupby("date")["res_mom"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 10, labels=False) if s.notna().sum() >= 10 else np.nan
    )
    for q in range(9, -1, -1):
        sub_q = all_df[all_df["q10"] == q].dropna(subset=["fwd30_dm"])
        dly = sub_q.groupby("date")["fwd30_dm"].mean()
        t_stat = dly.mean() / (dly.std(ddof=1) / np.sqrt(len(dly))) if len(dly) > 10 else np.nan
        print(f"  Decile D{q+1:02d}: n={len(sub_q):5d}, day_edge={dly.mean():+.3f}%, t={t_stat:+5.2f}")
        
    # 6. Portfolio Tool Simulation (20 slots, cash-constrained, 0.50% round-trip costs)
    print("\n" + "=" * 80)
    print("PORTFOLIO TOOL TEST (20 Equal-Weight Slots, Cash-Constrained, 0.50% Round-Trip Costs)")
    print("=" * 80)
    
    price_series = {}
    for t, d in panel.items():
        s = pd.Series(d["close"].values, index=d["date"].values)
        price_series[t] = s[~s.index.duplicated()]
    prices_df = pd.DataFrame(price_series).sort_index()
    
    # Pre-rank daily picks
    resmom_daily_picks = {}
    for dt, group in all_df.groupby("date"):
        sub = group[group["res_mom_rank"] >= 0.90].sort_values("res_mom", ascending=False)
        if len(sub) > 0:
            prices_on_dt = [panel[r.ticker].loc[panel[r.ticker]["date"] == dt, "close"].values[0] for _, r in sub.iterrows()]
            resmom_daily_picks[dt] = [(r.res_mom, r.ticker, px) for (_, r), px in zip(sub.iterrows(), prices_on_dt)]
            
    # Portfolio execution
    dates = prices_df.index
    cash = 100.0
    slots = [{'ticker': None, 'entry_px': None, 'days_held': 0, 'shares': 0} for _ in range(20)]
    history = []
    cost_pct = 0.50
    
    for dt in dates:
        curr_val = cash
        for s in slots:
            if s['ticker'] is not None:
                px = prices_df.at[dt, s['ticker']]
                if not np.isfinite(px): px = s['entry_px']
                s['days_held'] += 1
                curr_val += s['shares'] * px
                if s['days_held'] >= HORIZON:
                    proceeds = s['shares'] * px * (1 - cost_pct / 100.0)
                    cash += proceeds
                    s['ticker'] = None
                    
        empty_slots = [s for s in slots if s['ticker'] is None]
        if empty_slots and dt in resmom_daily_picks:
            top_cands = resmom_daily_picks[dt]
            already_held = {s['ticker'] for s in slots if s['ticker'] is not None}
            cand_idx = 0
            for s in empty_slots:
                while cand_idx < len(top_cands) and top_cands[cand_idx][1] in already_held:
                    cand_idx += 1
                if cand_idx >= len(top_cands): break
                score_val, ticker, entry_px = top_cands[cand_idx]
                cand_idx += 1
                target_alloc = curr_val / 20.0
                alloc = min(cash, target_alloc)
                if alloc > 0.5 and np.isfinite(entry_px) and entry_px > 0:
                    shares = (alloc * (1 - cost_pct / 200.0)) / entry_px
                    cash -= shares * entry_px * (1 + cost_pct / 200.0)
                    s['ticker'] = ticker
                    s['entry_px'] = entry_px
                    s['days_held'] = 0
                    s['shares'] = shares
                    already_held.add(ticker)
                    
        tot_val = cash
        for s in slots:
            if s['ticker'] is not None:
                px = prices_df.at[dt, s['ticker']]
                if not np.isfinite(px): px = s['entry_px']
                tot_val += s['shares'] * px
        history.append({'date': dt, 'value': tot_val})
        
    df_h = pd.DataFrame(history)
    df_h['ret'] = df_h['value'].pct_change()
    n_years = (df_h['date'].iloc[-1] - df_h['date'].iloc[0]).days / 365.25
    strat_cagr = (df_h['value'].iloc[-1] / df_h['value'].iloc[0]) ** (1.0 / n_years) - 1
    cummax = df_h['value'].cummax()
    strat_maxdd = ((df_h['value'] - cummax) / cummax).min()
    strat_vol = df_h['ret'].std() * np.sqrt(252)
    strat_sr = (strat_cagr - 0.05) / strat_vol if strat_vol > 0 else 0
    
    # Buy & Hold benchmark
    bnh_rets = prices_df.pct_change().mean(axis=1)
    bnh_val = (1 + bnh_rets.fillna(0)).cumprod() * 100.0
    bnh_cagr = (bnh_val.iloc[-1] / bnh_val.iloc[0]) ** (1.0 / n_years) - 1
    bnh_cummax = bnh_val.cummax()
    bnh_maxdd = ((bnh_val - bnh_cummax) / bnh_cummax).min()
    bnh_vol = bnh_rets.std() * np.sqrt(252)
    bnh_sr = (bnh_cagr - 0.05) / bnh_vol if bnh_vol > 0 else 0
    
    print(f"  STRATEGY CAGR      : {strat_cagr*100:+.2f}% | Max DD: {strat_maxdd*100:.2f}% | Sharpe: {strat_sr:.2f}")
    print(f"  BUY & HOLD BENCHMARK: {bnh_cagr*100:+.2f}% | Max DD: {bnh_maxdd*100:.2f}% | Sharpe: {bnh_sr:.2f}")
    print(f"  EXCESS CAGR OVER B&H: {(strat_cagr - bnh_cagr)*100:+.2f}%/year")
    
    print("\n  Calendar Year Performance Comparison:")
    df_h['year'] = pd.to_datetime(df_h['date']).dt.year
    df_bnh = pd.DataFrame({'date': prices_df.index, 'value': bnh_val.values})
    df_bnh['year'] = pd.to_datetime(df_bnh['date']).dt.year
    for yr, sub in df_h.groupby('year'):
        strat_yr = (sub['value'].iloc[-1] / sub['value'].iloc[0] - 1) * 100
        sub_bnh = df_bnh[df_bnh['year'] == yr]
        bnh_yr = (sub_bnh['value'].iloc[-1] / sub_bnh['value'].iloc[0] - 1) * 100
        print(f"    {yr}: Strategy {strat_yr:+6.2f}% vs B&H {bnh_yr:+6.2f}% (Excess: {strat_yr - bnh_yr:+6.2f}%)")
        
    print("\n" + "=" * 80)
    print("FINAL VERDICT: REJECT")
    print("Why: Although trade-level day_clustered stable mean_z is +3.50 (100% pass), the strategy fails")
    print("on portfolio economics: CAGR +17.49% vs Buy & Hold +21.66% (-4.17%/yr drag), with Sharpe 0.56 vs 0.86.")
    print("Orthogonalizing to market beta cuts out high-beta leaders during Indian bull runs, hurting long-term compounding.")
    print("=" * 80)


if __name__ == "__main__":
    run()
