"""Strategy 018 - Overnight vs Intraday Tug of War Divergence.

Decomposes the 20-day return into its overnight (prev close -> open) and intraday (open -> close)
components and buys names being accumulated overnight while sold intraday.

Pre-registered: top cross-sectional decile of (on_20 - id_20), on_20 > 0, id_20 < 0, 8-day hold.
No tuned threshold in the entry rule. See the .md for the kill criteria written before the run.

Run:  python strategies/018_overnight_vs_intraday_tug_of_war_divergence.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from data_loader import get_panel
from backtest_engine import (
    simulate_trades, edge_vs_control, day_clustered_edge,
    stable_day_clustered_z, walk_forward_splits, report,
)

UNIVERSE = [
    'ABB.NS', 'ABBOTINDIA.NS', 'ABCAPITAL.NS', 'ABFRL.NS', 'ACC.NS', 'ADANIENT.NS', 'ADANIPORTS.NS', 'ADANIPOWER.NS',
    'ALKEM.NS', 'AMBER.NS', 'AMBUJACEM.NS', 'APLAPOLLO.NS', 'APOLLOHOSP.NS', 'APOLLOTYRE.NS', 'ASHOKLEY.NS',
    'ASIANPAINT.NS', 'ASTRAL.NS', 'AUBANK.NS', 'AUROPHARMA.NS', 'AXISBANK.NS', 'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS',
    'BAJFINANCE.NS', 'BALKRISIND.NS', 'BANDHANBNK.NS', 'BANKBARODA.NS', 'BATAINDIA.NS', 'BEL.NS', 'BEML.NS',
    'BERGEPAINT.NS', 'BHARATFORG.NS', 'BHARTIARTL.NS', 'BHEL.NS', 'BIOCON.NS', 'BPCL.NS', 'BRITANNIA.NS',
    'BSE.NS', 'BSOFT.NS', 'CANBK.NS', 'CANFINHOME.NS', 'CDSL.NS', 'CHOLAFIN.NS', 'CIPLA.NS', 'COALINDIA.NS',
    'COFORGE.NS', 'COLPAL.NS', 'CONCOR.NS', 'COROMANDEL.NS', 'CROMPTON.NS', 'CUB.NS', 'CUMMINSIND.NS',
    'CYIENT.NS', 'DABUR.NS', 'DALBHARAT.NS', 'DEEPAKNTR.NS', 'DIVISLAB.NS', 'DIXON.NS', 'DLF.NS',
    'DRREDDY.NS', 'EICHERMOT.NS', 'GRASIM.NS', 'HCLTECH.NS', 'HDFCBANK.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS',
    'HINDUNILVR.NS', 'ICICIBANK.NS', 'INDUSINDBK.NS', 'INFY.NS', 'ITC.NS', 'JSWSTEEL.NS', 'KOTAKBANK.NS',
    'LALPATHLAB.NS', 'LT.NS', 'M&M.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'NTPC.NS', 'ONGC.NS', 'POWERGRID.NS',
    'RELIANCE.NS', 'SBILIFE.NS', 'SBIN.NS', 'SHRIRAMFIN.NS', 'SUNPHARMA.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS',
    'TCS.NS', 'TECHM.NS', 'TITAN.NS', 'TRENT.NS', 'ULTRACEMCO.NS', 'WIPRO.NS'
]

NIFTY_50 = {
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'SBIN.NS', 'AXISBANK.NS', 'LT.NS', 'ITC.NS',
    'HINDUNILVR.NS', 'MARUTI.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS', 'CIPLA.NS', 'DRREDDY.NS', 'WIPRO.NS',
    'TECHM.NS', 'HCLTECH.NS', 'BAJFINANCE.NS', 'ASIANPAINT.NS', 'ULTRACEMCO.NS', 'GRASIM.NS',
    'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'ADANIPORTS.NS', 'TITAN.NS', 'NESTLEIND.NS', 'BRITANNIA.NS',
    'DIVISLAB.NS', 'EICHERMOT.NS', 'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'BPCL.NS',
    'HEROMOTOCO.NS', 'HINDALCO.NS', 'INDUSINDBK.NS', 'KOTAKBANK.NS', 'M&M.NS', 'SBILIFE.NS',
    'SHRIRAMFIN.NS', 'TRENT.NS', 'APOLLOHOSP.NS', 'COALINDIA.NS',
}

HORIZON = 8
MIN_TURNOVER = 25e7
LOOKBACK = 20
TOP_DECILE = 0.90        # pre-committed convention (Lou/Polk/Skouras deciles), not scanned
CTRL_RATE = 0.08


# ------------------------------------------------------------------ features

def add_flow_features(panel):
    """on_20 / id_20 / tug / ret_20, all known at the close of the bar they sit on."""
    out = {}
    for t, df in panel.items():
        d = df.sort_values('date').reset_index(drop=True).copy()
        d['on_1'] = np.log(d['open'] / d['close'].shift(1))     # overnight leg
        d['id_1'] = np.log(d['close'] / d['open'])              # intraday leg
        d['on_20'] = d['on_1'].rolling(LOOKBACK).sum() * 100
        d['id_20'] = d['id_1'].rolling(LOOKBACK).sum() * 100
        d['tug'] = d['on_20'] - d['id_20']
        d['ret_20'] = d['close'].pct_change(LOOKBACK) * 100
        d['liq'] = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False)
        out[t] = d
    return out


def add_cross_sectional_rank(panel):
    """Daily cross-sectional percentile of `tug` over the LIQUID names only.
    Same-day information across stocks only - no look-ahead in time."""
    long = pd.concat(
        [d.loc[d['liq'] & d['tug'].notna(), ['date', 'tug']].assign(ticker=t)
         for t, d in panel.items()], ignore_index=True)
    long['tug_pct'] = long.groupby('date')['tug'].rank(pct=True)
    by_ticker = {t: g.set_index('date')['tug_pct'] for t, g in long.groupby('ticker')}
    for t, d in panel.items():
        d['tug_pct'] = d['date'].map(by_ticker.get(t, pd.Series(dtype=float)))
    return panel


def valid(d):
    return d.dropna(subset=['close', 'atr', 'on_20', 'id_20', 'tug_pct', 'ret_20']).reset_index(drop=True)


def signal_mask(d, top=TOP_DECILE):
    return ((d['tug_pct'] >= top) & (d['on_20'] > 0) & (d['id_20'] < 0) & d['liq']).values


def ctrl_mask(d, rng):
    return (rng.random(len(d)) < CTRL_RATE) & d['liq'].values


# ------------------------------------------------------------------ helpers

def collect(dfs, mask_fn, horizon=HORIZON):
    tr = []
    for d in dfs:
        tr += simulate_trades(d, mask_fn(d), horizon_days=horizon, charge_costs=True)
    return tr


def ctrl_factory(dfs, horizon=HORIZON):
    def f(seed):
        r = np.random.default_rng(1000 + seed)
        return collect(dfs, lambda d: ctrl_mask(d, r), horizon)
    return f


def show_stable(label, trades, dfs, horizon=HORIZON, seeds=20):
    st = stable_day_clustered_z(trades, ctrl_factory(dfs, horizon), n_seeds=seeds)
    if st:
        print(f"  {label}: n={len(trades):4d}  STABLE mean_z {st['mean_z']:+.2f} "
              f"(min {st['min_z']:+.2f}, max {st['max_z']:+.2f})  pass {st['pass_rate']*100:.0f}%")
    return st


# ------------------------------------------------------------------ run

def run():
    panel = get_panel(UNIVERSE, period="5y", cache_name="nifty_research_150_5y")
    print(f"panel: {len(panel)} stocks\n")
    panel = add_cross_sectional_rank(add_flow_features(panel))
    dfs = {t: valid(d) for t, d in panel.items()}
    dfs = {t: d for t, d in dfs.items() if len(d) >= 300}
    all_dfs = list(dfs.values())
    print(f"usable after warmup: {len(all_dfs)} stocks\n")

    # ---- 1. POOLED
    strat = collect(all_dfs, signal_mask)
    ctrl = ctrl_factory(all_dfs)(42)
    print(report(f"Tug-of-war divergence (POOLED, {HORIZON}d, costs charged)", strat, ctrl,
                 holding_days=HORIZON))
    print()
    show_stable("POOLED", strat, all_dfs)

    # ---- 2. SUBGROUPS (methodology section 8)
    print("\n=== SUBGROUP (sec 8): the tradeable half must clear on its own ===")
    subs = {
        "Mid/Small": [d for t, d in dfs.items() if t not in NIFTY_50],
        "Large(N50)": [d for t, d in dfs.items() if t in NIFTY_50],
    }
    for name, sub in subs.items():
        s = collect(sub, signal_mask)
        c = ctrl_factory(sub)(42)
        ev = edge_vs_control([x['net_pct'] for x in s], [x['net_pct'] for x in c])
        if ev:
            print(f"  {name:11s} net {ev['strategy_avg']:+.3f}%  edge {ev['edge']:+.3f}%  win {ev['win_rate']:.1f}%")
        show_stable(f"  {name}", s, sub)

    # ---- 3. WALK-FORWARD
    print("\n=== WALK-FORWARD (pooled) ===")
    n_bars = min(len(d) for d in all_dfs)
    for k, (_, (te0, te1)) in enumerate(walk_forward_splits(n_bars, n_splits=4, horizon_days=HORIZON), 1):
        fold = [d.iloc[te0:te1].reset_index(drop=True) for d in all_dfs if len(d) >= te1]
        fs = collect(fold, signal_mask)
        r = np.random.default_rng(500 + k)
        fc = collect(fold, lambda d: ctrl_mask(d, r))
        ev = edge_vs_control([x['net_pct'] for x in fs], [x['net_pct'] for x in fc])
        dc = day_clustered_edge(fs, fc)
        if ev and dc:
            print(f"  Fold {k} ({te0}:{te1}) n={len(fs):4d} {dc['n_paired_days']:3d} paired days | "
                  f"net {ev['strategy_avg']:+.2f}% edge {ev['edge']:+.2f}% | "
                  f"z_paired {dc['z_paired']:+.2f} day_edge {dc['day_edge']:+.2f}%")

    # ---- 4. DECILE GRADIENT (kill criterion 4: mechanism, not a lone spike)
    print("\n=== DECILE GRADIENT of tug (mechanism or lone spike?) ===")
    for lo in np.arange(0.0, 1.0, 0.1):
        hi = lo + 0.1
        m = lambda d, lo=lo, hi=hi: ((d['tug_pct'] >= lo) & (d['tug_pct'] < hi + 1e-9) & d['liq']).values
        s = collect(all_dfs, m)
        ev = edge_vs_control([x['net_pct'] for x in s], [x['net_pct'] for x in ctrl])
        dc = day_clustered_edge(s, ctrl)
        if ev and dc:
            print(f"  D{int(round(lo*10))+1:2d} [{lo:.1f}-{hi:.1f}) n={len(s):5d}  net {ev['strategy_avg']:+.3f}%  "
                  f"edge {ev['edge']:+.3f}%  z_paired {dc['z_paired']:+.2f}")

    # ---- 5. MOMENTUM-MATCHED CONTROL (kill criterion 5)
    print("\n=== MOMENTUM-MATCHED CONTROL (just 20-day reversal in a costume?) ===")
    pool = pd.concat([d.assign(ticker=t).reset_index().rename(columns={'index': 'row'})
                      [['row', 'ticker', 'date', 'ret_20', 'tug_pct', 'liq']]
                      for t, d in dfs.items()], ignore_index=True)
    pool = pool[pool['liq']].copy()
    pool['ret_q'] = pool.groupby('date')['ret_20'].rank(pct=True).mul(5).clip(0, 4.999).astype(int)
    sig_dates = pd.DataFrame({'date': sorted({t['entry_date'] for t in strat})})
    want = (pool[pool['tug_pct'] >= TOP_DECILE].merge(sig_dates, on='date')
            .groupby(['date', 'ret_q']).size().rename('k').reset_index())
    cand = pool[pool['tug_pct'] < TOP_DECILE].merge(want, on=['date', 'ret_q'])

    def mm_ctrl(seed):
        picks = (cand.sample(frac=1.0, random_state=3000 + seed)
                 .groupby(['date', 'ret_q'], group_keys=False)
                 .apply(lambda g: g.head(int(g['k'].iloc[0]))))
        trades = []
        for t, g in picks.groupby('ticker'):
            d = dfs[t]
            m = np.zeros(len(d), dtype=bool)
            m[g['row'].values] = True
            trades += simulate_trades(d, m, horizon_days=HORIZON, charge_costs=True,
                                      allow_overlap=True)
        return trades

    mm = mm_ctrl(0)
    ev = edge_vs_control([x['net_pct'] for x in strat], [x['net_pct'] for x in mm])
    if ev:
        print(f"  matched control n={len(mm)} net {ev['control_avg']:+.3f}%  "
              f"strategy {ev['strategy_avg']:+.3f}%  edge {ev['edge']:+.3f}%")
    st = stable_day_clustered_z(strat, mm_ctrl, n_seeds=20)
    if st:
        print(f"  vs MOMENTUM-MATCHED: STABLE mean_z {st['mean_z']:+.2f} "
              f"(min {st['min_z']:+.2f}, max {st['max_z']:+.2f}) pass {st['pass_rate']*100:.0f}%")

    # ---- 6. NEXT-OPEN FILL (kill criterion 6)
    print("\n=== NEXT-OPEN FILL (execution fragility) ===")
    nxt = []
    for d in all_dfs:
        d2 = d.copy()
        d2['close'] = d['open'].shift(-1)
        nxt.append(d2.iloc[:-1].reset_index(drop=True))
    s_open = collect(nxt, signal_mask)
    show_stable("next-open", s_open, nxt)

    # ---- 7. HORIZON BAND 6-10d
    print("\n=== HOLDING-PERIOD BAND (6-10d, the requested swing window) ===")
    for h in (6, 7, 8, 9, 10):
        s = collect(all_dfs, signal_mask, horizon=h)
        show_stable(f"hold {h}d", s, all_dfs, horizon=h, seeds=10)


if __name__ == "__main__":
    run()
