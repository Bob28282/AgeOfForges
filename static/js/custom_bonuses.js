/**
 * custom_bonuses.js — the custom civ bonus library, shared by two pages:
 *
 *   /builder/custom-bonuses  the library: add, edit, delete, import, export
 *   /builder (wizard)        step 3 picks library cards into the civ
 *
 * A card is one or more targets plus a list of effects, in exactly the shape
 * custom_bonus.py normalises:
 *   {id, targets: [{type:"group", id:"cavalry"} | {type:"unit", id, name, kind}, ...],
 *    effects: [{attr, op, value, resource?}], text}
 * Cards from before #76 have a single `target`; cbTargets() reads either.
 *
 * Groups and attributes come from /api/builder/custom-bonus/catalog so the two
 * sides can't drift; cbCardText mirrors custom_bonus.card_text.
 */

let _cbCatalog = null;

async function cbLoadCatalog() {
  if (_cbCatalog) return _cbCatalog;
  try {
    _cbCatalog = await (await fetch("/api/builder/custom-bonus/catalog")).json();
    if (_cbCatalog.allowed_pending) _cbRefreshAllowed(1);
  } catch (e) {
    console.warn("Could not load custom bonus catalog:", e);
  }
  return _cbCatalog;
}

// The per-target effect lists, the unit-line tiles and the "top" flags need the
// game DAT, which may still be loading on a first visit; until they arrive
// every effect of the right kind is offered and only single units are listed.
function _cbRefreshAllowed(attempt) {
  if (attempt > 10) return;
  setTimeout(async () => {
    try {
      const c = await (await fetch("/api/builder/custom-bonus/catalog")).json();
      if (!c.allowed) return _cbRefreshAllowed(attempt + 1);
      // Everything that needed the DAT: effect lists, line tiles, top flags.
      _cbCatalog.allowed = c.allowed;
      _cbCatalog.lines = c.lines;
      _cbCatalog.units = c.units;
      delete _cbCatalog.allowed_pending;
      if (_cbWork) { _cbRenderPicker(); _cbRenderEffects(); }
    } catch (e) { /* keep offering everything */ }
  }, 3000);
}

async function cbLoadLibrary() {
  try {
    return (await (await fetch("/api/custom-bonuses")).json()).bonuses || [];
  } catch (e) {
    console.warn("Could not load custom bonus library:", e);
    return [];
  }
}

const _CB_FASTER = { attack_speed: "attack", train_speed: "train", build_speed: "build", research_speed: "research" };
const _CB_COST    = new Set(["cost", "tech_cost"]);    // attrs with a resource picker

function _cbAttr(id)  { return (_cbCatalog?.attrs || []).find(a => a.id === id); }
function _cbGroup(id) { return (_cbCatalog?.groups || []).find(g => g.id === id); }
function _cbJob(id)   { return (_cbCatalog?.jobs   || []).find(j => j.id === id); }

function cbEsc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// A card's targets, whichever shape it was saved in.
function cbTargets(card) {
  if (Array.isArray(card?.targets)) return card.targets;
  return card?.target ? [card.target] : [];
}

function _cbTargetKind(t) {
  if (!t) return "unit";
  if (t.type === "group") return _cbGroup(t.id)?.kind || "unit";
  if (t.type === "job") return "job";
  if (t.type === "tech") return "tech";
  if (t.type === "civ") return "civ";
  return t.kind === "building" ? "building" : "unit";
}

function _cbTargetLabel(t) {
  if (!t) return "";
  if (t.type === "group") return _cbGroup(t.id)?.label || t.id;
  if (t.type === "job") return _cbJob(t.id)?.label || t.id;
  if (t.type === "tech") return t.name || `Tech ${t.id}`;
  if (t.type === "civ") return "Civilization";
  return t.name || `Unit ${t.id}`;
}

// Which targets can share a card (mirrors custom_bonus.target_family): units,
// buildings and villager jobs mix; techs only with techs; Civilization alone.
function _cbFamily(t) {
  const k = _cbTargetKind(t);
  return k === "tech" || k === "civ" ? k : "stats";
}

function _cbJoin(parts) {
  return parts.length < 2 ? (parts[0] || "") : `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}`;
}

// Why a card can't be a team bonus / part of a unique tech, or "" — mirrors
// custom_bonus.team_problem / ut_problem, which the build enforces.
function cbTeamProblem(card) {
  const ts = cbTargets(card);
  const fam = ts.length ? _cbFamily(ts[0]) : "stats";
  if (fam === "tech") return "Tech bonuses can't be team bonuses — allies research their own copies of some techs.";
  if (fam === "civ") return "Civilization bonuses can't be team bonuses — they're built as one-off events for this civ.";
  if (ts.some(t => t.type === "group" && t.id === "unique_unit")) return "\"Unique unit\" means this civ's unique unit, which allies don't train.";
  if ((card.effects || []).some(e => e.attr === "pop_space")) return "Population space only works on this civ's own buildings.";
  return "";
}

function cbUtProblem(card) {
  const ts = cbTargets(card);
  if (ts.length && _cbFamily(ts[0]) === "civ") return "Civilization bonuses can't go in a unique tech — they're tied to the start of the game or an age.";
  return "";
}

// What a card is about, as its text says it (mirrors custom_bonus.card_text):
// a unit with no scope is its whole line ("Militia line" — every card before
// #63 meant this); scope "up" is the unit and its upgrades ("Long Swordsman
// and up"), or just the unit when nothing comes after it ("Champion").
function _cbSubject(t) {
  const label = _cbTargetLabel(t);
  if (t?.type !== "unit" || t.kind === "building") return label;
  if (t.scope !== "up") return `${label} line`;
  return t.top ? label : `${label} and up`;
}

function _cbNum(v) { return Number.isInteger(v) ? String(v) : String(+v.toFixed(3)); }

function _cbEffectText(e, target) {
  const a = _cbAttr(e.attr);
  if (a?.novalue) return a.label;                      // "free and instant"
  const v = Number(e.value);
  if (!a || !v) return "";
  if (e.attr === "tech_cost") {
    const res = e.resource || "all";
    return `${v > 0 ? "+" : "-"}${_cbNum(Math.abs(v))}${e.op === "mul" ? "%" : ""} ${res === "all" ? "cost" : res + " cost"}`;
  }
  const sign = v > 0 ? "+" : "-";
  const num  = _cbNum(Math.abs(v));
  if (e.attr === "cost") {
    const res = e.resource || "all";
    return `${sign}${num}% ${res === "all" ? "cost" : res + " cost"}`;
  }
  if (_CB_FASTER[e.attr]) return `${_CB_FASTER[e.attr]} ${num}% ${v > 0 ? "faster" : "slower"}`;
  // A job names its work rate: "gather rate", "build speed", "repair speed".
  const label = e.attr === "work_rate" && target?.type === "job" ? (_cbJob(target.id)?.work || a.label) : a.label;
  if (e.op === "mul") return `${sign}${num}% ${label}`;
  return `${sign}${num} ${label}`;
}

