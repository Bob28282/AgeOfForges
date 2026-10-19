#!/usr/bin/env python3
"""The Fortified Outpost as a custom bonus target (user request, 2026-10-19).

It's the Outpost upgraded through the Macedonians' team bonus (team bonus 87
here), so a building card's usual "every age version" rule tied it to plain
Outposts.  It now has its own Buildings tile and belongs to Defensive
buildings, and both reach the fortified one ONLY (custom_bonus.EXACT_BUILDINGS).
The Outpost's own tile still covers the Outpost and its upgrade.

    venv/bin/python tests/test_fortified_outpost.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import custom_bonus as cb                                   # noqa: E402

failures = 0


def check(label, cond, extra=""):
    global failures
    print(("  ok   " if cond else "  FAIL ") + label + ("" if cond else f" — {extra}"))
    failures += 0 if cond else 1


# The game's Outpost line, as the build's line_of would give it.
LINE = {598: {598, 2415, 2417}, 2415: {598, 2415, 2417}, 2417: {598, 2415, 2417}}
line_of = lambda uid: set(LINE.get(uid, {uid}))            # noqa: E731
BLD = lambda uid, name: {"type": "unit", "id": uid, "name": name, "kind": "building"}  # noqa: E731

tile = cb._target_selectors(BLD(2415, "Fortified Outpost"), line_of, None)[1]
check("the Fortified Outpost tile reaches both its forms", {2415, 2417} <= tile, tile)
check("...and not the plain Outpost", 598 not in tile, tile)
outpost = cb._target_selectors(BLD(598, "Outpost"), line_of, None)[1]
check("the Outpost tile still covers the Outpost and its upgrade", {598, 2415, 2417} <= outpost, outpost)
classes, ids = cb._target_selectors({"type": "group", "id": "defensive"}, line_of, None)
check("Defensive buildings includes the Fortified Outpost", {2415, 2417} <= ids, ids)
check("...not plain Outposts", 598 not in ids, ids)
check("...and still every tower by class", 52 in classes, classes)

import app                                                  # noqa: E402
cat = app.app.test_client().get("/api/builder/custom-bonus/catalog").get_json()
fo = [b for b in cat["buildings"] if b["name"] == "Fortified Outpost"]
check("the Buildings tab offers a Fortified Outpost tile", len(fo) == 1 and fo[0]["id"] == 2415, fo)
check("...with its own art", bool(fo) and fo[0]["icon"].endswith("/Building/116.png"), fo)

print()
print("FAIL" if failures else "PASS", f"({failures} failure(s))")
sys.exit(1 if failures else 0)
