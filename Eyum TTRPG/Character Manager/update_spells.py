#!/usr/bin/env python3
r"""
Spell Updater — comprehensive sync from handbook to spells.json.
Run from the Character Manager root directory:
    python3 update_spells.py

Parses 6.1 Spells.md (Leveled + Unique tables), compares against
data/spells.json, and writes output/updater_log.txt with full
before/after details. Preserves all generator custom keys.
"""

import json, re, os, sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HANDBOOK_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), '6.0 Magic', '6.1 Spells.md')
SPELLS_PATH = os.path.join(SCRIPT_DIR, 'data', 'spells.json')
LOG_PATH = os.path.join(SCRIPT_DIR, 'output', 'updater_log.txt')

# ── Condition definitions ───────────────────────────────────────
ALL_CONDITIONS = [
    'On Fire', 'Frozen', 'Soaked', 'Storm Shocked',
    'Hurting', 'Entangled', 'Suffocating', 'Prone', 'Grappled',
    'Lethargic', 'Unconscious', 'Surprised', 'Threatened',
    'Invisible', 'Intangible', 'Grounded', 'Restrained',
    'Difficult Terrain', 'Impassable Terrain',
    'Bleeding', 'Pierced', 'Burned', 'Frostbitten',
    'Shocked', 'Poisoned', 'Diseased', 'Hellfire',
    'Purged', 'Corrupt', 'Necrosis', 'Blinded',
    'Deafened', 'Paralyzed', 'Petrified', 'Stunned',
    'Gelled', 'Radiation', 'Sickened', 'Withered', 'Plagued',
    'DoT', 'GroundBurn',
    'Charmed', 'Frightened', 'Enraged', 'Demoralized',
    'Despair', 'Hypnotized', 'Mute', 'Blurred', 'Addicted',
    'Psychic Drain',
    'Cursed', 'Hexed', 'Silenced', 'Slow Death',
    'Slowed', 'Hasted', 'Blessed', 'Hexproof', 'Eldritch Curse',
    'Push', 'Pull', 'Heal', 'NoFlight', 'NoAdvantage',
    'Collision', 'Scaling', 'Marked by Light',
    'Frostburned', 'Taboo',
]

COND_ALIAS = {
    'Difficult Terrain': 'DifficultTerrain',
    'Impassable Terrain': 'DifficultTerrain',
}

# ── Custom keys preserved across runs ───────────────────────────
CUSTOM_KEYS = frozenset({'bap_attack', 'retaliation', 'storm_bolts'})

# Generator modeling overrides — applied AFTER handbook sync
DAMAGE_OVERRIDES = {
    # Whiteout Expanse: Soaked condition doubles damage per user instruction
    ('Glacial', 'Whiteout Expanse'): {'damage_dice': '4d12', 'damage_flat': 12},
    # Moving Glacier: assume pinned against wall + shatter explosion
    ('Glacial', 'Moving Glacier'): {'damage_dice': '6d12', 'damage_flat': 40},
    ('Glacial', 'Age of Ice'): {'save': 'con', 'save_half': True},
    # Fission Verdict: all 3 blast radii hit the target (tripled)
    ('Atomic', 'Fission Verdict'): {'damage_dice': '30d12', 'damage_flat': 600},
}

# ── Field lists ─────────────────────────────────────────────────
STAT_PREREQ_KEYS = ['int_required', 'con_required', 'str_required',
                    'dex_required', 'wis_required', 'cha_required']
BOOLEAN_FLAGS = ['aoe_cone', 'aoe_line', 'aoe_cube', 'aoe_self',
                 'concentration', 'attack_roll', 'save_half',
                 'costs_bonus_action', 'bap_attack']
AOE_FLAGS = {'aoe_cone': None, 'aoe_line': None, 'aoe_cube': None, 'aoe_self': None}

