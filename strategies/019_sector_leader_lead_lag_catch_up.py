"""Strategy 019 - Sector Leader Lead-Lag Catch-Up.

Buys the liquid NON-leader in a sector whose highest-turnover peers have already moved up over
the last 5 sessions, on the hypothesis that industry information diffuses to under-covered
followers with a lag (Hou 2007). Pre-registered rules and kill criteria in the .md - in
particular the two matched controls (reversal-matched, sector-day-matched) that decide whether
this is anything more than short-term reversal or hot-sector beta.

Run:  python strategies/019_sector_leader_lead_lag_catch_up.py
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

# ---------------------------------------------------------------- universe + static sector map
SECTORS = {
    'IT': ['TCS.NS', 'INFY.NS', 'HCLTECH.NS', 'WIPRO.NS', 'TECHM.NS', 'LTIM.NS', 'COFORGE.NS',
           'PERSISTENT.NS', 'MPHASIS.NS', 'BSOFT.NS', 'CYIENT.NS', 'KPITTECH.NS', 'TATAELXSI.NS'],
    'BANK': ['HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'AXISBANK.NS', 'KOTAKBANK.NS', 'INDUSINDBK.NS',
             'BANKBARODA.NS', 'CANBK.NS', 'PNB.NS', 'FEDERALBNK.NS', 'IDFCFIRSTB.NS', 'AUBANK.NS',
             'BANDHANBNK.NS', 'CUB.NS', 'RBLBANK.NS'],
    'NBFC': ['BAJFINANCE.NS', 'BAJAJFINSV.NS', 'CHOLAFIN.NS', 'SHRIRAMFIN.NS', 'MUTHOOTFIN.NS',
             'MANAPPURAM.NS', 'LICHSGFIN.NS', 'CANFINHOME.NS', 'PFC.NS', 'RECLTD.NS', 'ABCAPITAL.NS'],
    'AUTO': ['MARUTI.NS', 'M&M.NS', 'TATAMOTORS.NS', 'BAJAJ-AUTO.NS', 'HEROMOTOCO.NS', 'EICHERMOT.NS',
             'TVSMOTOR.NS', 'ASHOKLEY.NS', 'BHARATFORG.NS', 'MOTHERSON.NS', 'BALKRISIND.NS',
             'APOLLOTYRE.NS', 'MRF.NS', 'EXIDEIND.NS'],
    'PHARMA': ['SUNPHARMA.NS', 'DRREDDY.NS', 'CIPLA.NS', 'DIVISLAB.NS', 'LUPIN.NS', 'AUROPHARMA.NS',
               'TORNTPHARM.NS', 'ALKEM.NS', 'GLENMARK.NS', 'ZYDUSLIFE.NS', 'IPCALAB.NS',
               'LAURUSLABS.NS', 'BIOCON.NS', 'ABBOTINDIA.NS', 'GRANULES.NS'],
    'FMCG': ['HINDUNILVR.NS', 'ITC.NS', 'NESTLEIND.NS', 'BRITANNIA.NS', 'DABUR.NS', 'MARICO.NS',
             'GODREJCP.NS', 'COLPAL.NS', 'TATACONSUM.NS', 'EMAMILTD.NS', 'VBL.NS'],
    'METAL': ['TATASTEEL.NS', 'JSWSTEEL.NS', 'HINDALCO.NS', 'VEDL.NS', 'JINDALSTEL.NS', 'SAIL.NS',
              'NMDC.NS', 'NATIONALUM.NS', 'HINDZINC.NS', 'APLAPOLLO.NS', 'RATNAMANI.NS'],
    'CEMENT': ['ULTRACEMCO.NS', 'SHREECEM.NS', 'AMBUJACEM.NS', 'ACC.NS', 'DALBHARAT.NS',
               'JKCEMENT.NS', 'RAMCOCEM.NS', 'BIRLACORPN.NS'],
    'OILGAS': ['RELIANCE.NS', 'ONGC.NS', 'BPCL.NS', 'IOC.NS', 'HINDPETRO.NS', 'GAIL.NS',
               'PETRONET.NS', 'OIL.NS', 'MGL.NS', 'IGL.NS'],
    'POWER': ['NTPC.NS', 'POWERGRID.NS', 'TATAPOWER.NS', 'ADANIPOWER.NS', 'JSWENERGY.NS',
              'TORNTPOWER.NS', 'NHPC.NS', 'SJVN.NS', 'CESC.NS'],
    'CAPGOODS': ['LT.NS', 'SIEMENS.NS', 'ABB.NS', 'CUMMINSIND.NS', 'THERMAX.NS', 'BHEL.NS', 'BEL.NS',
                 'HAL.NS', 'KEC.NS', 'NBCC.NS', 'GRINDWELL.NS', 'AIAENG.NS', 'TIMKEN.NS', 'BEML.NS'],
    'CHEM': ['PIDILITIND.NS', 'SRF.NS', 'DEEPAKNTR.NS', 'AARTIIND.NS', 'ATUL.NS', 'NAVINFLUOR.NS',
             'VINATIORGA.NS', 'TATACHEM.NS', 'GNFC.NS', 'COROMANDEL.NS', 'CHAMBLFERT.NS', 'UPL.NS',
             'PIIND.NS'],
    'REALTY': ['DLF.NS', 'GODREJPROP.NS', 'OBEROIRLTY.NS', 'PRESTIGE.NS', 'PHOENIXLTD.NS',
               'BRIGADE.NS', 'SOBHA.NS'],
    'CONSDUR': ['TITAN.NS', 'HAVELLS.NS', 'VOLTAS.NS', 'CROMPTON.NS', 'DIXON.NS', 'WHIRLPOOL.NS',
                'BLUESTARCO.NS', 'AMBER.NS', 'BATAINDIA.NS', 'KAJARIACER.NS', 'CERA.NS'],
    'TELMEDIA': ['BHARTIARTL.NS', 'IDEA.NS', 'INDUSTOWER.NS', 'TATACOMM.NS', 'PVRINOX.NS', 'SUNTV.NS'],
    'HEALTHSVC': ['APOLLOHOSP.NS', 'FORTIS.NS', 'MAXHEALTH.NS', 'LALPATHLAB.NS', 'METROPOLIS.NS',
                  'NH.NS'],
}
UNIVERSE = sorted({t for v in SECTORS.values() for t in v})
SECTOR_OF = {t: s for s, v in SECTORS.items() for t in v}

NIFTY_50 = {
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'SBIN.NS', 'AXISBANK.NS', 'LT.NS', 'ITC.NS',
    'HINDUNILVR.NS', 'MARUTI.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS', 'CIPLA.NS', 'DRREDDY.NS', 'WIPRO.NS',
    'TECHM.NS', 'HCLTECH.NS', 'BAJFINANCE.NS', 'ASIANPAINT.NS', 'ULTRACEMCO.NS', 'GRASIM.NS',
    'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'ADANIPORTS.NS', 'TITAN.NS', 'NESTLEIND.NS', 'BRITANNIA.NS',
    'DIVISLAB.NS', 'EICHERMOT.NS', 'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'BPCL.NS',
    'HEROMOTOCO.NS', 'HINDALCO.NS', 'INDUSINDBK.NS', 'KOTAKBANK.NS', 'M&M.NS', 'SBILIFE.NS',
    'SHRIRAMFIN.NS', 'TRENT.NS', 'APOLLOHOSP.NS', 'COALINDIA.NS', 'ICICIBANK.NS', 'SUNPHARMA.NS',
    'TATAMOTORS.NS', 'LTIM.NS', 'ADANIENT.NS', 'TATACONSUM.NS',
}

HORIZON = 8
MIN_TURNOVER = 25e7
LOOKBACK = 5          # leader/follower measurement window (one trading week)
N_LEADERS = 3         # per sector, by trailing 60d median turnover
TOP_DECILE = 0.90     # cross-sectional GAP cut
SECTOR_TERCILE = 2 / 3
CTRL_RATE = 0.08


# ---------------------------------------------------------------- feature build
def build_long(panel):
    """One tidy long frame: row index into each stock's frame + everything the signal needs."""
    parts = []
    for t, df in panel.items():
        d = df.sort_values('date').reset_index(drop=True).copy()
        d['r5'] = np.log(d['close'] / d['close'].shift(LOOKBACK)) * 100
        d['liq'] = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False)
        d['row'] = np.arange(len(d))
        d['ticker'] = t
        d['sector'] = SECTOR_OF[t]
        parts.append(d[['row', 'ticker', 'sector', 'date', 'r5', 'turnover_60d', 'liq']])
        panel[t] = d
    return panel, pd.concat(parts, ignore_index=True)


