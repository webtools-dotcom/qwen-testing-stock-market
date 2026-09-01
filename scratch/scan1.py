import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from xsec import build, deciles
from hunt import IS_END

df = build()
df = df[df["date"] <= IS_END]
print(f"rows {len(df)}, dates {df['date'].nunique()}")
ms = df[df["mid_small"]]

FEATS = ["ret1","ret3","ret5","ret10","ret20","ret60","resid5","resid10","rsi","atr_pct",
         "drop_atr5","dev_avwap","vol_ratio3","vol_ratio5","vol_ratio1","obv_ch20","rng_pos",
         "dist_high10","atr_pct_rank","semi_ratio","amihud_z","bb_bw_rank","bb_pos","dn_streak",
         "turnover_z","absorb","up_days20","path_smooth","momentum_60d","change_252d",
         "distance_from_high_50","beta","gap"]
for f in FEATS:
    print(deciles(df, f, label="ALL"))
    print(deciles(ms, f, label="mid/small"))