// Shortcodes in the player's own text ("[gold]") — the table is
// custom_bonus.TEXT_TOKENS, served in the catalog, so the browser and the build
// can't disagree.  cbGameText is what the game shows ("gold"); _cbTokensHtml
// draws the icon on a card.  An unknown "[word]" stays as typed on both.
function cbGameText(text) {
  const tokens = _cbCatalog?.tokens || {};
  return String(text).replace(/\[(\w+)\]/g, (m, tok) => tokens[tok]?.word ?? m);
}

function _cbTokensHtml(escaped) {
  const tokens = _cbCatalog?.tokens || {};
  return escaped.replace(/\[(\w+)\]/g, (m, tok) => tokens[tok]
    ? `<img class="resource-icon icon-${tok}" src="${tokens[tok].icon}" alt="${cbEsc(tokens[tok].word)}" title="${cbEsc(tokens[tok].word)}">`
    : m);
}

function cbCardText(card) {
  if (card.text) return cbGameText(card.text);
  const targets = cbTargets(card);
  if (targets[0]?.type === "civ") {
    // Mirrors custom_bonus._civ_effect_text: "+25 population limit in the
    // Imperial Age", "+100 stone at the start", "+200 wood on reaching the
    // Castle Age" (#65).
    const age = (_cbCatalog?.civ_ages || []).find(a => a.id === targets[0].age);
    return (card.effects || []).filter(e => e.value != null && !isNaN(e.value) && e.value !== 0).map(e => {
      const num = `${e.value > 0 ? "+" : "-"}${_cbNum(Math.abs(e.value))}`;
      if (e.attr === "resources") {
        const what = e.resource === "each" ? "of each resource" : (e.resource || "gold");
        return `${num} ${what} ${age ? `on reaching the ${age.label}` : "at the start"}`;
      }
      if (e.attr === "convert_time") {
        const n = Math.abs(e.value);
        return `Monks convert ${_cbNum(n)} second${n !== 1 ? "s" : ""} ${e.value < 0 ? "faster" : "slower"}`
             + (age ? ` from the ${age.label}` : "");
      }
      return `${num} ${_cbAttr(e.attr)?.label || e.attr}` + (age ? ` in the ${age.label}` : "");
    }).join(", ");
  }
  const subject = _cbJoin(targets.map(_cbSubject));
  // A job's own word for work rate ("gather rate") only when it's the only target.
  const named = targets.length === 1 ? targets[0] : null;
  const parts = (card.effects || []).map(e => _cbEffectText(e, named)).filter(Boolean);
  return parts.length ? `${subject}: ${parts.join(", ")}` : subject;
}

// Content equality, ignoring the id — "has the library card changed since this
// civ copied it?"
function cbSameCard(a, b) {
  const strip = c => JSON.stringify({ targets: cbTargets(c), effects: c.effects, text: c.text || "" });
  return strip(a) === strip(b);
}

// ── Cards ────────────────────────────────────────────────────────────────────
// A custom bonus drawn as a wizard bonus card, so it reads as one of the
// game's own.  The vanilla cards GUESS their layout by parsing label text
// (builder.js _parseBonusCard); a custom card knows its target, attribute and
// value, so its layout is exact:
//   one effect, no player text   value card — heading "+20%", stat "HP",
//                                footer "Cavalry"
//   several effects, or text     stacked lines, one per effect (or per ";")
// Art comes from the targets (the composer's own tiles): one icon, or the
// first two side by side.  No multiplier: the player types the amount, and a
// multiplier on a MULTIPLY would compound (x3 on +20% is +72.8%, not +60%).
// The category follows the vanilla cards' first-match order (naval, monk,
// cost, economy, speed, combat, research, building) from the card's data.

const _CB_CATS = {
  naval: "fa-anchor", monk: "fa-cross", cost: "fa-arrow-down", economy: "fa-coins",
  speed: "fa-bolt", combat: "fa-shield-halved", research: "fa-flask",
  building: "fa-chess-rook", general: "fa-shield",
};
const _CB_NAVAL_GROUPS = new Set(["ships", "warships", "dock_units"]);
const _CB_ECO_GROUPS   = new Set(["villagers", "economic", "drop_off", "farms", "trade"]);
const _CB_COST_ATTRS   = new Set(["cost", "tech_cost", "free"]);
const _CB_SPEED_ATTRS  = new Set(["speed", "attack_speed", "train_speed", "build_speed",
                                  "research_speed", "work_rate", "instant"]);
const _CB_COMBAT_ATTRS = new Set(["hp", "melee_armor", "pierce_armor", "melee_attack", "pierce_attack",
                                  "range", "los", "min_range", "no_min_range", "blast_radius", "regen"]);
const _CB_DOCK = 45;

function _cbUnitEntry(id) { return (_cbCatalog?.units || []).find(u => u.id === id); }
function _cbLineEntry(id) { return (_cbCatalog?.lines || []).find(l => l.id === id); }

function _cbIsNaval(t) {
  if (t.type === "group") return _CB_NAVAL_GROUPS.has(t.id);
  if (t.type !== "unit") return false;
  if (t.kind === "building") return t.id === _CB_DOCK;
  return _cbLineEntry(t.id)?.building === _CB_DOCK || _cbUnitEntry(t.id)?.category === "dock";
}

function _cbIsEconomy(t) {
  return t.type === "job" || (t.type === "group" && _CB_ECO_GROUPS.has(t.id));
}

function cbCardCategory(card) {
  const ts = cbTargets(card);
  const fx = card.effects || [];
  const all = set => fx.length > 0 && fx.every(e => set.has(e.attr));
  const fam = ts.length ? _cbFamily(ts[0]) : "stats";
  if (fam === "civ") {
    if (fx.every(e => e.attr.startsWith("convert"))) return "monk";
    return fx.some(e => e.attr === "resources") ? "economy" : "general";
  }
  if (fam === "tech") {
    if (all(_CB_COST_ATTRS)) return "cost";
    if (all(_CB_SPEED_ATTRS)) return "speed";
    return "research";
  }
  if (ts.length && ts.every(_cbIsNaval)) return "naval";
  if (ts.length && ts.every(t => t.type === "group" && (t.id === "monks" || t.id === "churches"))) return "monk";
  if (all(_CB_COST_ATTRS)) return "cost";
  if (ts.length && ts.every(_cbIsEconomy)) return "economy";
  if (all(_CB_SPEED_ATTRS)) return "speed";
  if (fx.some(e => _CB_COMBAT_ATTRS.has(e.attr))) return "combat";
  if (ts.length && ts.every(t => _cbTargetKind(t) === "building")) return "building";
  return "general";
}

