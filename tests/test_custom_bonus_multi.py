#!/usr/bin/env python3
"""Custom bonus cards with several targets (#76), as team bonuses (#54) and
inside a Custom unique tech (#75).

1. **Pure** — a card's targets share a family, it offers only the effects every
   target takes, an old single-"target" card still reads (and is still written
   for older versions), and team/UT refuse what they can't build.
2. **Build** — overlapping targets reach each unit once (Cavalry + the Knight
   line must not give the Knight its HP twice); team cards land in the team
   bonus effect for every ally; UT cards land in the UT's own effect, and a
   UT made of cards alone still gets its tech.  DAT-gated.

    venv/bin/python tests/test_custom_bonus_multi.py
"""
import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import custom_bonus as cb                                # noqa: E402
import civ_schema                                        # noqa: E402

failures = 0


def check(label, cond, extra=""):
    global failures
    if cond:
        print(f"  ok   {label}")
    else:
        failures += 1
        print(f"  FAIL {label}" + (f"\n       {extra}" if extra else ""))


G = lambda gid: {"type": "group", "id": gid}                          # noqa: E731
LINE = lambda uid, name: {"type": "unit", "id": uid, "name": name, "kind": "unit"}   # noqa: E731
BLD = lambda uid, name: {"type": "unit", "id": uid, "name": name, "kind": "building"}  # noqa: E731
HP = [{"attr": "hp", "op": "mul", "value": 20}]


def card(targets, effects=HP, **kw):
    return {"targets": targets, "effects": effects, **kw}


def norm(raw):
    out = cb.normalize([raw])
    return out[0] if out else None


# ── 1. Pure ───────────────────────────────────────────────────────────────────
old = norm({"target": G("cavalry"), "effects": HP})
check("a pre-#76 single-target card reads as one target",
      old is not None and old["targets"] == [G("cavalry")], old)
check("...and is still written with 'target' for older Empire Forge versions",
      old.get("target") == G("cavalry"))

two = norm(card([G("archers"), LINE(539, "Galley")],
                [{"attr": "range", "op": "add", "value": 1}]))
check("two targets survive", two is not None and len(two["targets"]) == 2, two)
check("a multi-target card carries no single 'target'", "target" not in two)
check("card text names every target",
      cb.card_text(two) == "Archers and Galley line: +1 range", cb.card_text(two))
three = norm(card([G("archers"), LINE(539, "Galley"), BLD(82, "Castle")],
                  [{"attr": "range", "op": "add", "value": 1}]))
check("three targets read 'A, B and C'",
      cb.card_text(three) == "Archers, Galley line and Castle: +1 range", cb.card_text(three))

dup = norm(card([G("archers"), G("archers")]))
check("the same target twice collapses to one", dup["targets"] == [G("archers")], dup)

mixed = norm(card([G("archers"), BLD(82, "Castle")],
                  [{"attr": "range", "op": "add", "value": 1},
                   {"attr": "speed", "op": "mul", "value": 10},
                   {"attr": "build_speed", "op": "mul", "value": 10}]))
check("Archers + Castle keep range (both take it) and drop speed and build speed",
      [e["attr"] for e in mixed["effects"]] == ["range"], mixed["effects"])

fam = norm(card([G("archers"), G("techs_blacksmith")]))
check("a tech mixed into a unit card is dropped, not the card",
      fam["targets"] == [G("archers")], fam["targets"])
techs = norm(card([G("techs_blacksmith"), G("set_farm")],
                  [{"attr": "tech_cost", "op": "mul", "value": -20}]))
check("techs combine with techs", techs is not None and len(techs["targets"]) == 2)
civ = norm(card([{"type": "civ", "id": "civ"}, {"type": "civ", "id": "civ", "age": 103}],
                [{"attr": "pop_cap", "op": "add", "value": 10}]))
check("the Civilization target stands alone", len(civ["targets"]) == 1, civ["targets"])

job = norm(card([{"type": "job", "id": "farmer"}, G("cavalry")],
                [{"attr": "hp", "op": "add", "value": 5}, {"attr": "los", "op": "add", "value": 1}]))
check("a villager job beside a unit group still refuses HP",
      [e["attr"] for e in job["effects"]] == ["los"], job["effects"])
solo_job = norm(card([{"type": "job", "id": "farmer"}], [{"attr": "work_rate", "op": "mul", "value": 10}]))
check("a lone job still says 'gather rate'", cb.card_text(solo_job) == "Farmers: +10% gather rate",
      cb.card_text(solo_job))

