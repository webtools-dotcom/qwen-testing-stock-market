import os, sys, pickle
import numpy as np
import pandas as pd
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from backtest_engine import simulate_trades, day_clustered_edge, stable_day_clustered_z
NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}

MIN_TURNOVER = 25e7
HOLD = 30  # ~1.5 months (30 trading sessions)

def load_data():
    obj = pickle.load(open(os.path.join(BASE, "cache", "master_10y.pkl"), "rb"))
    panel = obj["data"] if isinstance(obj, dict) and "data" in obj else obj
    return panel

def prepare(panel):
    prepped = {}
    for t, df in panel.items():
        d = df.copy().reset_index(drop=True)
        d["ticker"] = t
        d["mid_small"] = t not in NIFTY_50
        r = d["close"].pct_change()
        d["vol60"] = r.rolling(60).std() * 100
        
        # 1. 52w high nearness
        high_252 = d["high"].rolling(252).max()
        d["near_52w"] = d["close"] / high_252
        
        # 2. 252-day t-stat
        d["tstat_252"] = (r.rolling(252).mean() / (r.rolling(252).std() + 1e-8)) * np.sqrt(252)
        
        # 3. 3-Month risk-adjusted momentum (63 sessions)
        ret_63 = d["close"] / d["close"].shift(63) - 1.0
        d["mom_63_adj"] = ret_63 / (d["vol60"] + 1e-4)
        
        # 4. 6-Month risk-adjusted momentum (126 sessions)
        ret_126 = d["close"] / d["close"].shift(126) - 1.0
        d["mom_126_adj"] = ret_126 / (d["vol60"] + 1e-4)

        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        prepped[t] = d
        
    flat = pd.concat([d[["date", "ticker", "liq", "mid_small", "near_52w", "tstat_252", "mom_63_adj", "mom_126_adj"]]
                      for d in prepped.values()], ignore_index=True)
    elig = flat[flat["liq"] & flat["mid_small"]]
    
    # Cross sectional ranking
    for feat in ["near_52w", "tstat_252", "mom_63_adj", "mom_126_adj"]:
        flat.loc[elig.index, f"rank_{feat}"] = elig.groupby("date")[feat].rank(pct=True)
        
    flat.loc[elig.index, "rank_comp_52w_tstat"] = (flat.loc[elig.index, "rank_near_52w"] + flat.loc[elig.index, "rank_tstat_252"]) / 2.0
    
    key = flat.set_index(["ticker", "date"])
    for t, d in prepped.items():
        sub = key.loc[t]
        idx = pd.Index(d["date"].values)
        for c in ["rank_near_52w", "rank_tstat_252", "rank_mom_63_adj", "rank_mom_126_adj", "rank_comp_52w_tstat"]:
            d[c] = sub[c].reindex(idx).values
            
    return prepped

def run_strategy(prepped, rank_col, top_pct=0.90, horizon=HOLD):
    strat = []
    stocks = []
    for t, d in prepped.items():
        if t in NIFTY_50:
            continue
        sig = (d[rank_col] >= top_pct) & d["liq"]
        sig = sig.fillna(False).values
        t_trades = simulate_trades(d, sig, horizon_days=horizon, charge_costs=True,
                                  stop_atr_mult=99.0, target_atr_mult=99.0)
        strat += t_trades
        stocks.append(d)
        
    def control_factory(seed):
        rng = np.random.default_rng(1000 + seed)
        ctrl = []
        for d in stocks:
            rnd = d["liq"].values & (rng.random(len(d)) < 0.10)
            ctrl += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True,
                                   stop_atr_mult=99.0, target_atr_mult=99.0)
        return ctrl

    return strat, control_factory