# ── Regex patterns ──────────────────────────────────────────────
# Primary damage: "takes 20 + 5d6", "deals 6d8 + 30", "taking 150 + 20d20"
DAMAGE_FLAT_DICE = re.compile(
    r'(?:take|deal|taking|dealing|taken|suffer)s?\s+'
    r'(?:an?\s+(?:additional\s+)?)?(?:up\s+to\s+)?'
    r'(?:(?P<flat>\d+(?:\.\d+)?)\s*\+\s*(?P<dice>\d+d\d+)'
    r'|(?P<dice2>\d+d\d+)\s*\+\s*(?P<flat2>\d+(?:\.\d+)?))',
    re.IGNORECASE)

DICE_ONLY = re.compile(
    r'(?:take|deal|taking|dealing|taken|suffer)s?\s+(?P<dice>\d+d\d+)',
    re.IGNORECASE)

SAVE_RE = re.compile(
    r'(?:must\s+)?make\s+a(?:n)?\s+'
    r'(Strength|Dexterity|Constitution|Wisdom|Intelligence|Charisma)'
    r'\s+save', re.IGNORECASE)

SAVE_MAP = {s.lower(): s[:3].lower() for s in
            ['Strength','Dexterity','Constitution','Wisdom','Intelligence','Charisma']}

AOE_RADIUS = re.compile(r'(\d+)\s*ft\s*radius', re.IGNORECASE)
AOE_CONE = re.compile(r'(\d+)\s*ft\s*cone', re.IGNORECASE)
AOE_LINE = re.compile(r'(\d+)\s*ft.*?line', re.IGNORECASE)
AOE_CUBE = re.compile(r'(\d+)\s*ft\s*cube', re.IGNORECASE)

RANGE_RE = re.compile(r'^([A-Za-z]+)?\s*(\d+)?(?:/(\d+))?(?:\s*\((.*)\))?$')

STAT_PREREQ = re.compile(r'>\s*(\d+)\s+(Str|Dex|Con|Wis|Int|Cha)\b', re.IGNORECASE)
AFFINITY_PREREQ = re.compile(r'>\s*(\d+)\s*([A-Z][\w\s/]+?)(?:\s*Affinity)?\s*(?:$|and|,)', re.IGNORECASE)

# ── Parsing ──────────────────────────────────────────────────────
def parse_handbook(filepath):
    with open(filepath, 'r') as f:
        text = f.read()
    spells = {}
    in_table = False
    for line in text.split('\n'):
        s = line.strip()
        if s.startswith('## Leveled Spells') or s.startswith('## Unique Spells') or s.startswith('## Healing Spells'):
            in_table = True; continue
        if s.startswith('## ') and not s.startswith('## Leveled') and not s.startswith('## Unique') and not s.startswith('## Healing'):
            in_table = False; continue
        if not in_table or not s.startswith('| '):
            continue
        cells = [c.strip() for c in s.split('|')]
        if len(cells) < 5: continue
        name = cells[1]
        if not name or name.startswith('---') or name == 'Spell Name': continue
        try: mana = int(cells[2])
        except ValueError: continue
        spells[name] = {
            'mana': mana,
            'range': cells[3] if len(cells) > 3 else '',
            'affinity': cells[4] if len(cells) > 4 else '',
            'desc': cells[5] if len(cells) > 5 else '',
            'upcast': cells[6] if len(cells) > 6 else '',
            'prereq': cells[7] if len(cells) > 7 else '',
        }
    return spells


def parse_range(rng_str):
    info = {}
    if not rng_str: return info
    r = rng_str.strip()
    if r.lower() == 'self': info['aoe_self'] = True; return info
    if r.lower() == 'touch': info['range'] = 'Touch'; return info
    if r.lower().startswith('self'):
        info['aoe_self'] = True
        m = re.search(r'\((.*)\)', r)
        if m: info = _merge(info, _parse_aoe_text(m.group(1)))
        return info
    if r.lower().startswith('touch'):
        info['range'] = 'Touch'
        m = re.search(r'\((.*)\)', r)
        if m: info = _merge(info, _parse_aoe_text(m.group(1)))
        return info
    m = re.match(r'^(\d+)(?:/(\d+))?(?:\s*\((.*)\))?$', r)
    if m:
        info['range'] = int(m.group(1))
        if m.group(2): info['range_max'] = int(m.group(2))
        if m.group(3): info = _merge(info, _parse_aoe_text(m.group(3)))
    else:
        info['range'] = r
    return info


