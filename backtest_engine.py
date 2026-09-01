"""Honest backtest engine — the ground truth of this project.

Ported verbatim from the sister project (NSE trading-assistant), where every function here
caught a "this clearly works!" result that was actually noise. Do NOT rewrite these. If Gemini
proposes a "simpler" or "better" statistic, it is almost certainly reintroducing one of the
biases these functions exist to remove. Call this engine; don't reinvent it.

What it fixes vs naive backtesting:

1. NON-OVERLAPPING TRADES. A signal that stays true for days (RSI<30 for a week) becomes one
   episode, not 5 near-identical trades sharing forward returns. Overlap inflated this
   project's z-scores by ~1.7x. (Lopez de Prado, Advances in Financial ML, ch.4.)
2. TRANSACTION COSTS. Charged, not assumed away. On a 4-6 day Indian mid/small-cap hold the
   cost stack (~0.5%) is the same order of magnitude as the edge.
3. HONEST FILLS. Gaps blow through stops; fill at min(open, stop), never at the stop price.
4. DAY-CLUSTERING. Trades on the same day across different stocks share one market factor.
   1,125 trades over 112 days carry ~112 observations of information, not 1,125. THE headline
   number is z_paired, not the trade-level z.
5. WALK-FORWARD with purge + embargo so a 6-day label cannot straddle train/test and leak.
6. SEARCH-ADJUSTED SIGNIFICANCE. If you scanned K thresholds and reported the best, that is a
   max-of-K statistic, not a single test. Deflated Sharpe + block-bootstrap correct for it.

Run `python backtest_engine.py` — it self-checks against synthetic data with a KNOWN edge and
KNOWN noise, and asserts it recovers the real edge and rejects the noise.
"""

import numpy as np
import pandas as pd
from scipy import stats

# ------------------------------------------------------------------
# Cost model — Indian round-trip, liquidity-scaled. Edit here if your
# strategy trades a different instrument/holding period.
# ------------------------------------------------------------------
ROUND_TRIP_COST_PCT = 0.40      # STT + brokerage + fees + GST + stamp + baseline slippage
IMPACT_COST_TIERS = [           # extra impact by 60-day median turnover (INR)
    (25e7, 0.10),               # >= Rs 25 cr/day: negligible
    (10e7, 0.35),               # Rs 10-25 cr: noticeable
    (0,    0.90),               # < Rs 10 cr: severe — gross edge here rarely covers it
]
MIN_TURNOVER_INR = 25e7         # validated liquidity floor in the sister project


def round_trip_cost_pct(turnover_60d):
    """Total round-trip cost % including liquidity-scaled impact. Unknown liquidity = worst."""
    if turnover_60d is None or turnover_60d != turnover_60d:
        return ROUND_TRIP_COST_PCT + IMPACT_COST_TIERS[-1][1]
    for floor, impact in IMPACT_COST_TIERS:
        if turnover_60d >= floor:
            return ROUND_TRIP_COST_PCT + impact
    return ROUND_TRIP_COST_PCT + IMPACT_COST_TIERS[-1][1]


# ============================================================
# Trade simulation
# ============================================================