def build_signal(long):
    """Point-in-time leader basket per sector-day, GAP, cross-sectional decile.
    Everything uses only same-day-or-earlier information."""
    L = long.dropna(subset=['r5', 'turnover_60d']).copy()
    L = L[L['liq']].copy()

    # leader = top-N turnover_60d within sector on that day (trailing median -> known at close)
    L['turn_rank'] = L.groupby(['date', 'sector'])['turnover_60d'].rank(ascending=False, method='first')
    L['is_leader'] = L['turn_rank'] <= N_LEADERS

    lead = (L[L['is_leader']].groupby(['date', 'sector'])
            .agg(L5=('r5', 'mean'), n_lead=('r5', 'size')).reset_index())
    lead = lead[lead['n_lead'] == N_LEADERS]                      # full basket only
    lead['sec_rank'] = lead.groupby('date')['L5'].rank(pct=True)  # which sectors lead today

    L = L.merge(lead[['date', 'sector', 'L5', 'sec_rank']], on=['date', 'sector'], how='inner')
    L['gap'] = L['L5'] - L['r5']

    fol = L[~L['is_leader']].copy().reset_index(drop=True)
    fol['gap_pct'] = fol.groupby('date')['gap'].rank(pct=True)
    fol['r5_q'] = fol.groupby('date')['r5'].rank(pct=True).mul(5).clip(0, 4.999).astype(int)
    fol['hot'] = (fol['L5'] > 0) & (fol['sec_rank'] >= SECTOR_TERCILE)
    return fol


