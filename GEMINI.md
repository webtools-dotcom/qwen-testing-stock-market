# GEMINI.md

Gemini: this project's agent instructions live in **`AGENTS.md`**. Read these four files, in
order, before responding to the first request in any session — they define who you are and how to
work here:

1. `AGENTS.md` — mission + hard rules (start here)
2. `START_HERE.md` — the prime directive and workflow in full
3. `METHODOLOGY.md` — the exact statistical procedure (the 7 ways a backtest lies)
4. `REJECTED.md` — strategies already killed; never re-test these

The one rule above all: **try to kill every strategy, not confirm it.** Headline the day-clustered
`z_paired` (≥ 2.0, net of costs) or reject. Never report a number you didn't compute from a real
run. On any REJECT, run `python ledger.py reject "<idea>" "<why>"` immediately.