def _parse_aoe_text(text):
    info = {}
    t = text.lower()
    m = AOE_RADIUS.search(t)
    if m: info['aoe_radius'] = int(m.group(1))
    m = AOE_CONE.search(t)
    if m: info['aoe_radius'] = int(m.group(1)); info['aoe_cone'] = True
    m = AOE_LINE.search(t)
    if m: info['aoe_line'] = True
    m = AOE_CUBE.search(t)
    if m: info['aoe_radius'] = int(m.group(1)); info['aoe_cube'] = True
    if 'sphere' in t:
        m = re.search(r'(\d+)\s*ft\s*sphere', t, re.IGNORECASE)
        if m: info['aoe_radius'] = max(int(m.group(1)), info.get('aoe_radius', 0))
    return info


def _merge(base, extra):
    for k, v in extra.items():
        if k == 'aoe_radius' and 'aoe_radius' in base and base['aoe_radius'] >= v: continue
        if k in ('aoe_cone','aoe_line','aoe_cube'): v = True
        base[k] = v
    return base


def extract_spell_info(desc, prereq_str, rng_str):
    info = {}

    # Damage
    m = DAMAGE_FLAT_DICE.search(desc)
    if m:
        info['damage_dice'] = m.group('dice') or m.group('dice2')
        info['damage_flat'] = int(float(m.group('flat') or m.group('flat2')))
    else:
        m = DICE_ONLY.search(desc)
        if m: info['damage_dice'] = m.group('dice')

    # Conditions with stack counts
    conditions = []
    for cond in ALL_CONDITIONS:
        name = cond
        # Check for X×N notation first (e.g., "Radiation x15", "Bleeding x3")
        p = re.search(rf'{re.escape(cond)}\s*[×xX]\s*(\d+)', desc)
        if p:
            cname = COND_ALIAS.get(cond, cond)
            conditions.append(f'{cname} x{p.group(1)}')
        elif re.search(rf'\b{re.escape(cond)}\b', desc, re.IGNORECASE):
            cname = COND_ALIAS.get(cond, cond)
            conditions.append(cname)
    if conditions:
        info['extra_effect'] = '+'.join(conditions)

    # Save
    m = SAVE_RE.search(desc)
    if m: info['save'] = SAVE_MAP.get(m.group(1).lower(), m.group(1)[:3].lower())
    if 'half damage' in desc.lower() or 'take half' in desc.lower():
        info['save_half'] = True

    # Attack roll vs save — if both appear, attack+save spells need both modeled
    if 'spell attack' in desc.lower():
        info['attack_roll'] = True

    # AoE from range
    range_info = parse_range(rng_str)
    for k, v in range_info.items():
        if k == 'range' and 'range' not in info: info['range'] = v
        elif k == 'range_max' and 'range_max' not in info: info['range_max'] = v
        elif k == 'aoe_radius':
            if 'aoe_radius' in info: info['aoe_radius'] = max(info['aoe_radius'], v)
            else: info['aoe_radius'] = v
        elif k in ('aoe_cone','aoe_line','aoe_cube','aoe_self'):
            info[k] = v

    # AoE from description (in case not in range column)
    for pat, key in [(AOE_RADIUS, 'aoe_radius'), (AOE_CONE, 'aoe_cone'),
                      (AOE_LINE, 'aoe_line'), (AOE_CUBE, 'aoe_cube')]:
        if key in info: continue
        m = pat.search(desc.lower())
        if m:
            if key == 'aoe_radius': info['aoe_radius'] = int(m.group(1))
            else: info[key] = True

    # Concentration
    if re.search(r'(?<!not )\brequires\s+[Cc]oncentration\b', desc):
        info['concentration'] = True

    # Bonus action cost
    if 'bonus action' in desc.lower() and 'cast' in desc.lower():
        info['costs_bonus_action'] = True

    # Prerequisites
    for m in STAT_PREREQ.finditer(prereq_str):
        val = int(m.group(1)) + 1
        stat = m.group(2).lower()
        info[f'{stat}_required'] = val
    # Also check description for stat prereqs
    for m in STAT_PREREQ.finditer(desc):
        val = int(m.group(1)) + 1
        stat = m.group(2).lower()
        key = f'{stat}_required'
        if key not in info: info[key] = val

    # Affinity required from prerequisite
    m = AFFINITY_PREREQ.search(prereq_str)
    if m:
        info['affinity_required'] = int(m.group(1)) + 1

    return info


