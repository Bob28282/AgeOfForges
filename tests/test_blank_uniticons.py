#!/usr/bin/env python3
"""The UI mod never ships a blank unit icon.

Every icon in uniticons/ is written to wpfg/resources/uniticons/ in the UI mod,
where it replaces the game's own.  27 of them were blank placeholders, so with
any Empire Forge mod enabled the civ picker drew a blue box for 22 civs we
never touched: the Poles' and Lithuanians' Winged Hussar, the Gurjaras' two
second units, the Hindustanis' Imperial Camel Rider, ...  Reported by
Maruviel, 2026-10-11.

    venv/bin/python tests/test_blank_uniticons.py
"""
import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image                                  # noqa: E402
from build_all import _build_combined_ui_zip           # noqa: E402


def _is_blank_png(data: bytes) -> bool:
    """Every pixel identical.  Our own check, not build_all's, so the test
    does not trust the code under test."""
    with Image.open(io.BytesIO(data)) as im:
        return all(lo == hi for lo, hi in im.convert("RGBA").getextrema())

failures = 0


def check(label, cond, extra=""):
    global failures
    if cond:
        print(f"  ok   {label}")
    else:
        failures += 1
        print(f"  FAIL {label}" + (f" — {extra}" if extra else ""))


icons = sorted((ROOT / "uniticons").glob("*.png"))
blank = {p.name for p in icons if _is_blank_png(p.read_bytes())}
real = {p.name for p in icons} - blank
check("the blank detector finds the known placeholder (371, Winged Hussar)", "371_50730.png" in blank)
check("and passes a real portrait (041, Longbowman)", "041_50730.png" in real)

ui = zipfile.ZipFile(io.BytesIO(_build_combined_ui_zip({}, {}, {})))
shipped = {n.rsplit("/", 1)[-1]: ui.read(n) for n in ui.namelist()
           if n.startswith("resources/_common/wpfg/resources/uniticons/")}
check("no blank icon reaches the UI mod",
      not any(_is_blank_png(b) for b in shipped.values()),
      sorted(n for n, b in shipped.items() if _is_blank_png(b)))
check("every real icon still ships", real <= set(shipped), sorted(real - set(shipped)))

print()
if failures:
    print(f"{failures} FAILED")
    sys.exit(1)
print("All checks passed.")
