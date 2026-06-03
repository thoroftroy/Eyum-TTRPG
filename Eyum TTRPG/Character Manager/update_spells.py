#!/usr/bin/env python3
r"""
Spell Updater — full sync from handbook to spells.json.
Run from the Character Manager root directory:
    python3 update_spells.py

Parses 6.1 Spells.md (Leveled + Unique + Healing tables),
compares against data/spells.json, and writes output/updater_log.txt
with full before/after details for every field change.
"""

import json, re, os, sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HANDBOOK_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), '6.0 Magic', '6.1 Spells.md')
SPELLS_PATH = os.path.join(SCRIPT_DIR, 'data', 'spells.json')
LOG_PATH = os.path.join(SCRIPT_DIR, 'output', 'updater_log.txt')

# ── Condition definitions ───────────────────────────────────────
ALL_CONDITIONS = [
    # Environmental
    'On Fire', 'Frozen', 'Soaked', 'Storm Shocked',
    'Hurting', 'Entangled', 'Suffocating', 'Prone',
    'Grappled', 'Lethargic', 'Unconscious', 'Surprised',
    'Threatened', 'Invisible', 'Intangible', 'Grounded',
    'Restrained', 'Difficult Terrain',
    # Physical
    'Bleeding', 'Pierced', 'Burned', 'Frostbitten',
    'Shocked', 'Poisoned', 'Diseased', 'Hellfire',
    'Purged', 'Corrupt', 'Necrosis', 'Blinded',
    'Deafened', 'Paralyzed', 'Petrified', 'Stunned',
    'Gelled', 'Radiation', 'Sickened', 'Withered',
    'Plagued', 'DoT', 'GroundBurn',
    # Mental
    'Charmed', 'Frightened', 'Enraged',
    'Demoralized', 'Despair', 'Hypnotized',
    'Mute', 'Blurred', 'Addicted', 'Psychic Drain',
    # Magical
    'Cursed', 'Hexed', 'Silenced',
    'Slow Death', 'Slowed', 'Hasted',
    'Blessed', 'Hexproof', 'Eldritch Curse',
    # Other
    'Push', 'Pull', 'Heal',
    'NoFlight', 'NoAdvantage',
    'Collision', 'Scaling',
    'Marked by Light', 'Impassable Terrain',
]

# Map handbook names to JSON field names
COND_ALIAS = {
    'Difficult Terrain': 'DifficultTerrain',
    'Impassable Terrain': 'DifficultTerrain',
}

# ── Regex patterns ──────────────────────────────────────────────
DAMAGE_FLAT_DICE = re.compile(
    r'(?:take|deal)s?\s+(?:an?\s+additional\s+)?(?:up\s+to\s+)?'
    r'(?P<flat>\d+(?:\.\d+)?)\s*\+\s*(?P<dice>\d+d\d+)', re.IGNORECASE)

DICE_ONLY = re.compile(
    r'(?:take|deal)s?\s+(?P<dice>\d+d\d+)', re.IGNORECASE)

SAVE_RE = re.compile(
    r'(?:must\s+)?make\s+a(?:n)?\s+'
    r'(Strength|Dexterity|Constitution|Wisdom|Intelligence|Charisma)'
    r'\s+save', re.IGNORECASE)

SAVE_MAP = {s.lower(): s[:3].lower() for s in
            ['Strength', 'Dexterity', 'Constitution', 'Wisdom', 'Intelligence', 'Charisma']}

AOE_RADIUS = re.compile(r'(\d+)\s*ft\s*radius', re.IGNORECASE)
AOE_CONE = re.compile(r'(\d+)\s*ft\s*cone', re.IGNORECASE)
AOE_LINE = re.compile(r'(\d+)\s*ft.*?line', re.IGNORECASE)
AOE_CUBE = re.compile(r'(\d+)\s*ft\s*cube', re.IGNORECASE)
AOE_SPHERE = re.compile(r'(\d+)\s*ft\s*sphere', re.IGNORECASE)