def simulate_trades(stock_df, entry_mask, horizon_days=6, stop_atr_mult=2.0,
                    target_atr_mult=2.0, charge_costs=True, allow_overlap=False,
                    exit_rsi=None, stop_pct=None, target_pct=None):
    """Simulate trades for one stock.

    entry_mask: boolean array aligned to stock_df rows. Needs columns: open, high, low, close,
    atr. Optional: rsi (for exit_rsi), turnover_60d (for cost tiering).

    allow_overlap=False (default, honest) takes at most one trade per signal episode — no new
    entry until the previous trade exits. exit_rsi (None=off): also exit when RSI recovers to
    that level, filled on the NEXT open (exiting at the same close is look-ahead).
    """
    df = stock_df.reset_index(drop=True)
    mask = np.asarray(entry_mask)
    n = len(df)
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    open_ = df['open'].values if 'open' in df.columns else close
    atr = df['atr'].values
    rsi = df['rsi'].values if 'rsi' in df.columns else None
    turnover = df['turnover_60d'].values if 'turnover_60d' in df.columns else None

    trades = []
    last_exit = -1
    for i in np.where(mask)[0]:
        if i >= n - horizon_days - 1:
            break
        if not allow_overlap and i <= last_exit:
            continue
        if not np.isfinite(close[i]) or not np.isfinite(atr[i]) or atr[i] <= 0 or close[i] <= 0:
            continue

        entry = close[i]
        stop = entry * (1 - stop_pct) if stop_pct is not None else entry - stop_atr_mult * atr[i]
        target = entry * (1 + target_pct) if target_pct is not None else entry + target_atr_mult * atr[i]

        exit_price, reason, held = None, None, horizon_days
        for j in range(1, horizon_days + 1):
            k = i + j
            if open_[k] <= stop:                      # gap through stop → filled at open
                exit_price, reason, held = open_[k], 'stop_gap', j
                break
            if low[k] <= stop:
                exit_price, reason, held = stop, 'stop', j
                break
            if high[k] >= target:                     # conservative: stop assumed first if both touched
                exit_price, reason, held = target, 'target', j
                break
            if exit_rsi is not None and rsi is not None and np.isfinite(rsi[k]) and rsi[k] >= exit_rsi:
                nxt = i + j + 1
                if nxt < n:
                    exit_price, reason, held = open_[nxt], 'rsi_recover', j + 1
                else:
                    exit_price, reason, held = close[k], 'rsi_recover', j
                break
        if exit_price is None:
            exit_price, reason, held = close[i + horizon_days], 'time', horizon_days

        gross = (exit_price - entry) / entry * 100
        cost = round_trip_cost_pct(turnover[i] if turnover is not None else None) if charge_costs else 0.0
        trades.append({
            'entry_idx': int(i), 'exit_idx': int(i + held),
            'entry_date': df['date'].iat[i] if 'date' in df.columns else i,
            'gross_pct': gross, 'net_pct': gross - cost, 'cost_pct': cost,
            'reason': reason, 'held': held,
        })
        last_exit = i + held

    return trades


def average_uniqueness(trades, n_bars):
    """Fraction of each trade's lifespan not shared with others. 1.0 = independent.
    sqrt(1/uniqueness) ≈ the factor by which naive z-scores are inflated by overlap."""
    if not trades:
        return 1.0
    conc = np.zeros(n_bars + 1)
    for t in trades:
        conc[t['entry_idx']:t['exit_idx'] + 1] += 1
    vals = []
    for t in trades:
        span = conc[t['entry_idx']:t['exit_idx'] + 1]
        vals.append(np.mean(1.0 / np.maximum(span, 1)))
    return float(np.mean(vals)) if vals else 1.0


# ============================================================
# Statistics
# ============================================================

def edge_vs_control(strategy_returns, control_returns):
    """Welch two-sample test vs a random-entry control. Assumes independence — only true if
    trades are non-overlapping AND not day-clustered. For anything that selects days or fires
    broadly, this OVERSTATES significance; use day_clustered_edge as the headline instead."""
    s = np.asarray([r for r in strategy_returns if np.isfinite(r)])
    c = np.asarray([r for r in control_returns if np.isfinite(r)])
    if len(s) < 2 or len(c) < 2:
        return None
    se = np.sqrt(s.var(ddof=1) / len(s) + c.var(ddof=1) / len(c))
    edge = s.mean() - c.mean()
    z = edge / se if se > 0 else 0.0
    return {
        'n_strategy': len(s), 'n_control': len(c),
        'strategy_avg': float(s.mean()), 'control_avg': float(c.mean()),
        'edge': float(edge), 'z': float(z),
        'p_value': float(2 * (1 - stats.norm.cdf(abs(z)))),
        'win_rate': float((s > 0).mean() * 100),
    }