// A target's art: an image URL or a Font Awesome class.  Units, lines,
// buildings and techs need the DAT-backed half of the catalog; until it has
// loaded, they fall back to the wand.
function _cbTargetArt(t) {
  const c = _cbCatalog || {};
  if (t.type === "group") return _cbGroup(t.id)?.icon;
  if (t.type === "job")   return _cbJob(t.id)?.icon;
  if (t.type === "civ")   return "fa-landmark";
  if (t.type === "tech")  return (c.techs || []).find(x => x.id === t.id)?.icon;
  if (t.kind === "building") return (c.buildings || []).find(x => x.id === t.id)?.icon;
  return (t.scope !== "up" && _cbLineEntry(t.id)?.icon) || _cbUnitEntry(t.id)?.icon;
}

function _cbArtHtml(art, alt) {
  if (!art || art.startsWith("fa-")) {
    return `<span class="card-icon cb-card-icon--fa" aria-hidden="true"><i class="fa-solid ${art || "fa-wand-magic-sparkles"}"></i></span>`;
  }
  return `<img class="card-icon" src="${cbEsc(art)}" alt="${cbEsc(alt)}" onerror="this.style.visibility='hidden'">`;
}

// One effect as heading + stat, mirroring _cbEffectText's wording.
function _cbHeadline(e, target) {
  const a = _cbAttr(e.attr);
  if (!a) return { heading: "", stat: "" };
  if (a.novalue) {
    return { free: { heading: "Free", stat: "and instant" }, instant: { heading: "Instant", stat: "research" },
             no_min_range: { heading: "None", stat: "minimum range" } }[e.attr]
        || { heading: a.label, stat: "" };
  }
  const v = Number(e.value);
  const sign = v > 0 ? "+" : "-";
  const num = _cbNum(Math.abs(v));
  if (_CB_FASTER[e.attr]) return { heading: `${num}%`, stat: `${_CB_FASTER[e.attr]} ${v > 0 ? "faster" : "slower"}` };
  if (_CB_COST.has(e.attr)) {
    const res = e.resource || "all";
    const pct = e.attr === "cost" || e.op === "mul" ? "%" : "";
    return { heading: `${sign}${num}${pct}`, stat: res === "all" ? "cost" : `${res} cost` };
  }
  const label = e.attr === "work_rate" && target?.type === "job" ? (_cbJob(target.id)?.work || a.label) : a.label;
  return { heading: `${sign}${num}${e.op === "mul" ? "%" : ""}`, stat: label };
}

// The hover tooltip's text (tooltip.js): what the card does as the game will
// say it, then what each target covers — the composer's own hint, so "Galley
// line" spells out Galley, War Galley, Galleon — and why it's greyed out.
function _cbTipText(card, why) {
  const ts = cbTargets(card);
  const lines = [cbCardText(card)];
  for (const t of ts) {
    if (t.type === "civ") continue;              // its card text already says it all
    const hint = _cbTargetHint(t);
    if (hint) lines.push(ts.length > 1 ? `${_cbSubject(t)}: ${hint}` : hint);
  }
  if (why) lines.push(why);
  return lines.join("\n");
}

// The card's markup: the same structure and classes as a vanilla bonus card
// (builder.js _renderBonusCardInner), so it inherits every card style.
// opts: { selected, off, why, actions, attrs, extraClass } — `actions` is extra HTML under
// the footer; `attrs` extra attributes on the root element.
function cbCardHtml(card, opts = {}) {
  const targets = cbTargets(card);
  const cat  = cbCardCategory(card);
  const only = targets.length === 1 ? targets[0] : null;
  const art  = targets.slice(0, 2).map(t => _cbArtHtml(_cbTargetArt(t), _cbTargetLabel(t)));
  const icons = art.length > 1 ? `<div class="card-icon-row">${art.join("")}</div>` : (art[0] || "");
  const civ = targets[0]?.type === "civ";
  const footer = civ ? "Civilization" : _cbJoin(targets.map(_cbSubject));
  const fx = card.effects || [];

  let middle;
  if (!card.text && !civ && fx.length === 1) {
    const h = _cbHeadline(fx[0], only);
    middle = `<div class="card-heading">${cbEsc(h.heading)}</div><div class="card-stat">${cbEsc(h.stat)}</div>`;
  } else {
    // Player text splits on ";" like the vanilla desc cards; generated text is
    // one line per effect (a Civilization card's own phrasing, comma-joined).
    const lines = card.text ? card.text.split(";")
                : civ ? cbCardText(card).split(", ")
                : fx.map(e => _cbEffectText(e, only));
    middle = `<ul class="card-desc-lines">${lines.map(l => l.trim()).filter(Boolean)
      .map(l => `<li class="desc-line">${_cbTokensHtml(cbEsc(l))}</li>`).join("")}</ul>`;
  }
  const cls = ["bonus-card", "cb-card", card.text || civ || fx.length !== 1 ? "desc-bonus" : "",
               opts.selected ? "selected" : "", opts.off ? "cb-card--off" : "", opts.extraClass || ""]
    .filter(Boolean).join(" ");
  const label = `${cat.charAt(0).toUpperCase()}${cat.slice(1)}`;
  return `<div class="${cls}" data-cat="${cat}" style="--cat-color:var(--cat-${cat})"
      data-tip-title="${cbEsc(`${label} · Custom bonus`)}" data-tip="${cbEsc(_cbTipText(card, opts.why))}" ${opts.attrs || ""}>
    <div class="card-header"><div><i class="fa-solid ${_CB_CATS[cat]}"></i><span class="bonus-type">${label}</span></div>
      <img class="cb-card-badge" src="/static/gold-seal.png" alt="Custom bonus"></div>
    <div class="card-body">
      ${icons}
      ${middle}
      <div class="card-who"><span class="card-who-label">${cbEsc(footer)}</span></div>
      ${opts.why ? `<div class="cb-card-why">${cbEsc(opts.why)}</div>` : ""}
      ${opts.actions || ""}
    </div>
    <div class="card-shadow"></div><div class="top-corners"></div><div class="bottom-corners"></div>
  </div>`;
}

