#!/usr/bin/env python3
"""
post_build_template.py — add your own changes on top of an Empire Forge mod.

Empire Forge builds the civ; this script edits the finished game data file
(empires2_x2_p1.dat) inside the mod's -data folder to add what Empire Forge
doesn't offer.  Read docs/EXTENDING.md first — it explains the whole route.

    pip install genieutils-py==0.1.2          (needs Python 3.11 or newer)
    python post_build_template.py "<path>/mods/local/MyMod-data" --list-civs
    python post_build_template.py "<path>/mods/local/MyMod-data" --civ British

Safe to run again and again: the first run keeps a pristine copy of Empire
Forge's file next to it (empires2_x2_p1.dat.empireforge) and every run starts
from that copy, so a change never applies twice.  Rebuild in Empire Forge and
unzip the new mod over the old one, and the next run notices the new file and
starts from it instead.

────────────────────────────────────────────────────────────────────────────
A brief for your AI code editor — paste this, plus your idea, into its chat:

    You are editing an Age of Empires II: Definitive Edition data file with
    the genieutils-py library, inside apply_my_changes() in this script.
    Before writing any code, read the Empire Forge modding reference in the
    llm/ folder of https://github.com/napkingcole/aoe2-empire-forge —
    effect_commands.md, unit_quirks.md, advanced_techniques.md — and its
    CLAUDE.md "Critical Quirks".  Rules:
      * Find the vanilla precedent first: search the data for an existing
        effect or tech that already does something similar and copy its
        shape.  Never guess an attribute id or a command type.
      * Never hard-code a tech, effect or unit id that Empire Forge created;
        find it by name and civ (they change between builds).  Vanilla ids
        are fine.
      * Keep each Effect under ~180 commands; the game crashes near 189.
      * New text must reuse an EXISTING string id; brand-new ids are ignored.
      * Explain what you changed and how I can check it in game.
────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from copy import deepcopy
from pathlib import Path

from genieutils.datfile import DatFile
from genieutils.effect import Effect, EffectCommand
from genieutils.tech import ResearchLocation, ResearchResourceCost, Tech

DAT_IN_MOD = Path("resources/_common/dat/empires2_x2_p1.dat")

# Effect command types (EffectCommand.type).  See llm/effect_commands.md.
EC_SET, EC_RESOURCE, EC_ENABLE, EC_UPGRADE, EC_ADD, EC_MULTIPLY = 0, 1, 2, 3, 4, 5
# A few unit attributes (EffectCommand.c).  Full table: llm/effect_commands.md.
HP, LOS, ATTACK, ARMOR, WORK_RATE = 0, 1, 9, 8, 13
# Ages, as tech ids — a tech that requires one waits for that age.
FEUDAL, CASTLE, IMPERIAL = 101, 102, 103


# ── Your changes ──────────────────────────────────────────────────────────────

def apply_my_changes(data: DatFile, civ: int) -> None:
    """Edit `data` for civ index `civ`.  Replace the example with your own.

    The example is a civ bonus written exactly the way the game writes its
    own: a hidden tech that belongs to the civ, researches itself at the start
    (or when its prerequisites are met), and runs one Effect.  The command is
    the one Loom uses — +15 HP to class 4, every villager form.
    """
    add_civ_bonus(data, civ, "Post-build: Villagers +15 HP", [
        EffectCommand(type=EC_ADD, a=-1, b=4, c=HP, d=15.0),
    ])
    # The same bonus, but only from the Castle Age:
    # add_civ_bonus(data, civ, "Post-build: Villagers +15 HP (Castle)", [...], requires=[CASTLE])


# ── Helpers ───────────────────────────────────────────────────────────────────

def add_civ_bonus(data: DatFile, civ: int, name: str, commands: list[EffectCommand],
                  requires: list[int] = ()) -> int:
    """Add a hidden, self-researching tech for `civ` that runs `commands`;
    returns its tech id.  `requires` lists tech ids it waits for (an age, or
    another tech) — all of them.  This is the shape of every vanilla
    "C-Bonus, ..." tech and of Empire Forge's own custom bonuses."""
    data.effects.append(Effect(name=name, effect_commands=list(commands)))
    reqs = list(requires)[:6]
    empty = ResearchResourceCost(type=-1, amount=0, flag=0)
    data.techs.append(Tech(
        required_techs=tuple(reqs + [-1] * (6 - len(reqs))),
        resource_costs=(deepcopy(empty), deepcopy(empty), deepcopy(empty)),
        required_tech_count=len(reqs),
        civ=civ,
        full_tech_mode=0,
        language_dll_name=-1, language_dll_description=-1,
        effect_id=len(data.effects) - 1,
        type=0,
        icon_id=-1,
        language_dll_help=-1, language_dll_tech_tree=-1,
        name=name,
        # Vanilla's self-researching bonus techs are repeatable; a resource
        # trickle (EC_RESOURCE b=-1) only works when it is.
        repeatable=1,
        # Exactly one location, at -1 (no building): an empty list makes the
        # game silently ignore the tech.
        research_locations=[ResearchLocation(location_id=-1, research_time=0,
                                             button_id=0, hot_key_id=-1)],
    ))
    return len(data.techs) - 1


