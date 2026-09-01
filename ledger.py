"""One-command ledger, so verdicts always land in the same place the same way — both halves of
institutional memory, so a new session learns from what failed AND builds on what worked.

    python ledger.py reject "RSI<20 ultra-deep oversold" "z_paired 1.1, net -0.3%/trade, dies in 2025 fold"
    python ledger.py adopt  "Gap-down reversal, Mid/Small" "z_paired 3.1, net +0.9%/trade, holds all folds"

reject → dated row in REJECTED.md ; adopt → dated row in ADOPTED.md. Both refuse duplicates (same
idea text). The AI reads both files at session start, so failures are never re-tested and
survivors are the baseline new ideas must beat.
"""

import sys
import os
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
REJECTED = os.path.join(BASE, "REJECTED.md")
ADOPTED = os.path.join(BASE, "ADOPTED.md")

_LEDGERS = {
    'reject': (REJECTED, "## New rejections (this project)",
               "| _(none yet — add rows as you reject)_ | | |"),
    'adopt':  (ADOPTED, "## Adopted (this project)",
               "| _(none yet — add rows as you adopt)_ | | |"),
}


def _log(kind, idea, reason, when=None):
    """Append a row to the reject/adopt ledger. Returns True if added, False if already present."""
    path, marker, placeholder = _LEDGERS[kind]
    idea, reason = idea.strip(), reason.strip()
    when = when or date.today().isoformat()
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if f"| {idea} |" in text:
        return False                      # already logged — don't duplicate
    row = f"| {idea} | {reason} | {when} |"
    if placeholder in text:
        text = text.replace(placeholder, row)          # fill the empty placeholder first time
    elif marker in text:
        head, _, tail = text.partition(marker)
        lines = tail.splitlines(keepends=True)
        for i, ln in enumerate(lines):                 # insert after the table header separator
            if set(ln.strip()) <= set("|-: ") and "|" in ln:
                lines.insert(i + 1, row + "\n")
                break
        else:
            lines.append(row + "\n")
        text = head + marker + "".join(lines)
    else:
        text += f"\n{marker}\n\n| Idea | Result | Date |\n|---|---|---|\n{row}\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return True


def reject(idea, reason, when=None):
    return _log('reject', idea, reason, when)


def adopt(idea, reason, when=None):
    return _log('adopt', idea, reason, when)


def demo():
    """Self-check on temp copies so it never touches the real ledgers."""
    import tempfile, shutil
    global REJECTED, ADOPTED, _LEDGERS
    real = dict(_LEDGERS)
    tmp = tempfile.mkdtemp()
    for kind, (path, marker, ph) in real.items():
        tpath = os.path.join(tmp, os.path.basename(path))
        shutil.copy(path, tpath)
        _LEDGERS[kind] = (tpath, marker, ph)
    assert reject("Test idea XYZ", "z_paired 0.4"), "first reject should succeed"
    assert not reject("Test idea XYZ", "again"), "duplicate reject should be refused"
    assert adopt("Good idea ABC", "z_paired 3.2"), "first adopt should succeed"
    assert not adopt("Good idea ABC", "again"), "duplicate adopt should be refused"
    with open(_LEDGERS['reject'][0], encoding="utf-8") as fh:
        assert "Test idea XYZ" in fh.read()
    with open(_LEDGERS['adopt'][0], encoding="utf-8") as fh:
        assert "Good idea ABC" in fh.read()
    shutil.rmtree(tmp)
    _LEDGERS = real
    print("ledger.py self-check passed")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selfcheck":
        demo()
    elif len(sys.argv) >= 3 and sys.argv[1] in ('reject', 'adopt'):
        kind = sys.argv[1]
        added = _log(kind, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
        dest = os.path.basename(_LEDGERS[kind][0])
        print(f"added to {dest}" if added else "already present — not duplicated")
    else:
        print('usage: python ledger.py reject "<idea>" "<why it died: z_paired + net edge + fold>"')
        print('       python ledger.py adopt  "<idea>" "<why it survived: z_paired + net edge>"')
        print('       python ledger.py selfcheck')