// ── Editor ───────────────────────────────────────────────────────────────────
// Drives the #cb-editor markup in custom_bonuses.html.  cbOpenEditor(card, onSave)
// edits a copy; onSave(card) receives the cleaned card and returns a promise.

let _cbWork   = null;
let _cbOnSave = null;

// The effects a card's targets can take: the ones EVERY target takes (#76), so
// Archers + Castles offers range but not movement speed.
function _cbAttrsForAll(targets) {
  if (!targets?.length) return _cbAttrsFor(null);
  const lists = targets.map(t => new Set(_cbAttrsFor(t).map(a => a.id)));
  return _cbAttrsFor(targets[0]).filter(a => lists.every(l => l.has(a.id)));
}

// The effects a target can take: its kind's, narrowed to the ones that change
// a stat some unit it reaches has (no garrison space on Villagers, no range on
// a Champion).  Techs and the per-civ "Unique unit" group are not narrowed.
function _cbAttrsFor(target) {
  const kind = _cbTargetKind(target);
  const all = (_cbCatalog?.attrs || []).filter(a => a.kinds.includes(kind));
  const key = !target ? null
    : target.type === "group" ? `group:${target.id}`
    : target.type === "job"   ? `job:${target.id}`
    : target.type !== "unit"  ? null
    : kind === "building"      ? `building:${target.id}`
    : target.scope === "up"    ? `unit:${target.id}`
    : _cbCatalog?.allowed?.[`line:${target.id}`] ? `line:${target.id}` : `unit:${target.id}`;
  const ok = key && _cbCatalog?.allowed?.[key];
  return ok ? all.filter(a => ok.includes(a.id)) : all;
}

// ── Target picker: Group | Unit | Villager | Building tabs over icon tiles ──
// Clicking a tile adds or removes it (#76).  Tiles that can't share a card with
// what's chosen (a tech beside units, anything beside Civilization) are greyed
// out until the choice is cleared.

let _cbTab      = "group";
let _cbCategory = "";        // Unit tab filter chip ("" = all)

// The Villager tab: everything at once, each job, and Fishing Ships — not a
// villager, but where someone looking for fishing bonuses will look.
const _CB_FISHING_SHIP = 13;

function _cbTabOf(targets) {
  const t = targets?.[0];
  if (!t) return _cbTab;
  if (t.type === "job") return "villager";
  if (t.type === "tech") return "tech";
  if (t.type === "civ") return "civ";
  if (t.type === "group") return _cbGroup(t.id)?.tab || "group";
  if (t.type === "unit" && t.id === _CB_FISHING_SHIP) return "villager";
  return t.kind === "building" ? "building" : "unit";
}

function _cbSameTarget(a, b) {
  return !!a && !!b && a.type === b.type && String(a.id) === String(b.id) && (a.kind || "") === (b.kind || "")
      && (a.scope || "") === (b.scope || "") && (a.age || "") === (b.age || "");
}

function _cbIcon(icon, label) {
  if (!icon) return `<span class="cb-tile-art cb-tile-art--none"><i class="fa-solid fa-question"></i></span>`;
  if (icon.startsWith("fa-")) return `<span class="cb-tile-art cb-tile-art--fa"><i class="fa-solid ${icon}"></i></span>`;
  return `<img class="cb-tile-art" src="${icon}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">`;
}

// Tiles for a tab, with { heading } entries between sections.  Groups carry
// their own tab and section (custom_bonus.GROUPS), so a new group lands in the
// right place without touching this.
function _cbTilesFor(tab) {
  const c = _cbCatalog;
  const groupTile = g => ({ target: { type: "group", id: g.id }, label: g.label, icon: g.icon });
  const sectioned = groups => {
    const out = [];
    let last = null;
    for (const g of groups) {
      if (g.section && g.section !== last) { out.push({ heading: g.section }); last = g.section; }
      out.push(groupTile(g));
    }
    return out;
  };
  if (tab === "group") return sectioned(c.groups.filter(g => g.tab === "group"));
  if (tab === "civ") {
    // Keep the age already chosen when the tile is clicked again.
    const cur = _cbWork?.targets?.[0];
    const age = cur?.type === "civ" ? cur.age : undefined;
    return [{ target: { type: "civ", id: "civ", ...(age ? { age } : {}) },
              label: "Whole civilization", icon: "fa-landmark" }];
  }
  if (tab === "villager") {
    const all  = c.groups.find(g => g.id === "villagers");
    const ship = c.units.find(u => u.id === _CB_FISHING_SHIP);
    return [
      { target: { type: "group", id: "villagers" }, label: "All villagers", icon: all?.icon },
      ...c.jobs.map(j => ({ target: { type: "job", id: j.id }, label: j.label, icon: j.icon })),
      ...(ship ? [{ target: { type: "unit", id: ship.id, name: ship.name, kind: "unit" },
                    label: "Fishing Ships", icon: ship.icon }] : []),
    ];
  }
  // Unit / Building: this tab's groups first (the civ's own UU; economic,
  // drop-off, ...), then the searchable list.  The search filters both.
  const q = (document.getElementById("cb-search").value || "").trim().toLowerCase();
  const hit = label => !q || label.toLowerCase().includes(q);
  const groups = c.groups.filter(g => g.tab === tab && hit(g.label) && !_cbCategory);
  const pool = ({ unit: c.units, building: c.buildings, tech: c.techs }[tab] || [])
    .filter(x => hit(x.name))
    .filter(x => !_cbCategory || x.category === _cbCategory)
    .map(x => ({ target: x.kind === "tech"
                   ? { type: "tech", id: x.id, name: x.name }
                   : x.kind === "unit"
                     // A single unit is "this unit and up" (#63); whole lines
                     // are the line tiles below.
                     ? { type: "unit", id: x.id, name: x.name, kind: "unit", scope: "up",
                         ...(x.top ? { top: true } : {}) }
                     : { type: "unit", id: x.id, name: x.name, kind: x.kind },
                 label: x.name, icon: x.icon }));
  // Unit lines, by building (#63): the whole line, alternates included.
  const lineTiles = [];
  if (tab === "unit") {
    let last = null;
    for (const ln of (c.lines || []).filter(l => (hit(l.name) || l.members.some(hit))
                                              && (!_cbCategory || l.category === _cbCategory))) {
      if (ln.building_name !== last) { lineTiles.push({ heading: `${ln.building_name} lines` }); last = ln.building_name; }
      lineTiles.push({ target: { type: "unit", id: ln.id, name: ln.name.replace(/ line$/, ""), kind: "unit" },
                       label: ln.name, icon: ln.icon });
    }
  }
  if (!groups.length && !lineTiles.length) return pool;
  const listHeading = { unit: "Single units (and their upgrades)", building: "Individual buildings", tech: "Individual techs" }[tab];
  // The Tech tab's groups carry their own sections (Ages, Researched at, ...).
  const head = tab === "tech" ? sectioned(groups)
             : groups.length ? [{ heading: tab === "unit" ? "Special" : "Groups" }, ...groups.map(groupTile)] : [];
  return [...head, ...lineTiles, ...(pool.length ? [{ heading: listHeading }, ...pool] : [])];
}