check("unpack takes a bare multi-target card", cb.unpack(two) == [two])

# Shortcodes: stored as typed, read as words in game, unknown ones left alone.
tok = norm(card([G("archers")], [{"attr": "cost", "op": "mul", "value": -10}],
                text="Archers -10% [gold]; [plus]1 [range], [nope]"))
check("shortcodes are stored exactly as typed", tok["text"] == "Archers -10% [gold]; [plus]1 [range], [nope]")
check("the game reads them as words", cb.card_text(tok) == "Archers -10% gold; +1 range, [nope]", cb.card_text(tok))
check("every token the browser draws has a word and an icon",
      all(w and icon.startswith("/static/icons/") for w, icon in
          ((t["word"], t["icon"]) for t in cb.catalog()["tokens"].values())))
check("each token's icon file exists",
      all((ROOT / "static" / "icons" / icon).exists() for _, icon in cb.TEXT_TOKENS.values()),
      [i for _, i in cb.TEXT_TOKENS.values() if not (ROOT / "static" / "icons" / i).exists()])

# Team / UT refusals.
check("team: a unit card is fine", cb.team_problem(two) is None)
check("team: tech cards are refused", cb.team_problem(techs) is not None)
check("team: civilization cards are refused", cb.team_problem(civ) is not None)
check("team: the Unique unit group is refused",
      cb.team_problem(norm(card([G("archers"), G("unique_unit")]))) is not None)
check("team: population space is refused",
      cb.team_problem(norm(card([G("military_buildings")],
                                [{"attr": "pop_space", "op": "add", "value": 5}]))) is not None)
check("UT: unit and tech cards are fine",
      cb.ut_problem(two) is None and cb.ut_problem(techs) is None)
check("UT: civilization cards are refused", cb.ut_problem(civ) is not None)

# The saved file keeps both new lists.
draft = {"custom_team_bonuses": [two],
         "castle_ut": {"mode": "custom", "effects": [], "custom_bonuses": [techs]}}
back = civ_schema.to_draft(civ_schema.from_draft(draft))
check("a saved civ keeps its team cards", back["custom_team_bonuses"] == [two], back["custom_team_bonuses"])
check("a saved civ keeps its Castle UT cards", back["castle_ut"]["custom_bonuses"] == [techs],
      back["castle_ut"])


# ── 2. Build (DAT) ────────────────────────────────────────────────────────────
from dat_reader import find_game_dat, load_dat          # noqa: E402

dat_path = find_game_dat()
if dat_path is None:
    print("  skip  no game DAT found — build checks skipped")
    sys.exit(1 if failures else 0)

import civ_appender as ca                                # noqa: E402
import wizard_build                                      # noqa: E402

dat = load_dat(str(dat_path))


def civ_def(**kw):
    out = {"alias": "Targets Probe", "tagline": "", "architecture": 1, "language": 0,
           "wonder": -1, "castle": -1, "bonuses": [[], [], [], [], []], "tree": [[], [], []]}
    out.update(kw)
    return out


def build(slot, **kw):
    with contextlib.redirect_stdout(io.StringIO()) as log:
        res = ca.apply_civ(dat, civ_def(**kw), target_slot=slot)
    return res, log.getvalue()


def custom_cmds(res):
    ci = res["civ_index"]
    return [c for t in dat.techs if t.civ == ci and t.name == "C-Bonus, Custom"
            for c in dat.effects[t.effect_id].effect_commands]


units = dat.civs[1].units
knight_line = {38, 283, 569}                             # Knight, Cavalier, Paladin

res, _ = build(5, custom_bonuses=[card([G("cavalry"), LINE(38, "Knight")])])
cmds = custom_cmds(res)
by_id = [c for c in cmds if c.a in knight_line]
check("Cavalry + Knight line: the Knight line gets no per-unit HP command",
      not by_id, [(c.a, c.b, c.d) for c in by_id])
check("...because the class command already reaches it (class 12)",
      any(c.a == -1 and c.b == 12 and c.c == 0 for c in cmds))

res, _ = build(6, custom_bonuses=[card([G("archers"), G("cavalry_archers")])])
cmds = custom_cmds(res)
c36 = [c for c in cmds if c.a == -1 and c.b == 36 and c.c == 0]
check("Archers + Cavalry archers write class 36 once", len(c36) == 1, len(c36))

res, _ = build(7, custom_bonuses=[card([G("archers"), LINE(539, "Galley")],
                                       [{"attr": "range", "op": "add", "value": 1}])])
