#!/usr/bin/env python3
"""One pool of unique-tech presets for both slots.

The Castle and Imperial preset pools number their techs independently —
castle preset 25 is Nomads (tech 487), imperial preset 25 is Drill (tech 6) —
and either slot may now hold a preset from either pool.  So every UT entry
carries its pool ("tier"), and every reader must look a preset up in that pool,
never the slot's.  The failure this guards is silent: the right number in the
wrong pool is a valid, different tech.

1. **Pure** — get_ut_entries gives every entry a tier, defaulting to the slot's
   own (every civ saved before the merge, every KM file); the saved file keeps
   it; the wizard door carries it; the name comes from the entry's own pool.
2. **Build** — a Castle UT holding an Imperial preset copies the Imperial tech's
   commands, still researches in the Castle Age, and takes the Imperial tech's
   hotkey; a slot holding its own pool builds exactly as before.  DAT-gated.

    venv/bin/python tests/test_ut_pools.py
"""
import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import civ_appender as ca                                # noqa: E402
import civ_schema                                        # noqa: E402
import wizard_build                                      # noqa: E402
from build_all import _ut_name, _ut_source                # noqa: E402

failures = 0


def check(label, cond, extra=""):
    global failures
    if cond:
        print(f"  ok   {label}")
    else:
        failures += 1
        print(f"  FAIL {label}" + (f"\n       {extra}" if extra else ""))


DRILL = 25                       # castle 25 = Nomads (487), imperial 25 = Drill (6)
check("preset 25 is a different tech in each pool (the trap this file guards)",
      ca.ut_source_tech(DRILL, "castle") == 487 and ca.ut_source_tech(DRILL, "imperial") == 6)

# ── 1. Pure ───────────────────────────────────────────────────────────────────
km = {"bonuses": [[], [0], [[DRILL, 2]], [[DRILL, 1]], []]}
check("a KM file's entries take their slot's pool",
      ca.get_ut_entries(km, "castle_ut") == [[DRILL, 2, "castle"]]
      and ca.get_ut_entries(km, "imperial_ut") == [[DRILL, 1, "imperial"]])
old_ef = {"castle_ut": {"effects": [{"id": DRILL, "multiplier": 1}]}}
check("an Empire Forge civ saved before the merge reads as its slot's pool",
      ca.get_ut_entries(old_ef, "castle_ut") == [[DRILL, 1, "castle"]])
cross = {"castle_ut": {"effects": [{"id": DRILL, "multiplier": 1, "tier": "imperial"}]}}
check("a cross-pool entry keeps its pool",
      ca.get_ut_entries(cross, "castle_ut") == [[DRILL, 1, "imperial"]])
check("a nonsense tier falls back to the slot's pool",
      ca.get_ut_entries({"castle_ut": {"effects": [{"id": 1, "tier": "feudal"}]}}, "castle_ut")
      == [[1, 1, "castle"]])
check("a malformed entry is dropped, not raised",
      ca.get_ut_entries({"castle_ut": {"effects": [{"multiplier": 2}, "x", {"id": 3}]}}, "castle_ut")
      == [[3, 1, "castle"]])

draft = {"castle_ut": {"mode": "vanilla", "effects": [{"id": DRILL, "multiplier": 1, "tier": "imperial"}]},
         "imperial_ut": {"mode": "custom", "effects": [{"id": 1, "multiplier": 3, "tier": "castle"},
                                                         {"id": 2, "multiplier": 1}]}}
back = civ_schema.to_draft(civ_schema.from_draft(draft))
check("a saved civ keeps each effect's pool",
      back["castle_ut"]["effects"] == [{"id": DRILL, "multiplier": 1, "tier": "imperial"}]
      and back["imperial_ut"]["effects"] == [{"id": 1, "multiplier": 3, "tier": "castle"},
                                             {"id": 2, "multiplier": 1, "tier": "imperial"}],
      (back["castle_ut"]["effects"], back["imperial_ut"]["effects"]))
legacy = civ_schema.to_draft({"format": "empireforge_v2", "castle_ut": {"effects": [{"id": 4}]},
                              "imperial_ut": {"effects": [{"id": 4}]}})
check("a pre-merge saved file gets each slot's own pool on load",
      legacy["castle_ut"]["effects"][0]["tier"] == "castle"
      and legacy["imperial_ut"]["effects"][0]["tier"] == "imperial")

cd = wizard_build._draft_to_civ_def(draft)
check("the wizard door hands apply_civ each effect's pool",
      ca.get_ut_entries(cd, "castle_ut") == [[DRILL, 1, "imperial"]]
      and ca.get_ut_entries(cd, "imperial_ut") == [[1, 3, "castle"], [2, 1, "imperial"]],
      (ca.get_ut_entries(cd, "castle_ut"), ca.get_ut_entries(cd, "imperial_ut")))