function _cbRenderPicker() {
  // The choice stays visible while browsing another tab.  Each target is a chip
  // that removes itself; Clear starts over (and is the way out of a family).
  const chosen = document.getElementById("cb-target-chosen");
  const targets = _cbWork.targets;
  chosen.innerHTML = targets.length
    ? targets.map((t, i) => `<span class="cb-chosen-chip"><i class="fa-solid fa-check me-1"></i>${cbEsc(_cbSubject(t))}`
        + `<button type="button" class="cb-chosen-x" data-i="${i}" title="Remove" aria-label="Remove ${cbEsc(_cbSubject(t))}"><i class="fa-solid fa-xmark"></i></button></span>`).join("")
      + (targets.length > 1 ? `<button type="button" class="btn btn-sm btn-link p-0 ms-1 cb-chosen-clear">Clear</button>` : "")
    : `<span class="text-muted fw-normal">— pick one or more below</span>`;
  chosen.querySelectorAll(".cb-chosen-x").forEach(b => b.addEventListener("click", () =>
    _cbToggleTarget(targets[parseInt(b.dataset.i, 10)])));
  chosen.querySelector(".cb-chosen-clear")?.addEventListener("click", () => {
    _cbWork.targets = [];
    _cbTargetsChanged();
  });
  const family = targets.length ? _cbFamily(targets[0]) : null;
  document.querySelectorAll(".cb-tab").forEach(b => {
    const on = b.dataset.tab === _cbTab;
    b.classList.toggle("active", on);
    b.setAttribute("aria-selected", on);
  });
  const searchable = ["unit", "building", "tech"].includes(_cbTab);
  document.getElementById("cb-picker-tools").classList.toggle("d-none", !searchable);
  document.getElementById("cb-search").placeholder =
    { unit: "Search units… e.g. knight", building: "Search buildings… e.g. tower",
      tech: "Search techs… e.g. forging" }[_cbTab] || "Search…";

  const chips = document.getElementById("cb-chips");
  // Only chips that would show something.
  const pool = { unit: _cbCatalog.units, tech: _cbCatalog.techs }[_cbTab] || [];
  const cats = ({ unit: _cbCatalog.unit_categories, tech: _cbCatalog.tech_categories }[_cbTab] || null)
    ?.filter(cat => pool.some(x => x.category === cat.id));
  chips.innerHTML = cats
    ? [{ id: "", label: "All" }, ...cats].map(cat =>
        `<button type="button" class="cb-chip${cat.id === _cbCategory ? " active" : ""}" data-cat="${cat.id}">${cbEsc(cat.label)}</button>`).join("")
    : "";
  chips.querySelectorAll(".cb-chip").forEach(b => b.addEventListener("click", () => {
    _cbCategory = b.dataset.cat;
    _cbRenderPicker();
  }));

  const tiles = _cbTilesFor(_cbTab);
  const grid  = document.getElementById("cb-tiles");
  grid.classList.toggle("cb-tiles--big", !searchable);
  grid.innerHTML = tiles.map((t, i) => {
    if (t.heading) return `<div class="cb-section">${cbEsc(t.heading)}</div>`;
    const on = targets.some(x => _cbSameTarget(t.target, x));
    // Civilization is one target on its own; anything else mixes within its family.
    const off = !on && family && (family !== _cbFamily(t.target) || family === "civ");
    const title = off ? `${t.label} — can't share a bonus with ${family === "civ" ? "the whole civilization" : family === "tech" ? "techs" : "units or buildings"}. Clear the choice first.` : t.label;
    return `<button type="button" class="cb-tile${on ? " selected" : ""}${off ? " cb-tile--off" : ""}" data-i="${i}" aria-pressed="${on}"${off ? " disabled" : ""} title="${cbEsc(title)}">
      ${_cbIcon(t.icon, t.label)}<span class="cb-tile-label">${cbEsc(t.label)}</span></button>`;
  }).join("") || `<div class="text-muted small fst-italic p-2">Nothing matches that search.</div>`;
  grid.querySelectorAll(".cb-tile").forEach(el => el.addEventListener("click", () =>
    _cbToggleTarget(tiles[parseInt(el.dataset.i, 10)].target)));
}