def day_clustered_edge(trades, control_trades):
    """THE headline test. Edge vs control clustered by ENTRY DATE.

    Trades on the same day across different stocks share one market factor, so N trades over D
    days carry ~D observations, not N. z_paired pairs each day's strategy mean against the SAME
    day's control mean — nets out the common market move, isolating stock-selection skill.

    Both lists must carry 'entry_date' and 'net_pct'. Report z_paired, not z_day.
    """
    if not trades or not control_trades:
        return None
    s = pd.Series([t['net_pct'] for t in trades],
                  index=[t['entry_date'] for t in trades]).groupby(level=0).mean()
    c = pd.Series([t['net_pct'] for t in control_trades],
                  index=[t['entry_date'] for t in control_trades]).groupby(level=0).mean()
    if len(s) < 3 or len(c) < 3:
        return None

    se = np.sqrt(s.var(ddof=1) / len(s) + c.var(ddof=1) / len(c))
    unpaired_z = float((s.mean() - c.mean()) / se) if se > 0 else 0.0

    paired = (s - c).dropna()
    z_paired = (float(paired.mean() / (paired.std(ddof=1) / np.sqrt(len(paired))))
                if len(paired) > 2 and paired.std(ddof=1) > 0 else 0.0)

    return {
        'n_days': len(s), 'n_paired_days': len(paired),
        'day_edge': float(paired.mean()) if len(paired) else 0.0,
        'z_day': unpaired_z, 'z_paired': z_paired,
    }


def stable_day_clustered_z(strategy_trades, control_factory, n_seeds=20):
    """Robustness of z_paired to the random control draw. THE fix for the seed-luck trap.

    A single random-entry control is one noisy sample; its z_paired can land above or below the
    bar by chance. This re-runs day_clustered_edge against `control_factory(seed)` for many seeds
    and reports the distribution. `control_factory(seed)` must return a fresh control trade list
    (each carrying 'entry_date' and 'net_pct') for that seed.

    ADOPT requires the MEAN z_paired ≥ 2.0 (and ideally pass_rate near 1.0), NOT a single lucky
    draw. A candidate whose mean is 1.93 with a 50% pass rate is INCONCLUSIVE, not adopted.
    """
    zs = []
    for s in range(n_seeds):
        dc = day_clustered_edge(strategy_trades, control_factory(s))
        if dc:
            zs.append(dc['z_paired'])
    if not zs:
        return None
    zs = np.asarray(zs)
    return {
        'mean_z': float(zs.mean()), 'min_z': float(zs.min()), 'max_z': float(zs.max()),
        'pass_rate': float((zs >= 2.0).mean()), 'n_seeds': len(zs),
    }


def sharpe(returns, periods_per_year=252, holding_days=6):
    """Trade-level Sharpe annualised by trade frequency."""
    r = np.asarray([x for x in returns if np.isfinite(x)]) / 100.0
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    trades_per_year = periods_per_year / max(holding_days, 1)
    return float(r.mean() / r.std(ddof=1) * np.sqrt(trades_per_year))


def deflated_sharpe(observed_sr, all_trial_srs, n_obs, skew=0.0, kurtosis=3.0):
    """Deflated Sharpe (Bailey & Lopez de Prado 2014): given N strategies tried and the best
    picked, how likely is this Sharpe real vs the max of N noisy draws? Returns P(true SR > 0);
    want > 0.95. On pure noise the naive best-of-N declares a discovery ~100% of the time; DSR
    brings that to ~0.1%. Pass EFFECTIVE independent trials (see effective_trials)."""
    trials = np.asarray([s for s in all_trial_srs if np.isfinite(s)])
    n_trials = max(len(trials), 1)
    if n_trials < 2 or n_obs < 3:
        return None
    var_sr = trials.var(ddof=1)
    if var_sr <= 0:
        return None
    euler = 0.5772156649
    e_max = np.sqrt(var_sr) * (
        (1 - euler) * stats.norm.ppf(1 - 1.0 / n_trials)
        + euler * stats.norm.ppf(1 - 1.0 / (n_trials * np.e)))
    denom = np.sqrt(max(1e-12, 1 - skew * e_max + (kurtosis - 1) / 4.0 * e_max ** 2) / (n_obs - 1))
    return {'observed_sr': float(observed_sr), 'noise_ceiling_sr': float(e_max),
            'n_trials': int(n_trials), 'dsr': float(stats.norm.cdf((observed_sr - e_max) / denom))}


