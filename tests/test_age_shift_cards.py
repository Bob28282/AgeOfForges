#!/usr/bin/env python3
"""Age-shift cards move exactly what their text names.  DAT-gated.

  247  "Parthian Tactics can be researched in the Castle Age"
  221  "Spearman- and Militia-line upgrades (except Man-at-Arms) available one
       age earlier"

Both scanned a whole building and moved every age-gated tech in it.  247 took
the entire Imperial Archery Range to Castle Age: Arbalester, Heavy Cavalry
Archer, Imperial Skirmisher, Elite Genitour, Heavy Mounted Crossbowman (even
with Mounted Crossbowmen unticked) and more.  221 moved Squires and Gambesons
to Feudal and Elite Varangian Guard to Castle Age.  Where the original was
type=8-unlocked by the tree, the type=102 meant to hide it did nothing (a
type=102 does not undo a type=8), so the player saw two buttons for one
upgrade.  Reported by Patient, 2026-10-10.

    venv/bin/python tests/test_age_shift_cards.py
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
# The Wololo Warlords tree from test_shared_prereq_bonuses, plus the Varangian
# Guard (2708) so 221's old scan had its Elite upgrade to copy.
TREE = [
    [13, 17, 21, 74, 545, 539, 331, 125, 83, 128, 474, 39, 5, 6, 7, 492, 24, 4, 567, 473, 77, 75, 359, 358, 93, 1903, 1901, 441, 546, 448, 569, 283, 38, 548, 422, 1258, 1907, 1904, 36, 1942, 691, 420, 1795, 528, 527, 1104, 442, 1372, 1370, 440, 2708],
    [12, 45, 49, 50, 68, 70, 72, 79, 82, 84, 87, 101, 103, 104, 109, 199, 209, 276, 562, 584, 598, 621, 792, 236, 235, 234, 155, 117, 487],
    [22, 101, 102, 103, 408, 47, 436, 437, 875, 215, 602, 435, 39, 219, 212, 211, 201, 200, 199, 75, 68, 67, 80, 82, 81, 77, 76, 74, 375, 374, 373, 65, 51, 50, 64, 377, 63, 140, 608, 93, 194, 322, 380, 54, 379, 321, 315, 233, 230, 45, 46, 438, 319, 316, 441, 439, 231, 252, 280, 8, 249, 213, 182, 55, 279, 278, 221, 203, 202, 17, 23, 15, 12, 13, 14, 48],
]
SLOT = 1


def shifted_copies(bonus_id: int) -> dict[int, list[int]]:
    """original tech id -> its prerequisites as copied, for every tech the
    card added.  Originals are matched by effect contents, not names."""
    start = len(dat.techs)
    civ_def = {"alias": f"Age Shift {bonus_id}", "description": "", "architecture": 2,
               "language": 0, "wonder": -1, "castle": -1,
               "bonuses": [[[bonus_id, 1]], [], [], [], []], "tree": TREE}
    with contextlib.redirect_stdout(io.StringIO()):
        apply_civ(dat, civ_def, target_slot=SLOT)

    def sig(t):
        if not 0 <= t.effect_id < len(dat.effects):
            return None
        return tuple((c.type, c.a, c.b, c.c, c.d) for c in dat.effects[t.effect_id].effect_commands)

    out = {}
    for tid in range(start, len(dat.techs)):
        t = dat.techs[tid]
        if t.civ != SLOT or not t.research_locations or t.research_locations[0].location_id not in (12, 87):
            continue
        orig = next((o for o in range(start) if dat.techs[o].civ == -1 and sig(dat.techs[o]) == sig(t)
                     and dat.techs[o].research_locations
                     and dat.techs[o].research_locations[0].button_id == t.research_locations[0].button_id),
                    None)
        out[orig] = [r for r in t.required_techs if r >= 0]
    return out


print("247: Parthian Tactics in the Castle Age")
moved = shifted_copies(247)
check("only Parthian Tactics (436) is copied", set(moved) == {436}, f"copied: {sorted(moved, key=str)}")
check("the copy needs Castle Age, not Imperial", 102 in moved.get(436, []) and 103 not in moved.get(436, []),
      str(moved.get(436)))

print("221: Spearman/Militia-line upgrades one age earlier")
moved = shifted_copies(221)
LINE = {207: "Long Swordsman", 217: "Two-Handed Swordsman", 264: "Champion",
        197: "Pikeman", 429: "Halberdier"}
check("exactly the five line upgrades are copied", set(moved) == set(LINE),
      f"copied: {sorted(moved, key=str)}, expected {sorted(LINE)}")
for tid, name in LINE.items():
    reqs = moved.get(tid, [])
    want = {207: 101, 197: 101}.get(tid, 102)
    check(f"{name} one age earlier", want in reqs, str(reqs))
for tid, name in {215: "Squires", 875: "Gambesons", 1454: "Elite Varangian Guard", 222: "Man-at-Arms"}.items():
    check(f"{name} is not moved", tid not in moved)

print()
if failures:
    print(f"{failures} FAILED")
    sys.exit(1)
print("All checks passed.")
