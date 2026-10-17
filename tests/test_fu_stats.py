#!/usr/bin/env python3
"""Post-Imperial ("fully upgraded") stats read from the DAT (fu_stats.py).

Pins vanilla civs against known numbers: Britons archers (civ range bonus,
Yeomen, the skirmisher carve-out, team-bonus work rate) and Malians (a reduced
Blacksmith, Farimba reaching cavalry but not the Mangudai).  Also pins the
reachability rules that the first prototype got wrong.  DAT-gated.

    venv/bin/python tests/test_fu_stats.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

failures = 0


def check(label, cond, extra=""):
    global failures
    if cond:
        print(f"  ok   {label}")
    else:
        failures += 1
        print(f"  FAIL {label}" + (f" — {extra}" if extra else ""))


try:
    from dat_reader import find_game_dat, load_dat
    dat_path = find_game_dat()
except Exception:                                            # noqa: BLE001
    dat_path = None
if dat_path is None:
    print("  skip  no game DAT found")
    sys.exit(0)

from fu_stats import Simulation, reachable_techs                            # noqa: E402

dat = load_dat(str(dat_path))
BRITONS, MALIANS = 1, 26
PIERCE, MELEE = 3, 4
FARIMBA, CHEMISTRY = 577, 47


def sources(s):
    return {c["tech"] for c in s["changes"]}


print("=== Britons ===")
brit = Simulation(dat, BRITONS)
lb = brit.stats(8)
check("Longbowman upgrades to Elite Longbowman", lb["unit"] == 530, lb["unit"])
check("Elite Longbowman: 11 attack, 12 range, 3/5 armour",
      (lb["attack"][PIERCE], lb["range"], lb["armor"][MELEE], lb["armor"][PIERCE]) == (11, 12, 3, 5),
      f"{lb['attack'][PIERCE]} atk, {lb['range']} range, {lb['armor'][MELEE]}/{lb['armor'][PIERCE]}")

# Elite Skirmisher completing fires "Imperial Skirmisher (disable)" before the
# Imperial Skirmisher can be researched: auto-fire techs settle first.
sk = brit.stats(7)
check("Skirmisher stops at Elite Skirmisher, not Imperial", sk["unit"] == 6, sk["unit"])
check("Elite Skirmisher: civ range bonus cancels, Yeomen does not (range 9)", sk["range"] == 9, sk["range"])

arb = brit.stats(4)
check("Archer upgrades to Arbalester", arb["unit"] == 492, arb["unit"])
range_train = next(t for t in arb["train"] if t["building"] == 87)
check("Archery Range work rate = team bonus x Conscription",
      abs(range_train["work_rate"] - 1.1 * 1.33) < 0.01, range_train["work_rate"])

# ...except for the Vietnamese, whose team bonus disables that disabler.
vietnamese = next(i for i, c in enumerate(dat.civs) if c.name == "Vietnamese")
check("Vietnamese team bonus reaches the Imperial Skirmisher",
      Simulation(dat, vietnamese).stats(7)["unit"] == 1155)
others = [c.name for i, c in enumerate(dat.civs[1:], 1)
          if i != vietnamese and 655 in reachable_techs(dat, i)]
check("no other civ reaches the Imperial Skirmisher", not others, others)

print("\n=== Malians ===")
mali = Simulation(dat, MALIANS)
check("no Blast Furnace, Halberdier or Hussar",
      not {75, 429, 428} & set(mali.techs), sorted({75, 429, 428} & set(mali.techs)))
cav = mali.stats(38)
check("Knight line stops at Cavalier", cav["unit"] == 283, cav["unit"])
check("Farimba gives the Cavalier +5 (19 attack)",
      FARIMBA in sources(cav) and cav["attack"][MELEE] == 19, cav["attack"][MELEE])
check("Farimba does not touch the Mangudai (class 36)", FARIMBA not in sources(mali.stats(11)))

# Chemistry's unit -1 / class -1 command is not "every unit": melee is unaffected.
champ = mali.stats(74)
check("Chemistry does not touch the Champion", CHEMISTRY not in sources(champ))
check("Malian Champion: base + Forging + Iron Casting only",
      champ["attack"][MELEE] == next(a.amount for a in dat.civs[MALIANS].units[567].type_50.attacks
                                     if a.class_ == MELEE) + 2,
      champ["attack"][MELEE])

# What a civ can make is read from the simulated DAT (Simulation.available_lines),
# one entry per line as its final unit.  Each case below was wrong once.
print("\n=== available units (vanilla) ===")
CIV = {c.name: i for i, c in enumerate(dat.civs)}


def finals(civ_name):
    sim = Simulation(dat, CIV[civ_name])
    return sim, {sim.final_unit(b) for b in sim.available_lines()}


_, brit_units = finals("British")
check("Britons: no Condottiero, Imperial Skirmisher or Genitour",
      not {882, 1155, 1010, 1012} & brit_units, sorted({882, 1155, 1010, 1012} & brit_units))
check("Britons: Elite Skirmisher shown once, as its final unit", 6 in brit_units and 7 not in brit_units)
# Tech 121 type=102s these, but a type=8 in the civ's tree wins (quirk 10).
check("Berbers keep the Genitour (Elite)", 1012 in finals("Berbers")[1])
check("Italians keep the Condottiero", 882 in finals("Italians")[1])
check("Tatars keep the Flaming Camel (make-avail is type=2 with b=-1)", 1263 in finals("Tatars")[1])
# Heroes are made available by attribute 127, never by type=2.
check("Shu get Liu Bei", 1966 in finals("Shu")[1])
# The civ's own tech-tree effect hides units at game start.
check("Incas have no stray Militia", 74 not in finals("Incas")[1])
goths, goth_units = finals("Goths")
check("Goths: Elite Huskarl trains at the Castle and the Barracks",
      555 in goth_units and [t.unit_id for t in goths.units[555].creatable.train_locations] == [82, 12])
check("the Merchant Ship's Port isn't a building any civ has", 2149 not in brit_units)

# A custom civ, read from what apply_civ wrote: the questions from the user
# request that started this (Mangudai + "cavalry" bonuses, Anarchy + Perfusion).
print("\n=== custom civs ===")
import contextlib, copy, io, json                          # noqa: E402,E401
from civ_appender import apply_civ                          # noqa: E402
from civ_schema import FORMAT_KEY                           # noqa: E402

units, buildings, techs = json.loads(
    (ROOT / "my_civs" / "14_Barracks Enjoyers.json").read_text(encoding="utf-8"))["tree"]
TREE = {"units": sorted(set(units) | {448, 546, 441, 38, 283, 569, 39, 474}),
        "buildings": sorted(set(buildings) | {101}),
        "techs": sorted(set(techs) | {435, 39, 81, 82, 80, 437, 436, 75, 254, 428, 209})}
MANGUDAI_KM, STIRRUPS, ANARCHY, PERFUSION, FARIMBA_KM = 11, 3, 12, 12, 23
MOUNTED_HP_20 = 4


def build(slot, castle, imperial, bonuses):
    civ = {"format": FORMAT_KEY, "alias": f"FU {slot}", "architecture": 2, "language": 0,
           "bonuses": [{"id": b, "multiplier": 1} for b in bonuses],
           "unique_unit": {"km_idx": MANGUDAI_KM},
           "castle_ut": {"mode": "vanilla", "effects": [{"id": castle, "multiplier": 1}]},
           "imperial_ut": {"mode": "vanilla", "effects": [{"id": imperial, "multiplier": 1}]},
           "tree": TREE}
    with contextlib.redirect_stdout(io.StringIO()):
        r = apply_civ(dat, copy.deepcopy(civ), target_slot=slot)
    return Simulation(dat, slot), r


sim, r = build(11, STIRRUPS, FARIMBA_KM, [MOUNTED_HP_20])
mang, pal = sim.stats(11), sim.stats(38)
check("+20% mounted HP reaches the Mangudai", mang["hp"] == round(60 * 1.2) + 20, mang["hp"])
check("Stirrups speeds the Paladin's attack", r["castle_ut_tech_id"] in sources(pal))
check("Stirrups does not touch the Mangudai", r["castle_ut_tech_id"] not in sources(mang))
check("Farimba gives the Paladin +5", r["imp_ut_tech_id"] in sources(pal) and pal["attack"][MELEE] == 23,
      pal["attack"][MELEE])
check("Farimba does not touch the Mangudai", r["imp_ut_tech_id"] not in sources(mang))

# The tree list carries ids the player never ticked (every UU, the Condottiero,
# ...); the panel showed all of them at the Castle once.
sim_units = {sim.final_unit(b) for b in sim.available_lines()}
castle = sorted(u for u in sim_units
                if any(t.unit_id == 82 for t in sim.units[u].creatable.train_locations))
check("custom civ's Castle: Elite Mangudai, Petard, Trebuchet only",
      castle == sorted([561, 440, 331]), castle)
check("custom civ: no unticked bonus-card units (Condottiero, Winged Hussar, Flaming Camel)",
      not {882, 1707, 1263} & sim_units, sorted({882, 1707, 1263} & sim_units))

sim, r = build(12, ANARCHY, PERFUSION, [])
train = sim.stats(11)["train"]
check("Anarchy adds the Barracks; the Castle still trains it", [t["building"] for t in train] == [82, 12],
      [t["building"] for t in train])
check("Perfusion doubles the Barracks it trains at (x Conscription)",
      abs(train[1]["work_rate"] - 2 * 1.33) < 0.01, train[1]["work_rate"])

print()
print("FAIL" if failures else "PASS", f"({failures} failure(s))")
sys.exit(1 if failures else 0)