RANGE_PATTERN = re.compile(
    r'^(?:Self|Touch|(\d+)(?:/(\d+))?)\s*(?:\((.*)\))?$')

# Prerequisite parsing
STAT_PREREQ = re.compile(r'>\s*(\d+)\s*(Str|Dex|Con|Wis|Int|Cha)\b', re.IGNORECASE)
AFFINITY_PREREQ = re.compile(r'>\s*(\d+)\s*([A-Z][\w\s/]+?)(?:\s*Affinity)?\s*(?:$|and|\b)', re.IGNORECASE)
MULTI_AFF_RE = re.compile(
    r'>\s*(\d+)\s*in\s*at\s*least\s*(\d+)\s*affinit', re.IGNORECASE)

FIELDS = [
    'mana', 'range', 'description', 'upcast', 'prerequisite',
    'damage_dice', 'damage_flat', 'extra_effect',
    'save', 'save_half', 'attack_roll',
    'aoe_radius', 'aoe_cone', 'aoe_line', 'aoe_cube',
    'aoe_self', 'concentration', 'costs_bonus_action',
    'affinity_required', 'int_required', 'con_required',
    'str_required', 'dex_required', 'wis_required', 'cha_required',
    'affinities_at_required', 'affinities_at_count',
]

# ── Parsing ──────────────────────────────────────────────────────
def parse_handbook(filepath):
    """Return dict: spell_name -> {mana, affinity, range, desc, upcast, prereq}"""
    with open(filepath, 'r') as f:
        text = f.read()

    spells = {}
    current_section = None
    for line in text.split('\n'):
        s = line.strip()
        if s.startswith('## '):
            current_section = s[3:].strip()
            continue
        if not s.startswith('| '):
            continue
        cells = [c.strip() for c in s.split('|')]
        if len(cells) < 6:
            continue
        name = cells[1]
        if not name or name.startswith('---') or name == 'Spell Name':
            continue
        try:
            mana = int(cells[2])
        except ValueError:
            continue
        spells[name] = {
            'mana': mana,
            'range': cells[3] if len(cells) > 3 else '',
            'affinity': cells[4] if len(cells) > 4 else '',
            'desc': cells[5] if len(cells) > 5 else '',
            'upcast': cells[6] if len(cells) > 6 else '',
            'prereq': cells[7] if len(cells) > 7 else '',
            'section': current_section,
        }
    return spells


def parse_range(rng_str):
    """Parse range string like '60', '30/60', 'Self (30 ft)', 'Touch', '120 (20 ft radius)'
    Returns dict with range, range_max, aoe info."""
    info = {}
    rng_str = rng_str.strip()
    if not rng_str:
        return info

    if rng_str.lower() == 'self':
        info['aoe_self'] = True
        return info
    if rng_str.lower() == 'touch':
        info['range'] = 'Touch'
        return info

    # Check for "Self (...)" and "Touch (...)" patterns
    if rng_str.lower().startswith('self'):
        info['aoe_self'] = True
        # extract parenthetical like "Self (30 ft radius)"
        paren = re.search(r'\((.*)\)', rng_str)
        if paren:
            return _parse_aoe_paren(paren.group(1), info)
        return info

    if rng_str.lower().startswith('touch'):
        info['range'] = 'Touch'
        return info

    m = RANGE_PATTERN.match(rng_str)
    if m:
        if m.group(1):
            info['range'] = int(m.group(1))
        if m.group(2):
            info['range_max'] = int(m.group(2))
        if m.group(3):
            _parse_aoe_paren(m.group(3), info)
    else:
        info['range'] = rng_str

    return info


