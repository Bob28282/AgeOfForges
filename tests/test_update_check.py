#!/usr/bin/env python3
"""The update check's version order: a pre-release sorts below its release.

A preview build ("2.6.2-preview.1") must still be offered the real 2.6.2 when
it ships; read digit by digit it used to rank ABOVE it, so preview testers
would never have been told to update.

    venv/bin/python tests/test_update_check.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from update_check import _parse_version as v                 # noqa: E402

failures = 0


def check(label, cond):
    global failures
    print(("  ok   " if cond else "  FAIL ") + label)
    failures += 0 if cond else 1


check("2.6.2 is newer than 2.6.2-preview.1", v("2.6.2") > v("2.6.2-preview.1"))
check("v2.6.2 (tag form) is newer than 2.6.2-preview.1", v("v2.6.2") > v("2.6.2-preview.1"))
check("2.6.2-preview.2 is newer than 2.6.2-preview.1", v("2.6.2-preview.2") > v("2.6.2-preview.1"))
check("2.6.2-preview.1 is newer than 2.6.1", v("2.6.2-preview.1") > v("2.6.1"))
check("2.6.1 is newer than 2.6.1-beta.1", v("2.6.1") > v("2.6.1-beta.1"))
check("2.7.0 is newer than 2.6.10", v("2.7.0") > v("2.6.10"))
check("2.6 equals 2.6.0", v("2.6") == v("2.6.0"))
check("the same version is not newer", not v("2.6.2") > v("2.6.2"))

print()
print("FAIL" if failures else "PASS", f"({failures} failure(s))")
sys.exit(1 if failures else 0)