function _cbTargetHint(t) {
  if (!t) return "";
  if (t.type === "civ") {
    return "Population limit is added on top of the lobby's limit (200, 500…); there is no percentage, "
         + "since the lobby limit is a game setting the mod can't read. Resources are a one-time grant: "
         + "at the start (paid once a Town Center stands, so Nomad works) or on reaching the chosen age. "
         + "Only a start grant can be negative. Monk conversion time is in monk-seconds: "
         + "-1 makes your Monks convert faster (Inquisition); conversion resistance makes "
         + "enemy Monks slower against your units (Faith gives +4).";
  }
  if (t.type === "group") {
    return {
      cavalry:       "Includes cavalry archers and mounted gunpowder, just like the game's definition.",
      archers:       "Foot archers, cavalry archers and hand cannoneers — the units Archery armor upgrades cover.",
      foot_soldiers: "Infantry and foot archers.",
      villagers:     "Every villager, whatever job it is doing.",
      buildings:     "Every building, including walls, towers and farms — as the game's building HP bonuses do.",
      gunpowder:     "Every gunpowder unit, unique ones included.",
      military:      "Land military: infantry, archers, cavalry and Petards. Not siege or ships, like the game's definition.",
      unique_unit:   "Whatever unique unit the civ using this card has, base and elite — resolved when the mod is built.",
      drop_off:      "Town Center, Mill, Lumber Camp, Mining Camp, Dock, Settlement, Folwark and Mule Cart.",
      economic:      "The drop-off sites plus Market, Feitoria and Caravanserai.",
      military_buildings: "Barracks, Archery Range, Stable, Siege Workshop and Dock.",
      defensive:     "Every tower (Donjon and Bombard Tower included), Castle and Krepost.",
    }[t.id] || (_cbGroup(t.id)?.section === "Trained at"
      ? "Whatever this civ trains there, unique and regional units included — resolved when the mod is built."
      : "");
  }
  if (t.type === "tech" || _cbGroup(t.id)?.kind === "tech") {
    const g = _cbGroup(t.id);
    if (g?.id === "unique_techs") return "This civ's Castle and Imperial unique techs — resolved when the mod is built.";
    if (g?.section === "Researched at") return "Every tech this civ researches there, resolved when the mod is built. Age advances are separate.";
    if (g?.id === "set_farm") return "Horse Collar, Heavy Plow and Crop Rotation — or their Pasture replacements on a Pasture civ.";
    return "Flat cost changes only touch resources the tech already costs, and never go below zero. " +
           "Free means no cost and no research time, as the game's own free techs do.";
  }
  if (t.type === "job") {
    return "Applies only while a villager does this job. HP, cost and train time aren't offered here: " +
           "HP carries over when a villager changes job, and only the base Villager is ever trained.";
  }
  if (t.kind === "building") {
    return t.id === 45
      ? "Applies to every Dock, including the Malay Harbor it upgrades into."
      : "Applies to every age version of this building.";
  }
  if (t.scope === "up") {
    return t.top ? "Applies to this unit (and its alternate forms) — nothing upgrades from it."
                 : "Applies to this unit and every upgrade after it, not the ones before — e.g. Long Swordsman covers Two-Handed Swordsman, Champion and Legionary, but not Militia.";
  }
  const line = (_cbCatalog?.lines || []).find(l => String(l.id) === String(t.id));
  return line ? `Covers ${line.members.join(", ")} — whichever this civ has.`
              : "Applies to the whole upgrade line and any alternate forms — e.g. Knight also covers Cavalier and Paladin.";
}

function _cbToggleTarget(target) {
  const at = _cbWork.targets.findIndex(x => _cbSameTarget(x, target));
  if (at >= 0) _cbWork.targets.splice(at, 1);
  else if (target.type === "civ") _cbWork.targets = [target];
  else _cbWork.targets.push(target);
  _cbLastTarget = at >= 0 ? _cbWork.targets.at(-1) || null : target;
  _cbTargetsChanged();
}

function _cbTargetsChanged() {
  _cbShowHint();
  // Drop effects the targets can't all take (movement speed on a building, HP
  // on a villager job) — the server enforces the same list.
  const ok = new Set(_cbAttrsForAll(_cbWork.targets).map(a => a.id));
  _cbWork.effects = _cbWork.effects.filter(e => ok.has(e.attr));
  if (!_cbWork.effects.length && _cbWork.targets.length) _cbWork.effects.push(_cbNewEffect());
  _cbError("");
  _cbRenderPicker();
  _cbRenderEffects();
}

// The hint describes the target just picked; with several, it also says why
// some effects are missing.
let _cbLastTarget = null;
function _cbShowHint() {
  const ts = _cbWork.targets;
  const t = ts.find(x => _cbSameTarget(x, _cbLastTarget || {})) || ts.at(-1);
  const many = ts.length > 1
    ? " With several targets, only the effects every one of them can take are offered, and a unit two targets share gets the bonus once."
    : "";
  document.getElementById("cb-target-hint").textContent = (t ? _cbTargetHint(t) : "") + many;
}

function _cbRenderEffects() {
  const wrap  = document.getElementById("cb-effects");
  // A saved card keeps an effect the target no longer offers, so editing it
  // never swaps that effect for another one silently.
  const offered = _cbAttrsForAll(_cbWork.targets);
  const kept = _cbWork.effects.map(e => e.attr)
    .filter(id => !offered.some(a => a.id === id)).map(_cbAttr).filter(Boolean);
  const attrs = [...offered, ...kept];
  wrap.innerHTML = _cbWork.effects.map((e, i) => {
    const a = _cbAttr(e.attr);
    const only = _cbWork.targets.length === 1 ? _cbWork.targets[0] : null;
    const job = only?.type === "job" ? _cbJob(only.id) : null;
    const nameOf = x => (x.id === "work_rate" && job) ? job.work : x.label;   // "build speed"
    const attrOpts = attrs.map(x => {
      const n = nameOf(x);
      return `<option value="${x.id}"${x.id === e.attr ? " selected" : ""}>${cbEsc(n.charAt(0).toUpperCase() + n.slice(1))}</option>`;
    }).join("");
    const unitLabel = op => op === "add" ? "flat" : (_CB_FASTER[e.attr] ? "% faster" : "%");
    if (a?.novalue) {
      // Free / instant take no amount.
      return `<div class="cb-effect" data-idx="${i}">
        <select class="form-select form-select-sm cb-attr">${attrOpts}</select>
        <span class="cb-op-fixed small text-muted">${e.attr === "free" ? "no cost, no wait" : "no wait"}</span>
        <button type="button" class="btn btn-sm btn-link text-danger cb-effect-remove" title="Remove effect"><i class="fa-solid fa-xmark"></i></button>
      </div>`;
    }
    const opCtl = a && a.ops.length > 1
      ? `<select class="form-select form-select-sm cb-op">${a.ops.map(op =>
          `<option value="${op}"${op === e.op ? " selected" : ""}>${unitLabel(op)}</option>`).join("")}</select>`
      : `<span class="cb-op-fixed small text-muted">${unitLabel(e.op)}</span>`;
    const resCtl = e.attr === "resources"
      ? `<select class="form-select form-select-sm cb-res">${(_cbCatalog.civ_resources || []).map(r =>
          `<option value="${r}"${r === (e.resource || "gold") ? " selected" : ""}>${r === "each" ? "each resource" : r}</option>`).join("")}</select>`
      : _CB_COST.has(e.attr)
      ? `<select class="form-select form-select-sm cb-res">${_cbCatalog.cost_resources.map(r =>
          `<option value="${r}"${r === (e.resource || "all") ? " selected" : ""}>${r === "all" ? "all resources" : r}</option>`).join("")}</select>`
      : "";
    return `<div class="cb-effect" data-idx="${i}">
      <select class="form-select form-select-sm cb-attr">${attrOpts}</select>
      <input type="number" ${a?.positive ? 'min="1" step="1"' : 'step="any"'} class="form-control form-control-sm cb-value" value="${e.value ?? ""}" placeholder="e.g. ${a?.positive ? 10 : e.op === "add" ? 2 : 20}">
      ${opCtl}
      ${resCtl}
      <button type="button" class="btn btn-sm btn-link text-danger cb-effect-remove" title="Remove effect"><i class="fa-solid fa-xmark"></i></button>
    </div>`;
  }).join("");

  // A Civilization card can wait for an age (#65), like vanilla's
  // "+10 population in Imperial Age".
  const civT = _cbWork.targets[0]?.type === "civ" ? _cbWork.targets[0] : null;
  if (civT) {
    const ages = [{ id: "", label: "the start (Dark Age)" }, ...(_cbCatalog.civ_ages || [])];
    wrap.insertAdjacentHTML("beforeend", `<div class="cb-age-row d-flex align-items-center gap-2 mt-1 small">
      <span class="text-muted">From</span>
      <select class="form-select form-select-sm cb-age" style="max-width:14rem">${ages.map(a =>
        `<option value="${a.id}"${String(a.id) === String(civT.age || "") ? " selected" : ""}>${cbEsc(a.label)}</option>`).join("")}</select>
    </div>`);
    wrap.querySelector(".cb-age").addEventListener("change", ev => {
      const v = parseInt(ev.target.value, 10);
      if (isNaN(v)) delete civT.age; else civT.age = v;
      _cbRenderPicker();
      _cbUpdatePreview();
    });
  }

  wrap.querySelectorAll(".cb-effect").forEach(row => {
    const idx = parseInt(row.dataset.idx, 10);
    const e   = _cbWork.effects[idx];
    row.querySelector(".cb-attr").addEventListener("change", ev => {
      e.attr = ev.target.value;
      const a = _cbAttr(e.attr);
      if (!a.ops.includes(e.op)) e.op = a.ops[0];
      if (e.attr === "resources") e.resource = e.resource && e.resource !== "all" ? e.resource : "gold";
      else if (!_CB_COST.has(e.attr)) delete e.resource;
      if (a.novalue) delete e.value;
      _cbRenderEffects();
    });
    row.querySelector(".cb-value")?.addEventListener("input", ev => {
      const n = parseFloat(ev.target.value);
      e.value = isNaN(n) ? null : n;
      _cbUpdatePreview();
    });
    row.querySelector(".cb-op")?.addEventListener("change", ev => { e.op = ev.target.value; _cbRenderEffects(); });
    row.querySelector(".cb-res")?.addEventListener("change", ev => { e.resource = ev.target.value; _cbUpdatePreview(); });
    row.querySelector(".cb-effect-remove").addEventListener("click", () => {
      _cbWork.effects.splice(idx, 1);
      _cbRenderEffects();
    });
  });
  _cbUpdatePreview();
}

