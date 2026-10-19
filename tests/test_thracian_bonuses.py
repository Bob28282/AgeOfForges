#!/usr/bin/env python3
"""Thracian bonuses from Chronicles, read from the player's DAT (#74).  DAT-gated.

  458  All buildings except Town Centers can be built on any elevation.
       No effect command does this: it is each building's hill_mode, 0 on the
       Thracians' copies of 131 buildings (Wonder included), 2 on their TCs.
  459  Castles and towers make nearby Lumberjacks and Miners work 15% faster.
       The Thracian Fort's six aura tasks (action 155, attribute 13), copied
       onto this civ's Castle and towers.

Both edit unit data rather than writing effect commands, so this saves the
DAT and reads it back: a change the lazy loader didn't write out would pass
in memory and do nothing in game.

    venv/bin/python tests/test_thracian_bonuses.py
"""
import contextlib
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dat_reader import find_game_dat, load_dat      # noqa: E402
from dat_lazy import save_bytes                     # noqa: E402
from civ_appender import apply_civ, HANDLED_BONUS_IDS   # noqa: E402
import bonus_names                                  # noqa: E402

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

print("both cards are offered")
offered_gap = {b["id"] for b in bonus_names.unsupported_bonuses()} & {458, 459}
check("458 and 459 are handled and named", {458, 459} <= HANDLED_BONUS_IDS and not offered_gap,
      f"unsupported: {sorted(offered_gap)}")

dat = load_dat(str(dat_path))
thr = next(i for i, c in enumerate(dat.civs) if c.name == "Thracians")
# Not slot 1: apply_civ clones whatever is in slot 1 (the Britons) as its
# template, so a card applied there would leak into the later probes.
SLOT_ELEV, SLOT_AURA, SLOT_AURA2 = 5, 6, 7
for slot, bonuses in ((SLOT_ELEV, [[458, 1]]), (SLOT_AURA, [[459, 1]]), (SLOT_AURA2, [[459, 2]])):
    civ_def = {"alias": f"Thracian Probe {slot}", "description": "", "architecture": 2,
               "language": 0, "wonder": -1, "castle": -1,
               "bonuses": [bonuses, [], [], [], []], "tree": [[], [], []]}
    with contextlib.redirect_stdout(io.StringIO()):
        apply_civ(dat, civ_def, target_slot=slot)

with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "empires2_x2_p1.dat"
    out.write_bytes(save_bytes(dat))
    back = load_dat(str(out))

print("458: buildings on any elevation (read back from the saved DAT)")
units = back.civs[SLOT_ELEV].units
for uid, name in ((12, "Barracks"), (68, "Mill"), (82, "Castle"), (276, "Wonder")):
    check(f"{name} ({uid}) can be built on any elevation", units[uid].hill_mode == 0, f"hill_mode={units[uid].hill_mode}")
check("Town Center (109) keeps its elevation rule", units[109].hill_mode == back.civs[thr].units[109].hill_mode != 0,
      f"ours={units[109].hill_mode}")
want = {uid for uid, t in enumerate(back.civs[thr].units) if t is not None and t.type == 80 and t.hill_mode == 0}
got = {uid for uid, u in enumerate(units) if u is not None and u.type == 80 and u.hill_mode == 0}
check("matches the Thracians building for building", want <= got, f"missing {sorted(want - got)[:10]}")
check("an untouched civ keeps the normal rule", back.civs[SLOT_AURA].units[12].hill_mode != 0)

print("459: Castle and tower aura (read back from the saved DAT)")
LUMBER_MINERS = {123, 218, 124, 220, 579, 581}


def auras(slot, uid):
    u = back.civs[slot].units[uid]
    return [t for t in u.bird.tasks if t.action_type == 155 and int(t.search_wait_time) == 13]


for uid, name in ((82, "Castle"), (79, "Watch Tower"), (234, "Guard Tower"), (235, "Keep"), (236, "Bombard Tower")):
    a = auras(SLOT_AURA, uid)
    check(f"{name}: work-rate aura on Lumberjacks and Miners",
          {t.unit_id for t in a} == LUMBER_MINERS and all(abs(t.work_value_1 - 0.15) < 1e-6 for t in a),
          str([(t.unit_id, round(t.work_value_1, 3)) for t in a]))
ids = [t.id for t in back.civs[SLOT_AURA].units[82].bird.tasks]
check("task ids stay sequential", ids == list(range(len(ids))), str(ids))
check("x2 makes it +30%", all(abs(t.work_value_1 - 0.30) < 1e-6 for t in auras(SLOT_AURA2, 82)))
check("a civ without the card has no such aura", not auras(SLOT_ELEV, 82))


# The tasks alone do nothing: attribute 63 (Combat Ability) bit 32 switches
# task-155 auras on, as the Thracians' static bonus does for their Castle.
# Missing in the first version; in game there was no aura and no outline.
def aura_bits(slot):
    out = {}
    for t in back.techs:
        if t.civ != slot or not 0 <= t.effect_id < len(back.effects):
            continue
        for c in back.effects[t.effect_id].effect_commands:
            if c.type == 4 and int(c.c) == 63:
                out[int(c.a)] = out.get(int(c.a), 0) + int(c.d)
    return out


for slot, label in ((SLOT_AURA, "x1"), (SLOT_AURA2, "x2")):
    bits = aura_bits(slot)
    check(f"{label}: Castle and all four towers get the aura bit (+32 to attribute 63), unscaled",
          all(bits.get(uid) == 32 for uid in (82, 79, 234, 235, 236)), str(bits))
check("a civ without the card switches no aura on", not aura_bits(SLOT_ELEV))

print()
if failures:
    print(f"{failures} FAILED")
    sys.exit(1)
print("All checks passed.")
