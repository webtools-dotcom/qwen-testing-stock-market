"""Is residual (beta-adjusted) 10d reversal actually different from plain 10d RoC (strategy 002)
and from RSI<30 (already ADOPTED)? Discriminator battery, mid/small, in-sample only."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from hunt import load, enrich, add_cs_ranks, screen, fmt, NIFTY_50

panel = add_cs_ranks(enrich(load("sector_leadlag_5y")), ["resid5", "ret5"])
ms = lambda t: t not in NIFTY_50

T = {
 "A raw ret10<-8 (=strat 002)":      lambda d: (d["ret10"] < -8) & (d["close"] > d["sma_200"]),
 "A2 raw ret10<-8 no trend filter":  lambda d: (d["ret10"] < -8),
 "B resid10<-8 +sma200":             lambda d: (d["resid10"] < -8) & (d["close"] > d["sma_200"]),
 "B2 resid10<-8 no trend filter":    lambda d: (d["resid10"] < -8),
 "C resid<-8 & raw>-8 (pure idio)":  lambda d: (d["resid10"] < -8) & (d["ret10"] > -8) & (d["close"] > d["sma_200"]),
 "D raw<-8 & resid>-8 (mkt-driven)": lambda d: (d["ret10"] < -8) & (d["resid10"] > -8) & (d["close"] > d["sma_200"]),
 "E rsi<30 (ADOPTED baseline)":      lambda d: (d["rsi"] < 30),
 "F resid10<-8 & rsi>=30":           lambda d: (d["resid10"] < -8) & (d["rsi"] >= 30) & (d["close"] > d["sma_200"]),
 "G resid10<-8 & rsi<30":            lambda d: (d["resid10"] < -8) & (d["rsi"] < 30) & (d["close"] > d["sma_200"]),
}
for name, fn in T.items():
    print(fmt(name, screen(panel, fn, subset=ms)))