def effective_trials(trial_returns):
    """Effective independent trials from the correlation structure (participation ratio of the
    correlation eigenvalues). A threshold sweep is highly correlated; feeding the raw count to
    deflated_sharpe over-deflates and can false-reject a genuine edge."""
    mats = [np.asarray(r) for r in trial_returns if len(r) > 1]
    if len(mats) < 2:
        return len(mats)
    m = min(len(x) for x in mats)
    if m < 3:
        return len(mats)
    corr = np.nan_to_num(np.corrcoef(np.vstack([x[:m] for x in mats])), nan=0.0)
    eig = np.linalg.eigvalsh(corr)
    eig = eig[eig > 0]
    return float(eig.sum() ** 2 / (eig ** 2).sum()) if len(eig) else len(mats)


def block_bootstrap_pvalue(stock_dfs, signal_fn, thresholds, horizon_days=6,
                           n_iter=200, block=10, seed=42):
    """Search-adjusted p-value for a threshold chosen by scanning. Reporting the best of K
    thresholds is a max-of-K statistic (K=41 at alpha 0.05 → ~88% family-wise error). Bonferroni
    over-corrects because thresholds are correlated; the honest fix is empirical: block-shuffle
    (preserving autocorrelation), re-run the WHOLE sweep, count how often noise beats observed."""
    rng = np.random.default_rng(seed)

    def best_stat(dfs):
        best = -np.inf
        for th in thresholds:
            rets = []
            for df in dfs:
                rets += [t['net_pct'] for t in
                         simulate_trades(df, signal_fn(df, th), horizon_days=horizon_days)]
            if len(rets) > 30:
                best = max(best, float(np.mean(rets)))
        return best

    observed = best_stat(stock_dfs)
    worse = 0
    for _ in range(n_iter):
        shuffled = []
        for df in stock_dfs:
            n = len(df)
            starts = rng.integers(0, max(1, n - block), size=int(np.ceil(n / block)))
            idx = np.concatenate([np.arange(s, min(s + block, n)) for s in starts])[:n]
            shuffled.append(df.iloc[idx].reset_index(drop=True))
        if best_stat(shuffled) >= observed:
            worse += 1
    return {'observed_best': observed, 'p_value': (worse + 1) / (n_iter + 1), 'n_iter': n_iter}


def walk_forward_splits(n_bars, n_splits=4, horizon_days=6, embargo_pct=0.01):
    """Chronological train/test splits that respect label spans. Purge removes training bars
    whose labels overlap the test window; embargo drops bars just after it (serial correlation
    leaks forward). Without this a 6-day label straddles the boundary and leaks."""
    embargo = int(n_bars * embargo_pct)
    fold = n_bars // (n_splits + 1)
    for k in range(1, n_splits + 1):
        train_end = fold * k
        test_start, test_end = train_end, min(train_end + fold, n_bars)
        if test_end - test_start < horizon_days + 2:
            continue
        purged_train_end = max(0, train_end - horizon_days - embargo)
        if purged_train_end < horizon_days + 2:
            continue
        yield (0, purged_train_end), (test_start, test_end)


# ============================================================
# Reporting
# ============================================================