cmds = custom_cmds(res)
check("Archers + Galley line: the Galley line is reached by id (class 22 isn't an archer class)",
      {539, 21, 442} <= {int(c.a) for c in cmds}, sorted({int(c.a) for c in cmds}))
check("...and still one tech for the card", sum(1 for t in dat.techs if t.civ == res["civ_index"]
                                               and t.name == "C-Bonus, Custom") == 1)

# Team cards: into the team bonus effect, for allies too.
res, log = build(8, custom_team_bonuses=[
    card([G("barracks_units")], [{"attr": "hp", "op": "add", "value": 5}]),
    card([G("techs_blacksmith")], [{"attr": "tech_cost", "op": "mul", "value": -20}]),
])
tb = dat.effects[dat.civs[res["civ_index"]].team_bonus_id].effect_commands
ids = {int(c.a) for c in tb if c.c == 0}
check("a team card lands in the team bonus effect", bool(ids), log[-2000:])
check("team 'Barracks units' reach units this civ doesn't train (Eagle Warrior line)",
      {751, 752} & ids, sorted(ids))
check("a tech card picked as a team bonus is skipped with a reason",
      any("Tech bonuses can't be team bonuses" in w for w in res["warnings"]), res["warnings"])
check("apply_civ reports one team card applied",
      res["bonus_results"]["placed_cards"]["team"] == 1, res["bonus_results"]["placed_cards"])
check("the team line reads shortcodes as words too",
      ca.team_card_texts(civ_def(custom_team_bonuses=[tok])) == ["Archers -10% gold; +1 range, [nope]"])
check("team_card_texts lists only what the build applies",
      ca.team_card_texts(civ_def(custom_team_bonuses=[
          card([G("barracks_units")], [{"attr": "hp", "op": "add", "value": 5}]),
          card([G("techs_blacksmith")], [{"attr": "tech_cost", "op": "mul", "value": -20}]),
      ])) == ["Barracks units: +5 HP"])

big = card([G("buildings"), G("military"), G("ships"), G("siege"), G("trade"), G("gunpowder"),
            G("camels"), G("elephants")],
           [{"attr": "melee_armor", "op": "add", "value": 300}, {"attr": "pierce_armor", "op": "add", "value": 300},
            {"attr": "los", "op": "add", "value": 1}, {"attr": "hp", "op": "mul", "value": 5},
            {"attr": "cost", "op": "mul", "value": -5}, {"attr": "regen", "op": "add", "value": 5}])
res, _ = build(9, custom_team_bonuses=[big])
tb = dat.effects[dat.civs[res["civ_index"]].team_bonus_id].effect_commands
n = len(cb.card_commands(cb.normalize([big])[0], *ca._custom_bonus_resolver(dat, res["civ_index"], civ_def(), team=True)))
check("a team card too big for the shared effect is skipped, not written",
      n > ca._EFFECT_COMMAND_SOFT_LIMIT and len(tb) <= ca._EFFECT_COMMAND_SOFT_LIMIT
      and any("can't split" in w for w in res["warnings"]), (n, len(tb), res["warnings"]))

# UT cards: into the UT's own effect; a UT of cards alone still gets its tech.
ut_card = card([G("archers"), LINE(539, "Galley")], [{"attr": "range", "op": "add", "value": 1}])
res, log = build(10, castle_ut={"mode": "custom", "effects": [], "custom_bonuses": [ut_card]})
tid = res["castle_ut_tech_id"]
check("a Custom UT made only of library cards gets a tech", tid is not None, log[-1500:])
if tid is not None:
    eff = dat.effects[dat.techs[tid].effect_id].effect_commands
    check("...whose effect carries the card's commands",
          any(c.a == -1 and c.b == 0 and c.c == 12 for c in eff) and 539 in {int(c.a) for c in eff},
          [(c.type, c.a, c.b, c.c) for c in eff][:10])
    check("...and no auto-fire custom tech was made for it",
          not any(t.civ == res["civ_index"] and t.name == "C-Bonus, Custom" for t in dat.techs))

res, _ = build(11, castle_ut={"mode": "custom", "effects": [{"id": 1, "multiplier": 1}],
                              "custom_bonuses": [ut_card]})
tid = res["castle_ut_tech_id"]
eff = dat.effects[dat.techs[tid].effect_id].effect_commands
src = dat.effects[dat.techs[ca._KM_CASTLE_UT_TECHS[1]].effect_id].effect_commands
check("catalog effects and library cards stack in one UT",
      len(eff) >= len(src) + 1 and 539 in {int(c.a) for c in eff}, (len(eff), len(src)))

