#!/usr/bin/env python3
"""A UT that enables a non-unique unit doesn't retarget its commands onto our
unique unit.  DAT-gated.

_build_ut_effect_cmds treats a civ-gated UT that enables a unit as the
Anarchy/Marauders shape: the enabled unit is the source civ's unique unit,
and every other unit the tech touches is its elite form, so all of it is
redirected to this civ's own unique unit.  Timurid Siegecraft enables the
Flaming Camel, so its five trebuchet "+2 range" commands landed on our Elite
unique unit: Patient's melee Qurchi showed 10 range and never landed a hit,
and his trebuchets got nothing (2026-10-12).  Flemish Revolution (Flemish
Militia) had the same shape.

    venv/bin/python tests/test_ut_enable_misread.py
"""
import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dat_reader import find_game_dat, load_dat      # noqa: E402
from civ_appender import apply_civ                  # noqa: E402

failures = 0


def check(label, cond, extra=""):
    global failures
    if cond:
        print(f"  ok   {label}")
    else:
        failures += 1
        print(f"  FAIL {label}" + (f"\n       {extra}" if extra else ""))


dat_path = find_game_dat()
if dat_path is None:
    print("  skip  no game DAT found")
    sys.exit(0)

dat = load_dat(str(dat_path))
TIMURID_SIEGECRAFT, ANARCHY = 32, 12           # Imperial / Castle UT catalog ids
TREBUCHETS = {331, 729, 730, 1923, 1942}
RANGE, LOS, SEARCH = 12, 1, 23
civ_def = {
    "alias": "UT Enable Probe", "description": "", "architecture": 2,
    "language": 0, "wonder": -1, "castle": -1,
    # Patient's unique unit (KM preset 19), so the elite UU is a melee unit.
    "bonuses": [[], [19], [[ANARCHY, 1]], [[TIMURID_SIEGECRAFT, 1]], []],
    "tree": [[], [], []],
}
with contextlib.redirect_stdout(io.StringIO()):
    res = apply_civ(dat, civ_def, target_slot=1)

uu, elite = res["uu_id"], res["elite_uu_id"]


def cmds_of(tid):
    return [(c.type, int(c.a), int(c.b), int(c.c), c.d) for c in dat.effects[dat.techs[tid].effect_id].effect_commands]


print("Timurid Siegecraft (Imperial UT)")
imp = cmds_of(res["imp_ut_tech_id"])
on_uu = [c for c in imp if c[1] in (uu, elite) and c[3] in (RANGE, LOS, SEARCH)]
check("no range / LOS / search radius lands on our unique unit", not on_uu, str(on_uu))
got = {c[1] for c in imp if c[0] == 4 and c[3] == RANGE and c[4] == 2.0}
check("all five trebuchets get +2 range", TREBUCHETS <= got, f"missing {sorted(TREBUCHETS - got)}")

print("Anarchy (Castle UT) still redirects to our own unique unit")
castle = cmds_of(res["castle_ut_tech_id"])
check("Anarchy touches our unique unit", any(c[1] in (uu, elite) for c in castle), str(castle))
check("and never the Huskarl it was written for (41/555/761)",
      not any(c[1] in (41, 555, 761) for c in castle), str(castle))

print()
if failures:
    print(f"{failures} FAILED")
    sys.exit(1)
print("All checks passed.")