def _parse_aoe_paren(paren_text, info):
    """Parse parenthetical AoE like '20 ft radius', '30 ft cone', 'line, 10 ft wide'"""
    t = paren_text.lower()
    m = AOE_RADIUS.search(t)
    if m:
        info['aoe_radius'] = int(m.group(1))
    m = AOE_CONE.search(t)
    if m:
        info['aoe_radius'] = int(m.group(1))
        info['aoe_cone'] = True
    m = AOE_LINE.search(t)
    if m:
        info['aoe_line'] = True
    m = AOE_CUBE.search(t)
    if m:
        info['aoe_radius'] = int(m.group(1))
        info['aoe_cube'] = True
    m = AOE_SPHERE.search(t)
    if m:
        info['aoe_radius'] = int(m.group(1))
    return info


def parse_prereq(prereq_str, desc_str):
    """Parse prerequisite column and also extract stat/affinity requirements from description.
    Returns dict with affinity_required, int_required, etc."""
    info = {}
    # Combine both for parsing
    combined = f"{prereq_str} {desc_str}"

    if not prereq_str or prereq_str.lower() == 'none':
        # Try description
        pass

    # Stat requirements: >16 Int
    for m in STAT_PREREQ.finditer(prereq_str):
        val = int(m.group(1)) + 1
        stat = m.group(2).lower()
        if stat == 'str':
            info['str_required'] = val
        elif stat == 'dex':
            info['dex_required'] = val
        elif stat == 'con':
            info['con_required'] = val
        elif stat == 'wis':
            info['wis_required'] = val
        elif stat == 'int':
            info['int_required'] = val
        elif stat == 'cha':
            info['cha_required'] = val

    # Also check description for stat requirements (like ">16 Int")
    for m in STAT_PREREQ.finditer(desc_str):
        val = int(m.group(1)) + 1
        stat = m.group(2).lower()
        key = f'{stat}_required'
        if key not in info:
            info[key] = val

    return info


def parse_upcast_chain(upcast_str):
    """Parse upcast column. Returns dict:
    - next_spell: name of the next spell in chain (if it's a spell name)
    - upcast_rule: scaling rule string (e.g., 'x2, +3d6 damage')
    """
    if not upcast_str or upcast_str.lower() in ('none', '-'):
        return {}
    # If it's just a spell name (no digits, no commas), it's the next spell
    if re.match(r'^[A-Z][a-zA-Z\s]+$', upcast_str.strip()):
        return {'upcast_to': upcast_str.strip()}
    # Otherwise it's a scaling rule
    return {'upcast_rule': upcast_str.strip()}


