#!/usr/bin/env python3
"""The Longship is a tree node; card 51 (Longboats) is retired into the tree.

Since Viking Sagas the Longship is a regional Dock line (Vikings, Danes, Saxons,
Varangians) on button 8, the Demolition line's button.  It is a regional group
in the editor (main.js _REGIONAL_GROUPS: Demolition standard, Longship opt-in),
and card 51 is retired: civ_schema.RETIRED_INTO_TREE makes a civ that picked it
read as a tree with the Longship line and without the Demolition line, which is
what the card built.  DAT-gated for the builds.

    venv/bin/python tests/test_longship_tree.py
"""
import contextlib
import copy
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import civ_appender as ca                                   # noqa: E402
from civ_schema import FORMAT_KEY                           # noqa: E402

failures = 0


def check(label, cond, extra=""):
    global failures
    if cond:
        print(f"  ok   {label}")
    else:
        failures += 1
        print(f"  FAIL {label}" + (f" — {extra}" if extra else ""))


LONGSHIP, DEMO = {250, 533}, {1104, 527, 528}
units, buildings, techs = json.loads(
    (ROOT / "my_civs" / "14_Barracks Enjoyers.json").read_text(encoding="utf-8"))["tree"]
BASE = {"format": FORMAT_KEY, "alias": "Ship", "architecture": 2, "language": 0,
        "tree": {"units": sorted(set(units) - LONGSHIP), "buildings": buildings, "techs": techs}}
CARD = dict(BASE, bonuses=[{"id": 51, "multiplier": 1}])
KM_CARD = {"alias": "Ship KM", "architecture": 2, "language": 0,
           "tree": [sorted(set(units) - LONGSHIP), buildings, techs],
           "bonuses": [[[51, 1]], [], [], [], []]}

print("=== card 51 reads as the tree, in both formats ===")
for name, civ in (("wizard format", CARD), ("KM format", KM_CARD)):
    tree = ca._tree_unit_ids(civ)
    check(f"{name}: card 51 is no longer a bonus", 51 not in {e[0] for e in ca.get_civ_bonuses(civ)})
    check(f"{name}: its tree holds the Longship line", LONGSHIP <= tree)
    check(f"{name}: and not the Demolition line", not DEMO & tree, sorted(DEMO & tree))
check("a civ with no tree stays treeless (card 51 can't fake one)",
      ca._tree_unit_ids({"bonuses": [{"id": 51}]}) == set())

try:
    from dat_reader import find_game_dat, load_dat
    dat_path = find_game_dat()
except Exception:                                            # noqa: BLE001
    dat_path = None
if dat_path is None:
    print("  skip  no game DAT found")
else:
    import fu_stats

    def built(civ):
        dat = load_dat(str(dat_path))
        with contextlib.redirect_stdout(io.StringIO()):
            ca.apply_civ(dat, copy.deepcopy(civ), target_slot=1)
        sim = fu_stats.Simulation(dat, 1)
        return {sim.final_unit(b) for b in sim.available_lines()}

    print("\n=== what the build makes ===")
    plain = built(dict(BASE, bonuses=[]))
    check("no card, no node: no Longship", not LONGSHIP & plain)
    check("no card, no node: the Demolition line", 528 in plain)
    old = built(CARD)
    check("an old save with card 51: Elite Longship, as the card built", 533 in old)
    check("an old save with card 51: no Demolition line, as the card built", not DEMO & old)
    ticked = built(dict(BASE, bonuses=[], tree=dict(BASE["tree"], units=BASE["tree"]["units"] + sorted(LONGSHIP))))
    check("Longship node ticked: Elite Longship", 533 in ticked)
    check("Longship node ticked: the Demolition line too (page 2 of the Dock)", 528 in ticked)

print()
print("FAIL" if failures else "PASS", f"({failures} failure(s))")
sys.exit(1 if failures else 0)