def parse_upcast_chain(upcast_str):
    if not upcast_str or upcast_str.lower() in ('none', '-'): return {}
    if re.match(r'^[A-Z][a-zA-Z\s\-]+$', upcast_str.strip()):
        return {'upcast_to': upcast_str.strip()}
    return {'upcast_rule': upcast_str.strip()}


def fmt_val(v):
    if v is None: return '(none)'
    if isinstance(v, bool): return 'true' if v else 'false'
    return str(v)


# ── Main ─────────────────────────────────────────────────────────
def main():
    log_lines = []
    def log(s=''): log_lines.append(s)

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log(f"EYUM TTRPG — SPELL UPDATER LOG")
    log(f"Run at: {ts}")
    log("=" * 70)

    if not os.path.exists(HANDBOOK_PATH):
        print(f"ERROR: Handbook not found at {HANDBOOK_PATH}")
        _flush(log_lines); sys.exit(1)

    handbook = parse_handbook(HANDBOOK_PATH)
    log(f"Parsed {len(handbook)} spells from handbook")

    clear_affinity_markers()  # Reset change tracking for this run

    with open(SPELLS_PATH, 'r') as f:
        spells_json = json.load(f)

    # Index JSON spells by base name
    json_index = {}
    for aff_name, slist in spells_json.items():
        for s in slist:
            base = re.sub(r'\s*\(.*\)$', '', s['name']).strip()
            json_index.setdefault(base, []).append((aff_name, s, s['name']))

    # ── Update existing ──
    changed = []; unchanged = []; not_in_handbook = []

    for base_name, entries in json_index.items():
        if base_name not in handbook:
            for aff, s, orig_name in entries:
                not_in_handbook.append(f"  {orig_name} ({aff})")
            continue

        h = handbook[base_name]
        info = extract_spell_info(h['desc'], h['prereq'], h['range'])
        upcast = parse_upcast_chain(h['upcast'])

        for aff, s, orig_name in entries:
            custom = {k: s[k] for k in CUSTOM_KEYS if k in s}
            base = orig_name.split('(')[0].strip()
            # Fields that intentionally differ from handbook (generator overrides)
            skip_keys = set(DAMAGE_OVERRIDES.get((aff, base), {}).keys())
            diffs = []
            gameplay_diffs = 0  # count diffs that aren't from overrides

            # ── simple fields ──

            # mana
            if s.get('mana') != h['mana']:
                diffs.append(f"mana: {s['mana']} → {h['mana']}")
                s['mana'] = h['mana']

            # description
            if s.get('description', '') != h['desc']:
                diffs.append("description updated")
                s['description'] = h['desc']

            # upcast
            for uk, uv in upcast.items():
                if s.get(uk) != uv:
                    diffs.append(f"{uk}: {fmt_val(s.get(uk))} → {uv}")
                    s[uk] = uv

            # range
            if 'range' in info and s.get('range') != info['range']:
                diffs.append(f"range: {fmt_val(s.get('range'))} → {info['range']}")
                s['range'] = info['range']
            if 'range_max' in info and s.get('range_max') != info['range_max']:
                diffs.append(f"range_max: {fmt_val(s.get('range_max'))} → {info['range_max']}")
                s['range_max'] = info['range_max']

            # damage
            if 'damage_dice' in info and 'damage_dice' not in skip_keys:
                nd = info['damage_dice']
                od = s.get('damage_dice', '')
                if nd != od:
                    diffs.append(f"damage_dice: {od} → {nd}")
                    s['damage_dice'] = nd
            if 'damage_flat' in info and 'damage_flat' not in skip_keys:
                nf = info['damage_flat']
                of = s.get('damage_flat', 0)
                if nf != of:
                    diffs.append(f"damage_flat: {of} → {nf}")
                    s['damage_flat'] = nf

            # conditions
            ne = info.get('extra_effect') or ''
            oe = s.get('extra_effect') or ''
            if ne and ne != oe:
                diffs.append(f"extra_effect: {oe} → {ne}")
                s['extra_effect'] = ne

            # save
            if 'save' in info and 'save' not in skip_keys:
                if s.get('save') != info['save']:
                    diffs.append(f"save: {fmt_val(s.get('save'))} → {info['save']}")
                    s['save'] = info['save']
                    if s.get('attack_roll'): s['attack_roll'] = False; diffs.append("attack_roll→false (save)")

            # save_half handled via boolean flags below

            # AoE
            for k in ('aoe_radius','aoe_cone','aoe_line','aoe_cube','aoe_self'):
                v = info.get(k)
                if v is None: continue
                if k == 'aoe_radius':
                    if s.get(k) != v:
                        diffs.append(f"{k}: {s.get(k)} → {v}"); s[k] = v
                else:
                    if v and not s.get(k): diffs.append(f"{k}: false → true"); s[k] = True

            # boolean flags
            for flag in ('concentration','attack_roll','save_half','costs_bonus_action'):
                if info.get(flag) and not s.get(flag):
                    diffs.append(f"{flag}: false → true"); s[flag] = True

            # stat prerequisites
            for sk in STAT_PREREQ_KEYS:
                if sk in info and s.get(sk) != info[sk]:
                    diffs.append(f"{sk}: {fmt_val(s.get(sk))} → {info[sk]}")
                    s[sk] = info[sk]

            # affinity_required
            if 'affinity_required' in info:
                nv = info['affinity_required']
                if s.get('affinity_required') != nv:
                    diffs.append(f"affinity_required: {fmt_val(s.get('affinity_required'))} → {nv}")
                    s['affinity_required'] = nv

            # Restore custom keys
            for k, v in custom.items():
                if s.get(k) != v:
                    diffs.append(f"{k}: restored (custom flag)")
                    s[k] = v

            if diffs:
                changed.append((orig_name, aff, diffs))
                _mark_affinity(aff)
            else:
                unchanged.append(f"  {orig_name} ({aff})")

    # ── New spells ──
    all_bases = set()
    for entries in json_index.values():
        for _, _, on in entries:
            all_bases.add(re.sub(r'\s*\(.*\)$', '', on).strip())

    new_spells = {n: h for n, h in handbook.items() if n not in all_bases}

    print(f"\n{'='*60}")
    print(f"Spell Updater — {len(changed)} changed, {len(unchanged)} unchanged")
    print(f"{len(new_spells)} spells in handbook not in spells.json")
    print(f"{len(not_in_handbook)} spells in JSON not in handbook")
    print(f"{'='*60}")

    answer = 'n'
    if new_spells:
        print(f"\nNew spells in handbook NOT in spells.json:")
        for n in sorted(new_spells.keys()):
            print(f"  {n} ({new_spells[n]['affinity']})")
        answer = input(f"\nAdd these {len(new_spells)} spells to spells.json? [y/N]: ").strip().lower()
        if answer == 'y':
            added = []
            for hname, hdata in new_spells.items():
                info = extract_spell_info(hdata['desc'], hdata['prereq'], hdata['range'])
                up = parse_upcast_chain(hdata['upcast'])
                aff = hdata['affinity']
                if aff not in spells_json: spells_json[aff] = []
                e = {'name': hname, 'mana': hdata['mana'], 'description': hdata['desc'],
                     'damage_type': aff.lower()}
                if 'range' in info: e['range'] = info['range']
                if 'range_max' in info: e['range_max'] = info['range_max']
                for f in ('damage_dice','damage_flat','extra_effect','save',
                          'aoe_radius','affinity_required'):
                    if f in info: e[f] = info[f]
                for sk in STAT_PREREQ_KEYS:
                    if sk in info: e[sk] = info[sk]
                for f in BOOLEAN_FLAGS:
                    if info.get(f): e[f] = True
                for k, v in up.items(): e[k] = v
                spells_json[aff].append(e)
                added.append(hname)
                log(f"  + ADDED: {hname} ({aff}) mana={hdata['mana']}")
            for a in spells_json:
                spells_json[a].sort(key=lambda x: (x.get('affinity_required',0), x.get('mana',0)))
            print(f"  Added {len(added)} spells.")
        else:
            log("User chose NOT to add new spells.")
            for n in sorted(new_spells.keys()):
                log(f"  (skipped) {n} ({new_spells[n]['affinity']}): mana={new_spells[n]['mana']}")

    # ── Apply overrides ──
    for (aff_name, spell_name), overrides in DAMAGE_OVERRIDES.items():
        if aff_name not in spells_json: continue
        for s in spells_json[aff_name]:
            if s.get('name') == spell_name:
                for k, v in overrides.items():
                    if s.get(k) != v:
                        log(f"  OVERRIDE: {spell_name} ({aff_name}): {k}: {s.get(k)} → {v}")
                        s[k] = v
                break

    # Ensure every spell has damage_type
    for aff, slist in spells_json.items():
        aff_lower = aff.lower()
        for s in slist:
            if 'damage_type' not in s:
                s['damage_type'] = aff_lower
            if 'damage_dice' not in s and 'damage_formula' not in s:
                s['damage_type'] = aff_lower

    # ── Write JSON ──
    with open(SPELLS_PATH, 'w') as f:
        json.dump(spells_json, f, indent=2)
        f.write('\n')

    # ── Write log ──
    log(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    log(f"  Total handbook spells parsed: {len(handbook)}")
    log(f"  Changed:  {len(changed)}")
    log(f"  Unchanged: {len(unchanged)}")
    log(f"  Added:    {len(new_spells)}" if answer == 'y' else f"  Skipped:  {len(new_spells)} new spells")
    log(f"  Not in handbook: {len(not_in_handbook)}")

    if changed:
        log(f"\n{'─'*70}\nCHANGED SPELLS ({len(changed)})\n{'─'*70}")
        for name, aff, diffs in sorted(changed, key=lambda x: x[0].lower()):
            log(f"\n  {name} ({aff})")
            for d in diffs: log(f"      {d}")

    if unchanged:
        log(f"\n{'─'*70}\nUNCHANGED SPELLS ({len(unchanged)})\n{'─'*70}")
        for line in sorted(unchanged): log(line)

    if not_in_handbook:
        log(f"\n{'─'*70}\nNOT IN HANDBOOK ({len(not_in_handbook)})\n{'─'*70}")
        for line in sorted(not_in_handbook): log(line)

    log(f"\n{'='*70}\nEnd of log — {ts}")
    _flush(log_lines)
    print(f"\nDone. Full report: {LOG_PATH}")


def _flush(lines, path=LOG_PATH):
    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')


_AFFINITY_MARKER_PATH = os.path.join(SCRIPT_DIR, 'data', '.changed_affinities.json')


def _mark_affinity(aff_name):
    """Record that this affinity had a gameplay-relevant change."""
    import json as _json
    markers = {}
    if os.path.exists(_AFFINITY_MARKER_PATH):
        try:
            with open(_AFFINITY_MARKER_PATH) as _f:
                markers = _json.load(_f)
        except Exception:
            markers = {}
    markers[aff_name] = markers.get(aff_name, 0) + 1
    with open(_AFFINITY_MARKER_PATH, 'w') as _f:
        _json.dump(markers, _f)


def clear_affinity_markers():
    if os.path.exists(_AFFINITY_MARKER_PATH):
        os.remove(_AFFINITY_MARKER_PATH)


def get_changed_affinities():
    if not os.path.exists(_AFFINITY_MARKER_PATH):
        return set()
    import json as _json
    with open(_AFFINITY_MARKER_PATH) as _f:
        markers = _json.load(_f)
    return set(markers.keys())


if __name__ == '__main__':
    main()