def extract_spell_info(desc, prereq_str, rng_str):
    """Extract all machine-readable fields from a spell."""
    info = {}

    # Damage
    m = DAMAGE_FLAT_DICE.search(desc)
    if m:
        info['damage_dice'] = m.group('dice')
        info['damage_flat'] = int(float(m.group('flat')))
    else:
        m = DICE_ONLY.search(desc)
        if m:
            info['damage_dice'] = m.group('dice')

    # Conditions with stack counts
    conditions = []
    for cond in ALL_CONDITIONS:
        p = re.search(rf'{re.escape(cond)}\s*x(\d+)', desc, re.IGNORECASE)
        if p:
            count = int(p.group(1))
            cname = COND_ALIAS.get(cond, cond)
            conditions.append(f'{cname} x{count}')
        elif re.search(rf'\b{re.escape(cond)}\b', desc, re.IGNORECASE):
            cname = COND_ALIAS.get(cond, cond)
            conditions.append(cname)
    if conditions:
        info['extra_effect'] = '+'.join(conditions)

    # Save
    m = SAVE_RE.search(desc)
    if m:
        info['save'] = SAVE_MAP.get(m.group(1).lower(), m.group(1)[:3].lower())
    if 'half damage' in desc.lower() or 'take half' in desc.lower():
        info['save_half'] = True

    # Attack roll
    if 'spell attack' in desc.lower():
        info['attack_roll'] = True

    # AoE from description (even if not in range)
    for pattern, key in [(AOE_RADIUS, 'aoe_radius'), (AOE_CONE, 'aoe_cone'),
                          (AOE_LINE, 'aoe_line'), (AOE_CUBE, 'aoe_cube')]:
        m = pattern.search(desc)
        if m:
            if key == 'aoe_radius' and 'aoe_radius' not in info:
                info['aoe_radius'] = int(m.group(1))
            elif key not in ('aoe_radius',):
                info[key] = True
                if 'aoe_radius' not in info:
                    try:
                        info['aoe_radius'] = int(m.group(1))
                    except (IndexError, ValueError):
                        pass

    # Range parsing
    range_info = parse_range(rng_str)
    for k, v in range_info.items():
        if k == 'range' and 'range' not in info:
            info[k] = v
        elif k not in ('range',):
            if k == 'aoe_self' and v:
                info['aoe_self'] = True
            elif k == 'aoe_radius' and 'aoe_radius' not in info:
                info['aoe_radius'] = v
            elif k == 'range_max' and 'range_max' not in info:
                info['range_max'] = v

    # Concentration
    if 'concentration' in desc.lower():
        info['concentration'] = True

    # Bonus action cost
    if 'bonus action to cast' in desc.lower() or 'additional bonus action' in desc.lower():
        info['costs_bonus_action'] = True

    # Prerequisites from the prereq column
    prereqs = parse_prereq(prereq_str, desc)
    info.update(prereqs)

    # Affinity required from prerequisite
    m = AFFINITY_PREREQ.search(prereq_str)
    if m:
        val = int(m.group(1)) + 1
        aff_name = m.group(2).strip()
        # Determine which affinity
        info['affinity_required'] = val

    # Multi-affinity prerequisite like ">5 in at least 3 affinities"
    m = MULTI_AFF_RE.search(prereq_str)
    if m:
        info['affinity_required'] = int(m.group(1)) + 1
        info['affinities_at_required'] = int(m.group(1)) + 1
        info['affinities_at_count'] = int(m.group(2))

    return info


def fmt_val(v):
    if v is None:
        return '(none)'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    return str(v)


