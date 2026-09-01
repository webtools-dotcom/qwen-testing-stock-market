"""Scaffold the next strategy. Auto-numbers, copies the template, writes a runnable stub.

    python new_strategy.py "deep oversold with volume spike"

Creates strategies/NNN_deep_oversold_with_volume_spike.md (from STRATEGY_TEMPLATE.md) and a
matching .py stub wired to the engine, so the AI fills in rules instead of boilerplate.
"""

import sys
import os
import re
import glob

BASE = os.path.dirname(os.path.abspath(__file__))
STRAT_DIR = os.path.join(BASE, "strategies")


def next_number():
    nums = [int(m.group(1)) for f in glob.glob(os.path.join(STRAT_DIR, "*"))
            if (m := re.match(r"(\d{3})[_-]", os.path.basename(f)))]
    return max(nums, default=0) + 1


PY_STUB = '''"""Strategy @@NNN@@ — @@TITLE@@.

Fill in UNIVERSE, the entry signal, and exits. Model on strategies/001_rsi_mean_reversion.py.
Run:  python strategies/@@NNN@@_@@SLUG@@.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from data_loader import get_panel
from backtest_engine import simulate_trades, day_clustered_edge, report

UNIVERSE = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]   # TODO: real universe (Nifty 500 / Mid-Small list)
HORIZON = 6
MIN_TURNOVER = 25e7


def signal_mask(d):
    """TODO: return a boolean numpy array — True where the strategy ENTERS.
    Only use columns known at that bar (no look-ahead). Event signals enter next open."""
    raise NotImplementedError("define the entry signal")


def run():
    panel = get_panel(UNIVERSE, period="5y", cache_name="@@SLUG@@_5y")
    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    for ticker, df in panel.items():
        d = df.dropna(subset=["rsi", "atr", "close"]).reset_index(drop=True)
        if len(d) < 300:
            continue
        liq = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d) & liq
        rnd = (rng.random(len(d)) < 0.10) & liq         # matched random-entry control
        strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl  += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(report("@@TITLE@@", strat, ctrl))
    dc = day_clustered_edge(strat, ctrl)
    if dc:
        verdict = "ADOPT-eligible" if dc["z_paired"] >= 2.0 and dc["day_edge"] > 0 else "REJECT"
        print(f"\\nheadline z_paired {dc['z_paired']:.2f}, day_edge {dc['day_edge']:+.3f}%  ->  {verdict}")
        print("Then walk-forward it, and log the verdict: python ledger.py reject/adopt \\"...\\" \\"...\\"")


if __name__ == "__main__":
    run()
'''


def main():
    if len(sys.argv) < 2:
        print('usage: python new_strategy.py "<strategy name>"')
        return
    title = " ".join(sys.argv[1:]).strip()
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    nnn = f"{next_number():03d}"
    md_path = os.path.join(STRAT_DIR, f"{nnn}_{slug}.md")
    py_path = os.path.join(STRAT_DIR, f"{nnn}_{slug}.py")
    if os.path.exists(md_path) or os.path.exists(py_path):
        print(f"already exists: {nnn}_{slug} — pick a different name")
        return

    with open(os.path.join(BASE, "STRATEGY_TEMPLATE.md"), encoding="utf-8") as fh:
        template = fh.read()
    template = template.replace("# Strategy NNN — <short name>", f"# Strategy {nnn} — {title}", 1)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(template)
    stub = PY_STUB.replace("@@NNN@@", nnn).replace("@@SLUG@@", slug).replace("@@TITLE@@", title)
    with open(py_path, "w", encoding="utf-8") as fh:
        fh.write(stub)

    print(f"created:\n  strategies/{nnn}_{slug}.md   (fill in hypothesis, rules, kill criteria)")
    print(f"  strategies/{nnn}_{slug}.py   (define signal_mask, set UNIVERSE, then run it)")


if __name__ == "__main__":
    main()