def signal_rows(fol, gap_cut=TOP_DECILE, tercile=SECTOR_TERCILE):
    hot = (fol['L5'] > 0) & (fol['sec_rank'] >= tercile)
    return fol[hot & (fol['gap_pct'] >= gap_cut)]


# ---------------------------------------------------------------- trade helpers
def trades_from_rows(rows, panel, horizon=HORIZON, overlap=False):
    out = []
    for t, g in rows.groupby('ticker'):
        d = panel[t]
        m = np.zeros(len(d), dtype=bool)
        m[g['row'].values] = True
        out += simulate_trades(d, m, horizon_days=horizon, charge_costs=True, allow_overlap=overlap)
    return out


def random_ctrl_factory(dfs, horizon=HORIZON):
    def f(seed):
        r = np.random.default_rng(1000 + seed)
        tr = []
        for d in dfs:
            m = (r.random(len(d)) < CTRL_RATE) & d['liq'].values
            tr += simulate_trades(d, m, horizon_days=horizon, charge_costs=True)
        return tr
    return f


def matched_ctrl_factory(sig, cand_pool, keys, panel, horizon=HORIZON, base=3000):
    """Control that reproduces the signal's (date x keys) cell counts from a non-signal pool."""
    want = sig.groupby(['date'] + keys).size().rename('k').reset_index()
    cand = cand_pool.merge(want, on=['date'] + keys)

    def f(seed):
        picks = (cand.sample(frac=1.0, random_state=base + seed)
                 .groupby(['date'] + keys, group_keys=False)
                 .apply(lambda g: g.head(int(g['k'].iloc[0]))))
        return trades_from_rows(picks, panel, horizon, overlap=True)
    return f