def _affinity_from_prereq(prereq_str, handbook_affinity):
    """Determine what affinity this spell belongs to based on the prereq column."""
    # If the prereq mentions a specific affinity, use that
    m = re.search(r'>\s*\d+\s*([A-Z][\w\s/]+?)(?:\s*Affinity)?\s*(?:$|and)', prereq_str, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        return name
    # Otherwise use the handbook's affinity column
    return handbook_affinity


# ── Main ─────────────────────────────────────────────────────────
def main():
    log_lines = []
    def log(s=''):
        log_lines.append(s)

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log(f"EYUM TTRPG — SPELL UPDATER LOG")
    log(f"Run at: {ts}")
    log(f"Handbook: {HANDBOOK_PATH}")
    log(f"Spells JSON: {SPELLS_PATH}")
    log("=" * 70)

    if not os.path.exists(HANDBOOK_PATH):
        print(f"ERROR: Handbook not found at {HANDBOOK_PATH}")
        _flush_log(log_lines, LOG_PATH)
        sys.exit(1)

    handbook = parse_handbook(HANDBOOK_PATH)
    log(f"Parsed {len(handbook)} spells from handbook")

    with open(SPELLS_PATH, 'r') as f:
        spells_json = json.load(f)

    # Build reverse index
    json_index = {}
    for aff_name, slist in spells_json.items():
        for s in slist:
            base = re.sub(r'\s*\(.*\)$', '', s['name']).strip()
            json_index.setdefault(base, []).append((aff_name, s, s['name']))

    # ── Update existing spells ──
    changed = []
    unchanged = []
    not_in_handbook = []

    for base_name, entries in json_index.items():
        if base_name not in handbook:
            for aff, s, orig_name in entries:
                not_in_handbook.append(f"  {orig_name} ({aff})")
            continue

        h = handbook[base_name]
        info = extract_spell_info(h['desc'], h['prereq'], h['range'])
        upcast = parse_upcast_chain(h['upcast'])

        for aff, s, orig_name in entries:
            diffs = []

            # ── simple fields ──
            if s.get('mana') != h['mana']:
                diffs.append(f"mana: {s['mana']} → {h['mana']}")
                s['mana'] = h['mana']

            # description
            if s.get('description', '') != h['desc']:
                sammary = h['desc'][:60] + ('...' if len(h['desc']) > 60 else '')
                diffs.append(f"description updated")
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
            if 'damage_dice' in info and info['damage_dice'] != s.get('damage_dice', ''):
                diffs.append(f"damage_dice: {fmt_val(s.get('damage_dice'))} → {info['damage_dice']}")
                s['damage_dice'] = info['damage_dice']
            if 'damage_flat' in info and info.get('damage_flat', 0) != s.get('damage_flat', 0):
                diffs.append(f"damage_flat: {s.get('damage_flat', 0)} → {info['damage_flat']}")
                s['damage_flat'] = info['damage_flat']

            # conditions
            if 'extra_effect' in info and info['extra_effect'] != s.get('extra_effect', ''):
                diffs.append(f"extra_effect: {fmt_val(s.get('extra_effect'))} → {info['extra_effect']}")
                s['extra_effect'] = info['extra_effect']

            # save
            if 'save' in info and s.get('save') != info['save']:
                diffs.append(f"save: {fmt_val(s.get('save'))} → {info['save']}")
                s['save'] = info['save']
                if s.get('attack_roll') and info.get('save'):
                    s['attack_roll'] = False
                    diffs.append(f"attack_roll: true → false (save-based)")

            # AoE
            for aoe_key in ('aoe_radius', 'aoe_cone', 'aoe_line', 'aoe_cube', 'aoe_self'):
                if aoe_key in info:
                    hval = info[aoe_key]
                    sval = s.get(aoe_key)
                    if aoe_key == 'aoe_radius':
                        if hval != (sval or 0 if isinstance(hval, int) else None):
                            diffs.append(f"{aoe_key}: {fmt_val(sval)} → {hval}")
                            s[aoe_key] = hval
                    else:
                        if hval and not sval:
                            diffs.append(f"{aoe_key}: false → true")
                            s[aoe_key] = True

            # booleans
            for flag in ('concentration', 'attack_roll', 'save_half', 'costs_bonus_action'):
                hval = info.get(flag)
                sval = s.get(flag)
                if hval and not sval:
                    diffs.append(f"{flag}: false → true")
                    s[flag] = True

            # stat prerequisites
            for stat_key in ('int_required', 'con_required', 'str_required',
                            'dex_required', 'wis_required', 'cha_required',
                            'affinity_required', 'affinities_at_required',
                            'affinities_at_count'):
                if stat_key in info:
                    hval = info[stat_key]
                    sval = s.get(stat_key)
                    if hval != sval:
                        diffs.append(f"{stat_key}: {fmt_val(sval)} → {hval}")
                        s[stat_key] = hval

            if diffs:
                changed.append((orig_name, aff, diffs))
            else:
                unchanged.append(f"  {orig_name} ({aff})")

    # ── New spells ──
    all_json_bases = set()
    for entries in json_index.values():
        for _, _, oname in entries:
            all_json_bases.add(re.sub(r'\s*\(.*\)$', '', oname).strip())

    new_spells = {n: h for n, h in handbook.items() if n not in all_json_bases}

    print(f"\n{'='*60}")
    print(f"Spell Updater — {len(changed)} changed, {len(unchanged)} unchanged")
    print(f"{len(new_spells)} spells in handbook not in spells.json")
    print(f"{len(not_in_handbook)} spells in JSON not in handbook")
    print(f"{'='*60}")

    if new_spells:
        print(f"\nNew spells in handbook NOT in spells.json:")
        for name in sorted(new_spells.keys()):
            print(f"  {name} ({new_spells[name]['affinity']})")
        answer = input(f"\nAdd these {len(new_spells)} spells to spells.json? [y/N]: ").strip().lower()
        if answer == 'y':
            added = []
            for hname, hdata in new_spells.items():
                info = extract_spell_info(hdata['desc'], hdata['prereq'], hdata['range'])
                upcast = parse_upcast_chain(hdata['upcast'])
                affinity = hdata['affinity']
                if affinity == 'Special':
                    affinity = _affinity_from_prereq(hdata['prereq'], hdata['affinity'])
                if affinity not in spells_json:
                    spells_json[affinity] = []

                entry = {'name': hname, 'mana': hdata['mana'],
                         'description': hdata['desc'],
                         'damage_type': affinity.lower()}
                if 'range' in info:
                    entry['range'] = info['range']
                if 'range_max' in info:
                    entry['range_max'] = info['range_max']
                for field in ('damage_dice', 'damage_flat', 'extra_effect', 'save',
                              'aoe_radius', 'affinity_required',
                              'int_required', 'con_required', 'str_required',
                              'dex_required', 'wis_required', 'cha_required',
                              'affinities_at_required', 'affinities_at_count'):
                    if field in info:
                        entry[field] = info[field]
                for flag in ('aoe_cone', 'aoe_line', 'aoe_cube', 'aoe_self',
                            'concentration', 'attack_roll', 'save_half',
                            'costs_bonus_action'):
                    if info.get(flag):
                        entry[flag] = True
                for k, v in upcast.items():
                    entry[k] = v

                spells_json[affinity].append(entry)
                added.append(hname)
                log(f"  + ADDED: {hname} ({affinity}) mana={hdata['mana']}")

            # Sort each affinity's list by mana
            for aff_name in spells_json:
                spells_json[aff_name].sort(key=lambda x: x.get('mana', 0))
            print(f"  Added {len(added)} spells.")
        else:
            log(f"\nUser chose NOT to add new spells.")
            for hname, hdata in sorted(new_spells.items()):
                log(f"  (skipped) {hname} ({hdata['affinity']}): mana={hdata['mana']}")

    # ── Write JSON ──
    with open(SPELLS_PATH, 'w') as f:
        json.dump(spells_json, f, indent=2)
        f.write('\n')

    # ── Write log ──
    log(f"\n{'='*70}")
    log(f"SUMMARY")
    log(f"{'='*70}")
    log(f"  Total spells in handbook: {len(handbook)}")
    log(f"  Changed:  {len(changed)}")
    log(f"  Unchanged: {len(unchanged)}")
    log(f"  New (in handbook, not in JSON): {len(new_spells)}")

    if changed:
        log(f"\n{'─'*70}")
        log(f"CHANGED SPELLS ({len(changed)})")
        log(f"{'─'*70}")
        for name, aff, diffs in sorted(changed, key=lambda x: x[0].lower()):
            log(f"\n  {name} ({aff})")
            for d in diffs:
                log(f"      {d}")

    if unchanged:
        log(f"\n{'─'*70}")
        log(f"UNCHANGED SPELLS ({len(unchanged)})")
        log(f"{'─'*70}")
        for line in sorted(unchanged):
            log(line)

    if new_spells and answer != 'y':
        log(f"\n{'─'*70}")
        log(f"SKIPPED NEW SPELLS ({len(new_spells)})")
        log(f"{'─'*70}")
        for hname in sorted(new_spells.keys()):
            hdata = new_spells[hname]
            log(f"  {hname} ({hdata['affinity']}): mana={hdata['mana']}")

    if not_in_handbook:
        log(f"\n{'─'*70}")
        log(f"SPELLS IN JSON NOT IN HANDBOOK ({len(not_in_handbook)})")
        log(f"{'─'*70}")
        log(f"  (These may be healing/utility spells from a separate handbook section.)")
        for line in sorted(not_in_handbook):
            log(line)

    log(f"\n{'='*70}")
    log(f"End of log — {ts}")

    _flush_log(log_lines, LOG_PATH)
    print(f"\nDone. Full report written to: {LOG_PATH}")


def _flush_log(lines, path):
    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