res, _ = build(12, castle_ut={"mode": "vanilla", "effects": [{"id": 1, "multiplier": 1}],
                              "custom_bonuses": [ut_card]})
eff = dat.effects[dat.techs[res["castle_ut_tech_id"]].effect_id].effect_commands
check("Pick Vanilla ignores cards left over from Build Custom", 539 not in {int(c.a) for c in eff})

res, _ = build(13, castle_ut={"mode": "custom", "effects": [], "custom_bonuses": [civ]})
check("a civilization card in a UT is skipped with a reason",
      any("can't go in a unique tech" in w for w in res["warnings"]), res["warnings"])

# One card, one home (card_homes): the first use wins — civ, team, Castle UT,
# Imperial UT — and a card listed twice in one home counts once.
A = {**card([G("archers")], [{"attr": "hp", "op": "add", "value": 5}]), "id": "aaaaaaaa"}
B = {**card([G("cavalry")], [{"attr": "hp", "op": "add", "value": 5}]), "id": "bbbbbbbb"}
T = {**techs, "id": "tttttttt"}
homes = ca.card_homes(civ_def(custom_bonuses=[A, A], custom_team_bonuses=[A, B, T],
                              castle_ut={"mode": "custom", "custom_bonuses": [B]},
                              imperial_ut={"mode": "custom", "custom_bonuses": [T]}))
ids = lambda cs: [c["id"] for c in cs]                            # noqa: E731
check("a card used twice is kept in its first home only",
      ids(homes["civ"]) == ["aaaaaaaa"] and ids(homes["team"]) == ["bbbbbbbb"]
      and ids(homes["castle_ut"]) == [] and ids(homes["imperial_ut"]) == ["tttttttt"],
      {h: ids(homes[h]) for h in ("civ", "team", "castle_ut", "imperial_ut")})
check("...and each repeat is reported with where it was kept",
      sorted((h, c["id"], k) for h, c, k in homes["duplicates"])
      == [("castle_ut", "bbbbbbbb", "team"), ("civ", "aaaaaaaa", "civ"), ("team", "aaaaaaaa", "civ")],
      homes["duplicates"])
check("a card refused in one home doesn't use up its slot (tech as team bonus -> still the Imperial UT's)",
      ("team", "tttttttt") in {(h, c["id"]) for h, c, _ in homes["refused"]})
noid = card([G("monks")], [{"attr": "hp", "op": "add", "value": 5}])
homes = ca.card_homes(civ_def(custom_bonuses=[noid], custom_team_bonuses=[dict(noid)]))
check("without a library id, identical content is the same card",
      len(homes["civ"]) == 1 and homes["team"] == [] and len(homes["duplicates"]) == 1)

res, _ = build(14, custom_bonuses=[A], custom_team_bonuses=[A],
               castle_ut={"mode": "custom", "effects": [], "custom_bonuses": [A]})
check("the build applies a duplicated card once",
      res["bonus_results"]["custom_applied"] == 1
      and res["bonus_results"]["placed_cards"] == {"team": 0, "castle_ut": 0, "imperial_ut": 0},
      res["bonus_results"]["placed_cards"])
check("...says so",
      sum("already in your civ bonuses" in w for w in res["warnings"]) == 2, res["warnings"])
check("...and makes no empty UT for a card that was only a duplicate", res["castle_ut_tech_id"] is None,
      res["castle_ut_tech_id"])
check("the team line on the civ screen leaves the duplicate out",
      ca.team_card_texts(civ_def(custom_bonuses=[A], custom_team_bonuses=[A, B])) == ["Cavalry: +5 HP"])

# The wizard door carries both lists to apply_civ.
cd = wizard_build._draft_to_civ_def({
    "custom_team_bonuses": [two],
    "castle_ut": {"mode": "custom", "effects": [{"id": 1, "multiplier": 1}], "custom_bonuses": [techs]},
})
check("wizard civ_def carries team cards", ca.get_team_cards(cd) == [two])
check("wizard civ_def carries Castle UT cards", ca.get_ut_cards(cd, "castle_ut") == [techs])
check("...without changing the UT's catalog entries", ca.get_ut_entries(cd, "castle_ut") == [[1, 1, "castle"]],
      ca.get_ut_entries(cd, "castle_ut"))

print()
if failures:
    print(f"{failures} check(s) FAILED")
    sys.exit(1)
print("All checks passed.")