def report(name, strategy_trades, control_trades, n_bars=None, holding_days=6):
    """One consistent summary block. Prints BOTH the naive z and the day-clustered z_paired so
    the gap between them is visible — that gap is where the false positives live."""
    s_gross = [t['gross_pct'] for t in strategy_trades]
    s_net = [t['net_pct'] for t in strategy_trades]
    c_net = [t['net_pct'] for t in control_trades]
    res = edge_vs_control(s_net, c_net)
    lines = [f"--- {name} ---"]
    if res is None:
        return "\n".join(lines + ["  insufficient trades"])
    avg_cost = np.mean([t['cost_pct'] for t in strategy_trades]) if strategy_trades else 0.0
    lines += [
        f"  trades              : {res['n_strategy']}",
        f"  gross avg/trade     : {np.mean(s_gross):+.3f}%",
        f"  avg round-trip cost : {avg_cost:.3f}%",
        f"  NET avg/trade       : {res['strategy_avg']:+.3f}%",
        f"  control (random)    : {res['control_avg']:+.3f}%",
        f"  edge vs control     : {res['edge']:+.3f}%",
        f"  naive z             : {res['z']:.2f}   (p={res['p_value']:.4g})  <- OPTIMISTIC, do not headline",
        f"  win rate            : {res['win_rate']:.1f}%",
        f"  Sharpe (annualised) : {sharpe(s_net, holding_days=holding_days):.2f}",
    ]
    if all('entry_date' in t for t in strategy_trades[:1]) and control_trades:
        dc = day_clustered_edge(strategy_trades, control_trades)
        if dc:
            lines.append(f"  DAY-CLUSTERED z_pair: {dc['z_paired']:.2f}   <- THE HEADLINE "
                         f"({dc['n_paired_days']} paired days, day_edge {dc['day_edge']:+.3f}%)")
    if n_bars:
        u = average_uniqueness(strategy_trades, n_bars)
        lines.append(f"  label uniqueness    : {u:.3f} (naive-z inflation if overlapping: {np.sqrt(1/u):.2f}x)")
    return "\n".join(lines)


# ============================================================
# Self-check — run `python backtest_engine.py`
# ============================================================

def _synthetic(n=1500, edge=0.0, seed=0):
    """Series with a controllable, RSI-detectable edge (drift conditioned on a SUSTAINED
    decline, since RSI(14) only goes oversold after persistent selling)."""
    rng = np.random.default_rng(seed)
    price, steps = [100.0], []
    for _ in range(n):
        drift = edge if sum(steps[-10:]) < -4.0 else 0.0
        step = rng.normal(drift, 1.2)
        steps.append(step)
        price.append(max(1.0, price[-1] * (1 + step / 100)))
    close = pd.Series(price[1:])
    df = pd.DataFrame({
        'date': pd.date_range('2020-01-01', periods=n, freq='B'),
        'open': close, 'high': close * 1.01, 'low': close * 0.99, 'close': close,
        'volume': 1e6, 'turnover_60d': 1e9,
    })
    from data_loader import add_features
    return add_features(df).dropna(subset=['rsi', 'atr']).reset_index(drop=True)


