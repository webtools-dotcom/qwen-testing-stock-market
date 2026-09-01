"""022 follow-ups: proper +/-1 threshold step (inclusive cuts, not adjacent buckets), and a
survivorship probe (names present from 2016 vs names that entered the panel later)."""
import sys, os, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategies"))
import numpy as np, pandas as pd
m = importlib.import_module("022_risk_adjusted_12_month_momentum_swing_in_mid_small_caps")

panel = m.prepare(m.load())
print("== threshold robustness: INCLUSIVE cuts (the real +/-1 step) ==", flush=True)
for tp in (0.95, 0.90, 0.85, 0.80):
    s, cf = m.run_set(m.slice_panel(panel), top_pct=tp)
    m.summarize(f"top {100*(1-tp):.0f}% inclusive", s, cf, seeds=10)

print("\n== survivorship probe ==", flush=True)
first = {t: d["date"].min() for t, d in panel.items()}
old = {t for t, dt in first.items() if dt <= pd.Timestamp("2017-01-01")}
new = set(panel) - old
print(f"   names present from 2016-17: {len(old)}; entered later: {len(new)}", flush=True)
s, cf = m.run_set(m.slice_panel(panel, names=old)); m.summarize("old names only", s, cf, seeds=10)
s, cf = m.run_set(m.slice_panel(panel, names=new)); m.summarize("later entrants only", s, cf, seeds=10)

print("\n== sanity: extreme score values (bad split/bonus adjustments would fake momentum) ==", flush=True)
flat = pd.concat([d[["date","ticker","score","change_252d","liq","mid_small"]] for d in panel.values()],
                 ignore_index=True)
e = flat[flat.liq & flat.mid_small].dropna(subset=["score"])
print(e["change_252d"].describe(percentiles=[.5,.9,.99,.999]).to_string(), flush=True)
top = e.nlargest(10, "change_252d")[["date","ticker","change_252d","score"]]
print(top.to_string(index=False), flush=True)
