#!/usr/bin/env python3
"""A replaced civ's unique_unit_line names a line holding its own UU.

The AI addresses a civ's unique unit by line (my-unique-unit-line).  A UU no
vanilla civ owns (a KM-custom one) kept the replaced civ's line: an Amazon
Archer civ over the Goths still named the Huskarl line (-278), and its AI ally
acknowledged "train unique units" and never did, while a Mangudai civ (a line
the game knows) obeyed (in game, 2026-10-19).  patch_unitlines adds a line to
unitlines.json and points the civ at it; dat_json_files ships both files.
No DAT needed: the fixture is a small unitlines.json.

    venv/bin/python tests/test_unit_lines.py
"""
import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build_all import dat_json_files                        # noqa: E402
from civ_appender import _UNIT_LINE_RANGE, patch_civilizations_list, patch_unitlines   # noqa: E402

failures = 0


def check(label, cond, extra=""):
    global failures
    if cond:
        print(f"  ok   {label}")
    else:
        failures += 1
        print(f"  FAIL {label}" + (f" — {extra}" if extra else ""))


LINES = {"Hint": "LineIDs have to be between (-400, -199).", "UnitLines": [
    {"Name": "Huskarl Line", "Identifier": "huskarl-line", "LineID": -278, "IDChain": [41, 555]},
    {"Name": "Mangudai Line", "Identifier": "mangudai-line", "LineID": -274, "IDChain": [11, 561]},
    {"Name": "Taken", "Identifier": "taken", "LineID": -399, "IDChain": [1]},
]}
GOTHS, MONGOLS = 3, 12
CIVS = [{"internal_name": f"civ{i}"} for i in range(20)]
CIVS[GOTHS].update(unique_unit_id=41, elite_unique_unit_id=555, unique_unit_line=-278)
CIVS[MONGOLS].update(unique_unit_id=11, elite_unique_unit_id=561, unique_unit_line=-274)
AMAZON = {"name_sid": 1, "uu_unit_id": 2750, "uu_elite_id": 2751}     # KM-custom UU
MANGUDAI = {"name_sid": 2, "uu_unit_id": 11, "uu_elite_id": 561}       # a vanilla UU

print("=== patch_unitlines ===")
lines, civs = copy.deepcopy(LINES), copy.deepcopy(CIVS)
over = {GOTHS: AMAZON, 7: MANGUDAI}
patch_civilizations_list(civs, over)
added = patch_unitlines(lines["UnitLines"], civs, over)
new = next((l for l in lines["UnitLines"] if 2750 in l["IDChain"]), None)
check("a custom UU gets a line of its own", new is not None and new["IDChain"] == [2750, 2751], new)
check("its LineID is inside the range the file allows, and unused",
      new is not None and new["LineID"] in _UNIT_LINE_RANGE and new["LineID"] not in (-278, -274, -399),
      new and new["LineID"])
check("the custom civ points at it (no longer the Huskarl line)",
      new is not None and civs[GOTHS]["unique_unit_line"] == new["LineID"], civs[GOTHS].get("unique_unit_line"))
check("a vanilla UU takes the game's own line", civs[7].get("unique_unit_line") == -274, civs[7])
check("only the custom civ needed a new line", added == [GOTHS], added)
check("the game's lines are untouched", lines["UnitLines"][:3] == LINES["UnitLines"])
ids = [l["LineID"] for l in lines["UnitLines"]]
check("every LineID is unique", len(ids) == len(set(ids)), ids)
idents = [l["Identifier"] for l in lines["UnitLines"]]
check("every Identifier is unique", len(idents) == len(set(idents)), idents)

lines2, civs2 = copy.deepcopy(LINES), copy.deepcopy(CIVS)
two = {GOTHS: AMAZON, 5: {"name_sid": 3, "uu_unit_id": 2900, "uu_elite_id": None}}
patch_civilizations_list(civs2, two)
patch_unitlines(lines2["UnitLines"], civs2, two)
check("two custom civs get two different lines",
      civs2[GOTHS]["unique_unit_line"] != civs2[5]["unique_unit_line"])
check("a UU with no elite gets a one-unit chain",
      next(l for l in lines2["UnitLines"] if 2900 in l["IDChain"])["IDChain"] == [2900])

print("\n=== dat_json_files: both files beside the DAT go into the mod ===")
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "civilizations.json").write_text(json.dumps({"civilization_list": CIVS}), encoding="utf-8")
    (d / "unitlines.json").write_text(json.dumps(LINES), encoding="utf-8")
    out = dat_json_files(d / "empires2_x2_p1.dat", {GOTHS: AMAZON})
    check("both files are produced", set(out) == {"civilizations.json", "unitlines.json"}, sorted(out))
    shipped_lines = json.loads(out["unitlines.json"])["UnitLines"]
    shipped_civs = json.loads(out["civilizations.json"])["civilization_list"]
    line = next((l for l in shipped_lines if 2750 in l["IDChain"]), None)
    check("the shipped civilizations.json names the shipped line",
          line is not None and shipped_civs[GOTHS]["unique_unit_line"] == line["LineID"])
    check("the Hint survives", json.loads(out["unitlines.json"]).get("Hint") == LINES["Hint"])

    (d / "unitlines.json").unlink()
    out = dat_json_files(d / "empires2_x2_p1.dat", {GOTHS: AMAZON})
    check("no unitlines.json beside the DAT: civilizations.json still ships, unitlines.json doesn't",
          set(out) == {"civilizations.json"}, sorted(out))

print()
print("FAIL" if failures else "PASS", f"({failures} failure(s))")
sys.exit(1 if failures else 0)