def demo():
    rng = np.random.default_rng(7)

    # 1. A real edge must be recovered.
    edged = [_synthetic(edge=0.9, seed=s) for s in range(6)]
    strat, ctrl = [], []
    for df in edged:
        strat += simulate_trades(df, (df['rsi'] < 30).values, charge_costs=False)
        ctrl += simulate_trades(df, rng.random(len(df)) < 0.10, charge_costs=False)
    res = edge_vs_control([t['net_pct'] for t in strat], [t['net_pct'] for t in ctrl])
    assert res is not None and res['z'] > 2, f"failed to recover a real edge (z={res['z'] if res else None})"

    # 2. Pure noise must NOT produce significance. The test that matters.
    noise = [_synthetic(edge=0.0, seed=100 + s) for s in range(6)]
    nstrat, nctrl = [], []
    for df in noise:
        nstrat += simulate_trades(df, (df['rsi'] < 30).values, charge_costs=False)
        nctrl += simulate_trades(df, rng.random(len(df)) < 0.10, charge_costs=False)
    nres = edge_vs_control([t['net_pct'] for t in nstrat], [t['net_pct'] for t in nctrl])
    assert nres is None or abs(nres['z']) < 3, f"found significance in pure noise (z={nres['z']})"

    # 3. Non-overlapping yields strictly fewer trades and never overlaps.
    df = edged[0]
    m = (df['rsi'] < 30).values
    assert len(simulate_trades(df, m, allow_overlap=False)) < len(simulate_trades(df, m, allow_overlap=True))
    tr = simulate_trades(df, m, allow_overlap=False)
    assert all(a['exit_idx'] < b['entry_idx'] for a, b in zip(tr, tr[1:])), "overlap leaked through"

    # 4. Costs reduce net by exactly the charged amount.
    free = simulate_trades(df, m, charge_costs=False)
    paid = simulate_trades(df, m, charge_costs=True)
    assert all(abs((f['gross_pct'] - p['net_pct']) - p['cost_pct']) < 1e-9 for f, p in zip(free, paid))
    assert paid[0]['cost_pct'] > 0, "costs were not charged"

    # 5. Deflated Sharpe must reject the best of many pure-noise trials.
    noise_srs = [sharpe(rng.normal(0, 6, 400), holding_days=6) for _ in range(200)]
    d = deflated_sharpe(max(noise_srs), noise_srs, n_obs=400)
    assert d is not None and d['dsr'] < 0.95, f"DSR failed to reject a noise winner (dsr={d['dsr']:.3f})"

    # 6. Walk-forward splits must be purged.
    for (tr0, tr1), (te0, te1) in walk_forward_splits(1000, n_splits=4, horizon_days=6):
        assert tr1 <= te0 - 6, "purge gap missing — labels can straddle the split"

    # 7. Day-clustering must deflate a result whose trades all sit on a few dates.
    days = pd.to_datetime(['2024-01-02', '2024-02-05', '2024-03-07', '2024-04-09'])
    strat_t, ctrl_t = [], []
    for d_i, d in enumerate(days):
        daily = rng.normal([1.5, -0.9, 2.1, -0.4][d_i], 0.3, 125)
        strat_t += [{'net_pct': float(x), 'entry_date': d} for x in daily]
        ctrl_t += [{'net_pct': float(x), 'entry_date': d} for x in rng.normal(0, 0.3, 125)]
    naive = edge_vs_control([t['net_pct'] for t in strat_t], [t['net_pct'] for t in ctrl_t])
    clustered = day_clustered_edge(strat_t, ctrl_t)
    assert abs(naive['z']) > 4, "test setup: naive z should look significant here"
    assert abs(clustered['z_paired']) < abs(naive['z']) / 2, (
        f"clustering failed to deflate (naive z={naive['z']:.1f}, paired z={clustered['z_paired']:.1f})")
    assert clustered['n_days'] == 4

    # 8. Stable-control z: a borderline edge must show mean_z near the per-seed spread, and the
    #    pass_rate must reflect that ~half the seeds miss when the mean sits just under the bar.
    strat_fixed = [{'net_pct': 1.5 + rng.normal(0, 0.4), 'entry_date': d}
                   for d in days for _ in range(60)]
    def ctrl_factory(seed):
        r = np.random.default_rng(seed)
        return [{'net_pct': float(r.normal(1.4, 0.4)), 'entry_date': d}
                for d in days for _ in range(60)]
    sc = stable_day_clustered_z(strat_fixed, ctrl_factory, n_seeds=15)
    assert sc is not None and 0.0 <= sc['pass_rate'] <= 1.0 and sc['n_seeds'] == 15, "stable-control check broke"

    print("backtest_engine.py self-check passed")


if __name__ == "__main__":
    demo()