def find_civ(data: DatFile, name: str) -> int:
    """A civ's index by its name in the data file — the VANILLA civ whose slot
    your custom civ replaced ("British" for the Britons slot), not your civ's
    display name.  --list-civs prints them all."""
    for i, c in enumerate(data.civs):
        if c.name.lower() == name.lower():
            return i
    raise SystemExit(f"No civ named {name!r} in this file. Run with --list-civs to see the names.")


def civ_techs(data: DatFile, civ: int) -> list[tuple[int, str]]:
    """(id, name) of every tech that belongs only to `civ` — Empire Forge
    names its own readably: "<Civ> Castle UT", "<Civ> Imperial UT",
    "C-Bonus, Custom" for custom bonuses.  Use this to find them by name."""
    return [(i, t.name) for i, t in enumerate(data.techs) if t.civ == civ]


# ── Plumbing ──────────────────────────────────────────────────────────────────

def _sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description="Add your own changes to an Empire Forge mod.")
    ap.add_argument("data_mod", type=Path, help="the mod's -data folder (unzipped)")
    ap.add_argument("--civ", help="the civ to change, by its name in the data file (see --list-civs)")
    ap.add_argument("--list-civs", action="store_true", help="print every civ's index and name, then stop")
    args = ap.parse_args()

    dat = args.data_mod / DAT_IN_MOD
    if not dat.exists():
        raise SystemExit(f"No data file at {dat} — point at the mod's -data folder (unzipped).")
    pristine = dat.with_name(dat.name + ".empireforge")    # Empire Forge's own output
    stamp = dat.with_name(dat.name + ".written")           # what this script last wrote

    # A data file we didn't write is a fresh Empire Forge build: start from it.
    if not pristine.exists() or not stamp.exists() or stamp.read_text().strip() != _sha1(dat):
        shutil.copy2(dat, pristine)
        print(f"Using Empire Forge's file as the starting point ({pristine.name}).")

    print("Reading the data file (this takes a little while)...")
    data = DatFile.parse(str(pristine))

    if args.list_civs:
        for i, c in enumerate(data.civs):
            print(f"  {i:3}  {c.name}")
        return
    if not args.civ:
        raise SystemExit("Say which civ to change with --civ (see --list-civs).")

    civ = find_civ(data, args.civ)
    apply_my_changes(data, civ)
    data.save(str(dat))
    stamp.write_text(_sha1(dat))
    print(f"Saved {dat}.  Your civ's own techs now: {[n for _, n in civ_techs(data, civ)][-5:]}")


if __name__ == "__main__":
    sys.exit(main())