function _cbNewEffect() {
  const used  = new Set(_cbWork.effects.map(e => e.attr));
  const attrs = _cbAttrsForAll(_cbWork.targets);
  const a = attrs.find(x => !used.has(x.id)) || attrs[0];
  return { attr: a.id, op: a.id === "hp" ? "mul" : a.ops[0], value: null,
           ...(a.id === "resources" ? { resource: "gold" } : {}) };
}

function _cbUpdatePreview() {
  const textEl = document.getElementById("cb-text");
  const work = { ..._cbWork, text: textEl.value.trim() };
  const out = cbCardText(work);
  document.getElementById("cb-preview-text").textContent = _cbWork.targets.length ? `• ${out}` : "—";
  textEl.placeholder = cbCardText({ ..._cbWork, text: "" });
  // The card as the wizard will show it — only the effects with an amount.
  const card = document.getElementById("cb-preview-card");
  if (card) {
    const effects = work.effects.filter(e => _cbAttr(e.attr)?.novalue || (e.value != null && !isNaN(e.value) && e.value !== 0));
    card.innerHTML = _cbWork.targets.length && effects.length
      ? cbCardHtml({ ...work, effects })
      : `<div class="text-muted small fst-italic">Pick a target and an amount to see the card.</div>`;
  }
}

async function cbOpenEditor(card, onSave) {
  if (!await cbLoadCatalog()) return;
  _cbOnSave = onSave;
  _cbWork = card ? JSON.parse(JSON.stringify(card)) : { effects: [], text: "" };
  _cbWork.targets = cbTargets(_cbWork);
  delete _cbWork.target;
  _cbLastTarget = null;
  _cbTab = _cbTabOf(_cbWork.targets);
  _cbCategory = "";
  document.getElementById("cb-search").value = "";
  _cbRenderPicker();
  _cbShowHint();
  document.getElementById("cb-text").value = _cbWork.text || "";
  const chips = document.getElementById("cb-tokens");
  if (chips) chips.innerHTML = Object.entries(_cbCatalog.tokens || {}).map(([tok, t]) =>
    `<button type="button" class="cb-token" data-token="${tok}" title="[${tok}] — reads “${cbEsc(t.word)}” in game">
       <img src="${t.icon}" alt="">${tok}</button>`).join("");
  document.getElementById("cb-error").classList.add("d-none");
  document.getElementById("cb-editor-title").textContent = card ? "Edit bonus" : "New bonus";
  if (!_cbWork.effects.length && _cbWork.targets.length) _cbWork.effects.push(_cbNewEffect());
  _cbRenderEffects();
  document.getElementById("cb-editor").classList.remove("d-none");
  document.getElementById("cb-new")?.classList.add("d-none");
  document.querySelector(".cb-tab.active")?.focus();
}

function cbCloseEditor() {
  _cbWork = null;
  document.getElementById("cb-editor").classList.add("d-none");
  document.getElementById("cb-new")?.classList.remove("d-none");
}

function _cbError(msg) {
  const err = document.getElementById("cb-error");
  err.textContent = msg;
  err.classList.toggle("d-none", !msg);
}