def portfolio_test(prepped, rank_col, top_pct=0.90, horizon=HOLD, cost_rt=0.0050):
    # Simulate a realistic 20-slot equal weight cash portfolio
    # Get all dates
    all_dates = sorted({dt for d in prepped.values() for dt in d["date"]})
    df_map = {t: d.set_index("date") for t, d in prepped.items() if t not in NIFTY_50}
    
    cash = 100.0
    n_slots = 20
    slot_cap = 100.0 / n_slots
    positions = {} # ticker -> {'entry_date': dt, 'entry_price': p, 'bars_held': 0, 'shares': s}
    
    port_values = []
    
    for dt in all_dates:
        # 1. Update existing positions & check exits
        to_close = []
        pos_val = 0.0
        for t, pos in list(positions.items()):
            if dt not in df_map[t].index:
                continue
            bar = df_map[t].loc[dt]
            pos["bars_held"] += 1
            cur_price = bar["close"]
            pos_val += pos["shares"] * cur_price
            
            if pos["bars_held"] >= horizon:
                # Exit at close minus half cost
                exit_proceeds = pos["shares"] * cur_price * (1.0 - cost_rt / 2.0)
                cash += exit_proceeds
                to_close.append(t)
                
        for t in to_close:
            del positions[t]
            
        # 2. Check candidate entries if slots available
        open_slots = n_slots - len(positions)
        if open_slots > 0:
            candidates = []
            for t, df_t in df_map.items():
                if t in positions:
                    continue
                if dt in df_t.index:
                    bar = df_t.loc[dt]
                    if bar["liq"] and bar[rank_col] >= top_pct:
                        candidates.append((t, bar["close"], bar[rank_col]))
                        
            # Sort by rank score descending
            candidates.sort(key=lambda x: x[2], reverse=True)
            for t, price, score in candidates[:open_slots]:
                alloc = min(cash / max(1, open_slots), cash)
                if alloc > 1.0: # min position size
                    entry_cost = alloc * (cost_rt / 2.0)
                    invest_amt = alloc - entry_cost
                    cash -= alloc
                    shares = invest_amt / price
                    positions[t] = {'entry_date': dt, 'entry_price': price, 'bars_held': 0, 'shares': shares}
                    
        # Total portfolio equity
        pos_val = 0.0
        for t, pos in positions.items():
            if dt in df_map[t].index:
                pos_val += pos["shares"] * df_map[t].loc[dt]["close"]
        total_equity = cash + pos_val
        port_values.append((dt, total_equity))
        
    ts = pd.Series([v for dt, v in port_values], index=[dt for dt, v in port_values])
    rets = ts.pct_change().dropna()
    cagr = (ts.iloc[-1] / ts.iloc[0]) ** (252.0 / len(ts)) - 1.0
    sharpe_ratio = rets.mean() / (rets.std() + 1e-8) * np.sqrt(252)
    dd = (ts / ts.cummax() - 1.0).min()
    return {'cagr': cagr, 'sharpe': sharpe_ratio, 'max_dd': dd, 'series': ts}

def main():
    panel = load_data()
    prepped = prepare(panel)
    
    candidates = [
        ("Near 52W High (George-Hwang)", "rank_near_52w"),
        ("252d Trend T-Stat / Sharpe", "rank_tstat_252"),
        ("3-Month Risk-Adj Momentum (63d)", "rank_mom_63_adj"),
        ("6-Month Risk-Adj Momentum (126d)", "rank_mom_126_adj"),
        ("Composite (52w High + T-Stat)", "rank_comp_52w_tstat"),
    ]
    
    print(f"================ CANDIDATE TESTING (HOLD = {HOLD} SESSIONS) ================\n")
    print(f"{'Candidate':<32} | {'Trades':<6} | {'Days':<5} | {'Mean z':<7} | {'Pass%':<5} | {'Net Edge':<9} | {'Portfolio CAGR':<14} | {'Sharpe':<6} | {'Max DD':<8}")
    print("-" * 115)
    
    for label, col in candidates:
        strat, cf = run_strategy(prepped, col, top_pct=0.90, horizon=HOLD)
        st = stable_day_clustered_z(strat, cf, n_seeds=20)
        ctrl = cf(0)
        dc = day_clustered_edge(strat, ctrl)
        
        # Portfolio test
        pf = portfolio_test(prepped, col, top_pct=0.90, horizon=HOLD)
        
        print(f"{label:<32} | {len(strat):<6d} | {dc['n_paired_days']:<5d} | {st['mean_z']:>+6.2f} | {st['pass_rate']*100:>4.0f}% | {dc['day_edge']:>+8.3f}% | {pf['cagr']*100:>+13.2f}% | {pf['sharpe']:>5.2f} | {pf['max_dd']*100:>7.1f}%")

if __name__ == "__main__":
    main()