def show_stable(label, trades, factory, seeds=20):
    st = stable_day_clustered_z(trades, factory, n_seeds=seeds)
    if st:
        print(f"  {label}: n={len(trades):4d}  STABLE mean_z {st['mean_z']:+.2f} "
              f"(min {st['min_z']:+.2f}, max {st['max_z']:+.2f})  pass {st['pass_rate']*100:.0f}%")
    return st


# ---------------------------------------------------------------- run
def run():
    panel = get_panel(UNIVERSE, period="5y", cache_name="sector_leadlag_5y")
    panel = {t: d for t, d in panel.items() if len(d) >= 400}
    print(f"panel: {len(panel)}/{len(UNIVERSE)} stocks")
    panel, long = build_long(panel)
    fol = build_signal(long)
    sig = signal_rows(fol)
    print(f"followers scored: {len(fol):,} stock-days | signal rows: {len(sig):,} "
          f"over {sig['date'].nunique()} days\n")

    dfs = list(panel.values())
    strat = trades_from_rows(sig, panel)
    rc = random_ctrl_factory(dfs)
    print(report(f"Sector leader lead-lag catch-up (POOLED, {HORIZON}d, costs)", strat, rc(42),
                 holding_days=HORIZON))
    print()
    show_stable("POOLED vs random", strat, rc)

    # ---- 2. SUBGROUP (methodology sec 8)
    print("\n=== SUBGROUP (sec 8): the tradeable half must clear on its own ===")
    for name, keep in (("Mid/Small", lambda t: t not in NIFTY_50),
                       ("Large(N50)", lambda t: t in NIFTY_50)):
        sub_t = [t for t in panel if keep(t)]
        s = trades_from_rows(sig[sig['ticker'].isin(sub_t)], panel)
        f = random_ctrl_factory([panel[t] for t in sub_t])
        ev = edge_vs_control([x['net_pct'] for x in s], [x['net_pct'] for x in f(42)])
        if ev:
            print(f"  {name:11s} net {ev['strategy_avg']:+.3f}%  edge {ev['edge']:+.3f}%  "
                  f"win {ev['win_rate']:.1f}%")
        show_stable(f"  {name}", s, f)

    # ---- 3. KILL TEST 4: reversal-matched control (is this just short-term reversal?)
    print("\n=== KILL TEST: REVERSAL-MATCHED control (same own-r5 quintile, no sector condition) ===")
    rev_pool = fol[~fol.index.isin(sig.index)][['row', 'ticker', 'date', 'r5_q']]
    rev = matched_ctrl_factory(sig, rev_pool, ['r5_q'], panel, base=3000)
    ev = edge_vs_control([x['net_pct'] for x in strat], [x['net_pct'] for x in rev(0)])
    if ev:
        print(f"  matched n={ev['n_control']}  control {ev['control_avg']:+.3f}%  "
              f"strategy {ev['strategy_avg']:+.3f}%  edge {ev['edge']:+.3f}%")
    show_stable("vs reversal-matched", strat, rev)

    # ---- 4. KILL TEST 5: sector-day-matched control (is this just hot-sector beta?)
    print("\n=== KILL TEST: SECTOR-DAY-MATCHED control (same sector, same day, not the laggard) ===")
    sec_pool = fol[~fol.index.isin(sig.index)][['row', 'ticker', 'date', 'sector']]
    sec = matched_ctrl_factory(sig, sec_pool, ['sector'], panel, base=5000)
    ev = edge_vs_control([x['net_pct'] for x in strat], [x['net_pct'] for x in sec(0)])
    if ev:
        print(f"  matched n={ev['n_control']}  control {ev['control_avg']:+.3f}%  "
              f"strategy {ev['strategy_avg']:+.3f}%  edge {ev['edge']:+.3f}%")
    show_stable("vs sector-day-matched", strat, sec)

    # ---- 5. GAP DECILE GRADIENT (mechanism or lone spike?)
    print("\n=== GAP DECILE GRADIENT (within hot sectors) ===")
    ctrl42 = rc(42)
    hot = fol[fol['hot']]
    for lo in np.arange(0.0, 1.0, 0.1):
        rows = hot[(hot['gap_pct'] >= lo) & (hot['gap_pct'] < lo + 0.1 + 1e-9)]
        s = trades_from_rows(rows, panel)
        ev = edge_vs_control([x['net_pct'] for x in s], [x['net_pct'] for x in ctrl42])
        dc = day_clustered_edge(s, ctrl42)
        if ev and dc:
            print(f"  D{int(round(lo*10))+1:2d} [{lo:.1f}-{lo+0.1:.1f}) n={len(s):5d}  "
                  f"net {ev['strategy_avg']:+.3f}%  edge {ev['edge']:+.3f}%  z_paired {dc['z_paired']:+.2f}")

    # ---- 6. WALK-FORWARD
    print("\n=== WALK-FORWARD (pooled, by date window) ===")
    dates = np.array(sorted(long['date'].unique()))
    for k, (_, (te0, te1)) in enumerate(walk_forward_splits(len(dates), n_splits=4,
                                                            horizon_days=HORIZON), 1):
        lo, hi = dates[te0], dates[te1 - 1]
        rows = sig[(sig['date'] >= lo) & (sig['date'] <= hi)]
        fs = trades_from_rows(rows, panel)
        r = np.random.default_rng(500 + k)
        fc = []
        for d in dfs:
            win = ((d['date'] >= lo) & (d['date'] <= hi)).values
            m = (r.random(len(d)) < CTRL_RATE) & d['liq'].values & win
            fc += simulate_trades(d, m, horizon_days=HORIZON, charge_costs=True)
        ev = edge_vs_control([x['net_pct'] for x in fs], [x['net_pct'] for x in fc])
        dc = day_clustered_edge(fs, fc)
        if ev and dc:
            print(f"  Fold {k} {str(lo)[:10]}..{str(hi)[:10]} n={len(fs):4d} "
                  f"{dc['n_paired_days']:3d} paired days | net {ev['strategy_avg']:+.2f}% "
                  f"edge {ev['edge']:+.2f}% | z_paired {dc['z_paired']:+.2f} "
                  f"day_edge {dc['day_edge']:+.2f}%")

    # ---- 7. SENSITIVITY (+-1 step on both pre-committed cuts)
    print("\n=== SENSITIVITY (+-1 step: plateau or spike?) ===")
    for gc in (0.85, 0.90, 0.95):
        for tc in (0.50, 2 / 3, 0.80):
            s = trades_from_rows(signal_rows(fol, gc, tc), panel)
            st = stable_day_clustered_z(s, rc, n_seeds=10)
            if st:
                print(f"  gap>={gc:.2f} sector>={tc:.2f}: n={len(s):4d} mean_z {st['mean_z']:+.2f}")

    # ---- 8. NEXT-OPEN FILL (execution fragility)
    print("\n=== NEXT-OPEN FILL ===")
    nxt = {}
    for t, d in panel.items():
        d2 = d.copy()
        d2['close'] = d['open'].shift(-1)
        nxt[t] = d2.iloc[:-1].reset_index(drop=True)
    keep = sig[[r < len(nxt[t]) for t, r in zip(sig['ticker'], sig['row'])]]
    s_open = trades_from_rows(keep, nxt)
    show_stable("next-open", s_open, random_ctrl_factory(list(nxt.values())))

    # ---- 9. HORIZON BAND 6-10d
    print("\n=== HOLDING-PERIOD BAND (6-10d) ===")
    for h in (6, 7, 8, 9, 10):
        s = trades_from_rows(sig, panel, horizon=h)
        show_stable(f"hold {h:2d}d", s, random_ctrl_factory(dfs, h), seeds=10)


if __name__ == "__main__":
    run()