async function _cbSave() {
  if (!_cbWork.targets.length) return _cbError("Choose who this bonus applies to.");
  const effects = _cbWork.effects.filter(e =>
    _cbAttr(e.attr)?.novalue || (e.value !== null && e.value !== undefined && e.value !== 0 && !isNaN(e.value)));
  if (!effects.length) return _cbError("Add at least one effect with a non-zero amount.");
  const tooLow = effects.find(e => e.op === "mul" && e.value <= -100);
  if (tooLow) return _cbError(`${_cbAttr(tooLow.attr).label} can't go down by 100% or more.`);
  // The server drops these silently; say why instead.  A lower population
  // limit was tested in game and ignored (2026-10-11).
  const negative = effects.find(e => _cbAttr(e.attr)?.positive && e.value < 0);
  if (negative) {
    const label = _cbAttr(negative.attr).label;
    return _cbError(`${label.charAt(0).toUpperCase() + label.slice(1)} can only be raised` +
      (negative.attr === "pop_cap" ? " — the game ignores a lower limit." : "."));
  }
  const card = {
    targets: _cbWork.targets,
    effects: effects.map(e => {
      if (_cbAttr(e.attr)?.novalue) return { attr: e.attr, op: "set" };
      const out = { attr: e.attr, op: e.op, value: e.value };
      if (_CB_COST.has(e.attr)) out.resource = e.resource || "all";
      // Without this every one-time resources card saved as gold.
      if (e.attr === "resources") out.resource = e.resource || "gold";
      return out;
    }),
    text: document.getElementById("cb-text").value.trim(),
  };
  if (_cbWork.id) card.id = _cbWork.id;
  try {
    await _cbOnSave(card);
    cbCloseEditor();
  } catch (e) {
    _cbError(e.message || "Couldn't save that bonus.");
  }
}

function cbWireEditor() {
  document.getElementById("cb-cancel").addEventListener("click", cbCloseEditor);
  document.getElementById("cb-save").addEventListener("click", _cbSave);
  document.getElementById("cb-add-effect").addEventListener("click", () => {
    _cbWork.effects.push(_cbNewEffect());
    _cbRenderEffects();
  });
  document.getElementById("cb-text").addEventListener("input", _cbUpdatePreview);
  // Shortcode chips: insert "[gold]" at the cursor.
  document.getElementById("cb-tokens")?.addEventListener("click", ev => {
    const chip = ev.target.closest("[data-token]");
    if (!chip) return;
    const input = document.getElementById("cb-text");
    const at = input.selectionStart ?? input.value.length;
    const code = `[${chip.dataset.token}]`;
    input.value = (input.value.slice(0, at) + code + input.value.slice(input.selectionEnd ?? at)).slice(0, 160);
    input.focus();
    input.setSelectionRange(at + code.length, at + code.length);
    _cbUpdatePreview();
  });
  document.querySelectorAll(".cb-tab").forEach(b => b.addEventListener("click", () => {
    _cbTab = b.dataset.tab;
    _cbCategory = "";
    document.getElementById("cb-search").value = "";
    _cbRenderPicker();
  }));
  document.getElementById("cb-search").addEventListener("input", _cbRenderPicker);
}

// ── Server writes ────────────────────────────────────────────────────────────

async function cbSaveToLibrary(card) {
  const res  = await fetch("/api/custom-bonuses", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(card),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || "Couldn't save that bonus.");
  return body;
}

// ── Library page ─────────────────────────────────────────────────────────────

async function _cbLibraryPage() {
  const list   = document.getElementById("cb-library-list");
  const status = document.getElementById("cb-status");
  let library  = [];

  const say = (msg, kind = "muted") => {
    status.className = `small mb-3 text-${kind}`;
    status.textContent = msg;
  };

  async function refresh() {
    const res = await (await fetch("/api/custom-bonuses")).json().catch(() => ({}));
    library = res.bonuses || [];
    if (res.path) document.getElementById("cb-path").textContent = res.path;
    document.getElementById("cb-count").textContent =
      library.length ? `${library.length} bonus${library.length === 1 ? "" : "es"}` : "";
    document.getElementById("cb-export-all").classList.toggle("disabled", !library.length);
    if (!library.length) {
      list.innerHTML = `<div class="text-muted small fst-italic py-3">No custom bonuses yet — make one, or import a file someone shared with you.</div>`;
      return;
    }
    list.innerHTML = library.map(c => cbCardHtml(c, {
      attrs: `data-id="${cbEsc(c.id)}"`,
      actions: `<div class="cb-card-actions">
        <a class="btn btn-sm btn-link" href="/api/custom-bonuses/export?ids=${encodeURIComponent(c.id)}" title="Download to share" aria-label="Download to share"><i class="fa-solid fa-download"></i></a>
        <button type="button" class="btn btn-sm btn-link cb-edit" title="Edit" aria-label="Edit"><i class="fa-solid fa-pen"></i></button>
        <button type="button" class="btn btn-sm btn-link text-danger cb-remove" title="Delete" aria-label="Delete"><i class="fa-solid fa-trash"></i></button>
      </div>`,
    })).join("");
    list.querySelectorAll(".cb-card[data-id]").forEach(row => {
      const card = library.find(c => c.id === row.dataset.id);
      row.querySelector(".cb-edit").addEventListener("click", () => cbOpenEditor(card, async saved => {
        await cbSaveToLibrary(saved);
        say("Saved. Civs that already use this bonus keep their copy until you update them in the wizard.");
        await refresh();
      }));
      row.querySelector(".cb-remove").addEventListener("click", async () => {
        // Two-click delete rather than confirm() — browser dialogs block automation
        // and read as an error on this page's styling.
        const btn = row.querySelector(".cb-remove");
        if (!btn.dataset.armed) {
          btn.dataset.armed = "1";
          btn.innerHTML = `<span class="small">Delete?</span>`;
          setTimeout(() => { if (btn.isConnected) { delete btn.dataset.armed; btn.innerHTML = `<i class="fa-solid fa-trash"></i>`; } }, 3000);
          return;
        }
        await fetch(`/api/custom-bonuses/${encodeURIComponent(card.id)}`, { method: "DELETE" });
        say("Deleted. Civs that already use it keep their copy.");
        await refresh();
      });
    });
  }

  cbWireEditor();
  await cbLoadCatalog();
  document.getElementById("cb-new").addEventListener("click", () => cbOpenEditor(null, async card => {
    await cbSaveToLibrary(card);
    say("Saved to your library.", "success");
    await refresh();
  }));

  const fileInput = document.getElementById("cb-import-file");
  document.getElementById("cb-import").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const f = fileInput.files[0];
    fileInput.value = "";
    if (!f) return;
    const form = new FormData();
    form.append("file", f);
    const res  = await fetch("/api/custom-bonuses/import", { method: "POST", body: form });
    const body = await res.json();
    if (!res.ok) return say(body.error || "Import failed.", "danger");
    const bits = [`${body.added} added`];
    if (body.skipped) bits.push(`${body.skipped} already in your library`);
    if (body.invalid) bits.push(`${body.invalid} couldn't be read`);
    say(`Imported ${f.name}: ${bits.join(", ")}.`, body.added ? "success" : "muted");
    await refresh();
  });

  await refresh();
}

if (document.getElementById("cb-library-page")) _cbLibraryPage();