check("a KM name lookup reads the entry's own pool",
      _ut_name(*_ut_source(cross, 2)) == _ut_name(DRILL, castle=False)
      and _ut_name(*_ut_source(cross, 2)) != _ut_name(DRILL, castle=True),
      (_ut_name(*_ut_source(cross, 2)), _ut_name(DRILL, castle=False)))
check("...and an empty slot still gets its own generic name",
      _ut_name(*_ut_source({}, 2)) == "Castle Unique Technology"
      and _ut_name(*_ut_source({}, 3)) == "Imperial Unique Technology")

# ── 2. Build (DAT) ────────────────────────────────────────────────────────────
from dat_reader import find_game_dat, load_dat           # noqa: E402

dat_path = find_game_dat()
if dat_path is None:
    print("  skip  no game DAT found — build checks skipped")
    sys.exit(1 if failures else 0)
dat = load_dat(str(dat_path))


def sig(cmds):
    return [(int(c.type), int(c.a), int(c.b), int(c.c), round(float(c.d), 4)) for c in cmds]


def build(slot, castle_fx, imperial_fx=()):
    cd = {"alias": "Pool Probe", "tagline": "", "architecture": 1, "language": 0,
          "wonder": -1, "castle": -1, "bonuses": [[], [], [], [], []], "tree": [[], [], []],
          "castle_ut": {"mode": "vanilla", "effects": list(castle_fx)},
          "imperial_ut": {"mode": "vanilla", "effects": list(imperial_fx)}}
    with contextlib.redirect_stdout(io.StringIO()):
        return ca.apply_civ(dat, cd, target_slot=slot)


drill_alone, _, _ = ca._build_ut_effect_cmds(dat, [[DRILL, 1, "imperial"]], "probe", "castle")
nomads_alone, _, _ = ca._build_ut_effect_cmds(dat, [[DRILL, 1, "castle"]], "probe", "castle")
check("the builder picks the entry's pool over the slot's default",
      sig(drill_alone) != sig(nomads_alone) and drill_alone)

res = build(5, [{"id": DRILL, "multiplier": 1, "tier": "imperial"}])
tid = res["castle_ut_tech_id"]
t = dat.techs[tid]
check("a Castle UT holding Drill copies Drill's commands, not Nomads'",
      sig(dat.effects[t.effect_id].effect_commands) == sig(drill_alone),
      (sig(dat.effects[t.effect_id].effect_commands)[:4], sig(drill_alone)[:4]))
check("...and still needs the Castle Age (102)", 102 in list(t.required_techs), list(t.required_techs))
check("...and takes Drill's hotkey",
      t.research_locations[0].hot_key_id == dat.techs[6].research_locations[0].hot_key_id)

res = build(6, [], [{"id": 1, "multiplier": 1, "tier": "castle"}])
t = dat.techs[res["imp_ut_tech_id"]]
castle1, _, _ = ca._build_ut_effect_cmds(dat, [[1, 1, "castle"]], "probe", "imperial")
check("an Imperial UT holding a Castle preset copies that one and needs the Imperial Age",
      sig(dat.effects[t.effect_id].effect_commands) == sig(castle1) and 103 in list(t.required_techs))

# Both pools in one UT, with a multiplier on the cross-pool one.
res = build(7, [{"id": 7, "multiplier": 1, "tier": "castle"},
                {"id": DRILL, "multiplier": 2, "tier": "imperial"}])
t = dat.techs[res["castle_ut_tech_id"]]
want, _, _ = ca._build_ut_effect_cmds(dat, [[7, 1, "castle"], [DRILL, 2, "imperial"]], "probe", "castle")
check("one UT can stack presets from both pools", sig(dat.effects[t.effect_id].effect_commands) == sig(want))

# A slot's own pool, with and without the explicit tier, builds identically.
r1 = build(8, [{"id": 7, "multiplier": 1}])
r2 = build(9, [{"id": 7, "multiplier": 1, "tier": "castle"}])
e1 = dat.effects[dat.techs[r1["castle_ut_tech_id"]].effect_id].effect_commands
e2 = dat.effects[dat.techs[r2["castle_ut_tech_id"]].effect_id].effect_commands
check("an entry without a tier builds exactly like its slot's pool", sig(e1) == sig(e2) and e1)

print()
if failures:
    print(f"{failures} check(s) FAILED")
    sys.exit(1)
print("All checks passed.")
