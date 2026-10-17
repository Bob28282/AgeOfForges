#!/usr/bin/env python3
"""A blank civ's seed (/api/builder/techtree?civ=full) holds only units the
editor can show.

The seed is the union of every civ's units from aoe2techtree, which also lists
units with no editor node.  One of them, the Longship, became unlockable by any
civ in Viking Sagas, so every new civ quietly got it (and, sharing Dock button
8, lost its Demolition Ship upgrades) with no node to untick.  Buildings are
left whole: the Fish Trap (199) has no node, yet its presence keeps its
make-avail tech (CLAUDE.md quirk 15).

    venv/bin/python tests/test_full_seed.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app                                                  # noqa: E402
from civ_appender import _editor_nodes                      # noqa: E402

failures = 0


def check(label, cond, extra=""):
    global failures
    if cond:
        print(f"  ok   {label}")
    else:
        failures += 1
        print(f"  FAIL {label}" + (f" — {extra}" if extra else ""))


seed = app.app.test_client().get("/api/builder/techtree?civ=full").get_json()
hidden = sorted(set(seed["units"]) - _editor_nodes()["units"])
check("every seeded unit is an editor node", not hidden, hidden)
# The Longship is an editor node now (Dock button 8, regional, card 51
# retired), so it belongs in this union; the wizard's regional filter keeps it
# off a blank civ (tests/test_seed_tree.js).
check("the Longship line is an editor node", {250, 533} <= _editor_nodes()["units"])
check("the Demolition line is seeded", {1104, 527, 528} <= set(seed["units"]))
check("the Fish Trap (199) is still seeded", 199 in seed["buildings"])

print()
print("FAIL" if failures else "PASS", f"({failures} failure(s))")
sys.exit(1 if failures else 0)
