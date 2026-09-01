import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from hunt import load, enrich, add_cs_ranks, screen, fmt, NIFTY_50

panel = enrich(load("sector_leadlag_5y"))
ms = lambda t: t not in NIFTY_50
up200 = lambda d: d["close"] > d["sma_200"]

T = {
 # ATR-scaled drop: gradient test (pre-committed as a monotonic ladder, not a tuned peak)
 "11a drop_atr5 < -2":   lambda d: (d["drop_atr5"] < -2) & up200(d),
 "11b drop_atr5 < -3":   lambda d: (d["drop_atr5"] < -3) & up200(d),
 "11c drop_atr5 < -4":   lambda d: (d["drop_atr5"] < -4) & up200(d),
 "11d drop_atr5 < -5":   lambda d: (d["drop_atr5"] < -5) & up200(d),
 # anchored-VWAP magnetism
 "12a dev_avwap < -5%":  lambda d: (d["dev_avwap"] < -5) & up200(d),
 "12b dev_avwap < -8%":  lambda d: (d["dev_avwap"] < -8) & up200(d),
 # absorption: heavy turnover, tiny price move
 "13 absorption_flat":   lambda d: (d["turnover_z"] > 2) & (d["ret1"].abs() < 1) & up200(d),
 # down-streak exhaustion
 "14a dn_streak==4":     lambda d: (d["dn_streak"] == 4) & up200(d),
 "14b dn_streak>=5":     lambda d: (d["dn_streak"] >= 5) & up200(d),
 # squeeze at lower band in uptrend
 "15 bbsqueeze_lowband": lambda d: (d["bb_bw_rank"] < 0.25) & (d["bb_pos"] < 0.25) & (d["close"] > d["sma_50"]),
 # weekly-oversold + daily turn-up
 "16 wkly_oversold_turn":lambda d: (d["rsi_w"] < 35) & (d["ret1"] > 0) & up200(d),
 # quiet base near 20d high (low vol before breakout)
 "17 quiet_base_nearhigh":lambda d: (d["close"] > d["high20"] * 0.98) & (d["bb_bw_rank"] < 0.25) & up200(d),
 # smooth-path momentum (trend quality) held 8d
 "18 smooth_momentum":   lambda d: (d["path_smooth"] > 1.0) & (d["ret20"] > 5) & up200(d),
 # gap-down filled same day, in uptrend
 "19 gapdown_filled":    lambda d: (d["gap_fill"] == 1) & (d["close"] > d["sma_50"]),
}
for name, fn in T.items():
    print(fmt(name, screen(panel, fn, subset=ms)))
