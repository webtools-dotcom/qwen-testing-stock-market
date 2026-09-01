import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from master_lab import build, report, dayt

flat = build(force=True)
print(f"rows {len(flat)} names {flat.ticker.nunique()} dates {flat.date.nunique()} "
      f"{flat.date.min().date()}..{flat.date.max().date()}", flush=True)
d = flat[flat["mid_small"]].copy()
d["av_rank"] = d.groupby("date")["dev_avwap"].rank(pct=True)
print(f"mid/small rows {len(d)}, names {d.ticker.nunique()}\n", flush=True)

S = {
 "REF rsi<30 (ADOPTED baseline)": (d.rsi < 30),
 "REF ret10 < -8 (=strat 002)":   (d.ret10 < -8),
 "A dev_avwap < -6":              (d.dev_avwap < -6),
 "B dev_avwap < -8":              (d.dev_avwap < -8),
 "C dev_avwap < -12":             (d.dev_avwap < -12),
 "D dev_avwap bottom decile":     (d.av_rank < 0.10),
 "E dev_avwap bottom 5%":         (d.av_rank < 0.05),
 "F bb_pos < 0":                  (d.bb_pos < 0),
 "G drop_atr5 < -3":              (d.drop_atr5 < -3),
 "H B & vol_ratio3 < 1.0":        (d.dev_avwap < -8) & (d.vol_ratio3 < 1.0),
 "I B & vol_ratio3 > 1.5":        (d.dev_avwap < -8) & (d.vol_ratio3 > 1.5),
 "J B & close>sma_200":           (d.dev_avwap < -8) & (d.close > d.sma_200),
 "K B & close<sma_200":           (d.dev_avwap < -8) & (d.close < d.sma_200),
 "L B & rsi<30":                  (d.dev_avwap < -8) & (d.rsi < 30),
 "M B & change_252d>0":           (d.dev_avwap < -8) & (d.change_252d > 0),
 "N B & rng_pos>0.6":             (d.dev_avwap < -8) & (d.rng_pos > 0.6),
 "O 20d low & rng_pos>0.6":       (d.close <= d.low20*1.005) & (d.rng_pos > 0.6),
 "P B & atr_pct below median":    (d.dev_avwap < -8) & (d.atr_pct < d.groupby("date").atr_pct.transform("median")),
 "Q B & turnover_z<0":            (d.dev_avwap < -8) & (d.turnover_z < 0),
}
for name, m in S.items():
    print(report(name, d[m.fillna(False)]), flush=True)

print("\n=== horizon band for the leaders ===", flush=True)
for name in ("B dev_avwap < -8", "D dev_avwap bottom decile", "H B & vol_ratio3 < 1.0",
             "J B & close>sma_200", "Q B & turnover_z<0"):
    sel = d[S[name].fillna(False)]
    for h in (6, 8, 10):
        m, t, nd = dayt(sel, f"fwd{h}_dm")
        print(f"  {name:30s} h={h:2d}: edge {m:+.3f}% t={t:+5.2f} days={nd}", flush=True)
