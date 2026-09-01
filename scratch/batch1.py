"""Batch 1 candidates. All screened IN-SAMPLE only (<= 2025-06-30)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from hunt import load, enrich, add_cs_ranks, screen, fmt, NIFTY_50

panel = enrich(load("sector_leadlag_5y"))
panel = add_cs_ranks(panel, ["resid5", "ret5"])
print(f"panel: {len(panel)} names")

up = lambda d: (d["close"] > d["sma_50"]) & (d["sma_50"] > d["sma_200"])

CANDS = {
 # 1 volume dry-up pullback (no-supply) in uptrend
 "1 vol_dryup_pullback": lambda d: up(d) & (d["vol_ratio3"] < 0.75) & (d["ret5"] < 0) &
                                   (d["close"] < d["high10"] * 0.97) & (d["rsi"] < 50),
 # 2 OBV accumulation divergence at 20d price low
 "2 obv_divergence_low": lambda d: (d["close"] <= d["low20"] * 1.01) & (d["obv_ch20"] > 0) &
                                   (d["close"] > d["sma_200"]),
 # 3 spring / failed breakdown (undercut 20d low, close strong)
 "3 spring_failed_breakdown": lambda d: (d["low"] < d["low20"].shift(1)) & (d["rng_pos"] > 0.6) &
                                        (d["close"] > d["sma_200"]),
 # 4 Amihud illiquidity spike + weakness -> reversal
 "4 amihud_spike_rev": lambda d: (d["amihud_z"] > 1.5) & (d["ret5"] < -3) & (d["close"] > d["sma_200"]),
 # 5 idiosyncratic (beta-adjusted) 5d reversal, bottom cross-sec decile
 "5 resid5_reversal_d1": lambda d: (d["resid5_csr"] < 0.10) & (d["close"] > d["sma_200"]),
 # 6 quiet uptrend small dip (low ATR percentile)
 "6 quiet_uptrend_dip": lambda d: up(d) & (d["atr_pct_rank"] < 0.30) & (d["ret3"] < 0) & (d["rsi"] < 55),
 # 7 low downside/upside semivol ratio + pullback from 10d high
 "7 semivol_healthy_pullback": lambda d: up(d) & (d["semi_ratio"] < 0.85) & (d["dist_high10"] < -0.05),
 # 8 gap-down into support with strong close (intraday absorption, next-day known at close)
 "8 gapdown_absorb": lambda d: (d["gap"] < -1.5) & (d["rng_pos"] > 0.7) & (d["close"] > d["sma_50"]),
 # 9 volume expansion off a 20d low with close in top third (demand appearing)
 "9 demand_thrust_off_low": lambda d: (d["close"].shift(1) <= d["low20"].shift(1) * 1.02) &
                                       (d["vol_ratio1"] > 1.5) & (d["ret1"] > 1) & (d["close"] > d["sma_200"]),
 # 10 residual 10d reversal, uptrend, high liquidity
 "10 resid10_reversal": lambda d: (d["resid10"] < -8) & (d["close"] > d["sma_200"]),
}

mid_small = lambda t: t not in NIFTY_50
for name, fn in CANDS.items():
    r = screen(panel, fn)
    print(fmt(name, r))
    r2 = screen(panel, fn, subset=mid_small)
    print(fmt("     ^ mid/small", r2))
