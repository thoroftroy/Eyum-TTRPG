#!/usr/bin/env python3
r"""
Handbook Syncer — syncs spells AND feats from the handbook to JSON data.
Run from the Character Manager root directory:
    python3 update_spells.py

Parses 6.1.1 Elemental Spells.md and 6.1.2 Unique, Racial, and Healing Spells.md and 3.4 Feats.md, compares against
data/spells.json and data/feats.json, and writes output/updater_log.txt.
Preserves all generator custom keys.
"""

import json, re, os, sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HANDBOOK_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), '6.0 Magic', '6.1 Spells', '6.1.1 Elemental Spells.md')
HANDBOOK_PATH_2 = os.path.join(os.path.dirname(SCRIPT_DIR), '6.0 Magic', '6.1 Spells', '6.1.2 Unique, Racial, and Healing Spells.md')
FEATS_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), '3.0 Character Management', '3.4 Feats.md')
SPELLS_JSON = os.path.join(SCRIPT_DIR, 'data', 'spells.json')
FEATS_JSON = os.path.join(SCRIPT_DIR, 'data', 'feats.json')
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

# Generator modeling overrides — intended to be empty. Add entries only when
# the handbook's text cannot be mechanically modeled by the damage parser.
# Each entry should have a comment explaining WHY the override is needed.
DAMAGE_OVERRIDES = {}

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
    log(f"EYUM TTRPG — HANDBOOK SYNCER LOG")
    log(f"Run at: {ts}")
    log("=" * 70)

    sync_spells(log_lines, log)
    sync_feats(log_lines, log)

    log(f"\n{'='*70}\nEnd of log — {ts}")
    _flush(log_lines)
    print(f"\nDone. Full report: {LOG_PATH}")


def sync_spells(log_lines, log):
    if not os.path.exists(HANDBOOK_PATH):
        print(f"ERROR: Elemental spells not found at {HANDBOOK_PATH}")
        _flush(log_lines); sys.exit(1)
    if not os.path.exists(HANDBOOK_PATH_2):
        print(f"ERROR: Unique/racial/healing spells not found at {HANDBOOK_PATH_2}")
        _flush(log_lines); sys.exit(1)

    handbook = parse_handbook(HANDBOOK_PATH)
    handbook2 = parse_handbook(HANDBOOK_PATH_2)
    handbook.update(handbook2)
    log(f"Parsed {len(handbook)} spells from handbook ({len(handbook2)} unique/racial/healing)")

    clear_affinity_markers()

    with open(SPELLS_JSON, 'r') as f:
        spells_json = json.load(f)

    json_index = {}
    for aff_name, slist in spells_json.items():
        for s in slist:
            base = re.sub(r'\s*\(.*\)$', '', s['name']).strip()
            json_index.setdefault(base, []).append((aff_name, s, s['name']))

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
            skip_keys = set(DAMAGE_OVERRIDES.get((aff, base), {}).keys())
            diffs = []

            if s.get('mana') != h['mana']:
                diffs.append(f"mana: {s['mana']} -> {h['mana']}")
                s['mana'] = h['mana']

            if s.get('description', '') != h['desc']:
                diffs.append("description updated")
                s['description'] = h['desc']

            for uk, uv in upcast.items():
                if s.get(uk) != uv:
                    diffs.append(f"{uk}: {fmt_val(s.get(uk))} -> {uv}")
                    s[uk] = uv

            if 'range' in info and s.get('range') != info['range']:
                diffs.append(f"range: {fmt_val(s.get('range'))} -> {info['range']}")
                s['range'] = info['range']
            if 'range_max' in info and s.get('range_max') != info['range_max']:
                diffs.append(f"range_max: {fmt_val(s.get('range_max'))} -> {info['range_max']}")
                s['range_max'] = info['range_max']

            if 'damage_dice' in info and 'damage_dice' not in skip_keys:
                nd = info['damage_dice']; od = s.get('damage_dice', '')
                if nd != od:
                    diffs.append(f"damage_dice: {od} -> {nd}")
                    s['damage_dice'] = nd
            if 'damage_flat' in info and 'damage_flat' not in skip_keys:
                nf = info['damage_flat']; of = s.get('damage_flat', 0)
                if nf != of:
                    diffs.append(f"damage_flat: {of} -> {nf}")
                    s['damage_flat'] = nf

            ne = info.get('extra_effect') or ''; oe = s.get('extra_effect') or ''
            if ne and ne != oe:
                diffs.append(f"extra_effect: {oe} -> {ne}")
                s['extra_effect'] = ne

            if 'save' in info and 'save' not in skip_keys:
                if s.get('save') != info['save']:
                    diffs.append(f"save: {fmt_val(s.get('save'))} -> {info['save']}")
                    s['save'] = info['save']
                    if s.get('attack_roll'): s['attack_roll'] = False; diffs.append("attack_roll->false (save)")

            for k in ('aoe_radius','aoe_cone','aoe_line','aoe_cube','aoe_self'):
                v = info.get(k)
                if v is None: continue
                if k == 'aoe_radius':
                    if s.get(k) != v: diffs.append(f"{k}: {s.get(k)} -> {v}"); s[k] = v
                elif v and not s.get(k): diffs.append(f"{k}: false -> true"); s[k] = True

            for flag in ('concentration','attack_roll','save_half','costs_bonus_action'):
                if info.get(flag) and not s.get(flag):
                    diffs.append(f"{flag}: false -> true"); s[flag] = True

            for sk in STAT_PREREQ_KEYS:
                if sk in info and s.get(sk) != info[sk]:
                    diffs.append(f"{sk}: {fmt_val(s.get(sk))} -> {info[sk]}")
                    s[sk] = info[sk]

            if 'affinity_required' in info:
                nv = info['affinity_required']
                if s.get('affinity_required') != nv:
                    diffs.append(f"affinity_required: {fmt_val(s.get('affinity_required'))} -> {nv}")
                    s['affinity_required'] = nv

            for k, v in custom.items():
                if s.get(k) != v:
                    diffs.append(f"{k}: restored (custom flag)")
                    s[k] = v

            if diffs:
                changed.append((orig_name, aff, diffs))
                _mark_affinity(aff)
            else:
                unchanged.append(f"  {orig_name} ({aff})")

    all_bases = set()
    for entries in json_index.values():
        for _, _, on in entries:
            all_bases.add(re.sub(r'\s*\(.*\)$', '', on).strip())

    new_spells = {n: h for n, h in handbook.items() if n not in all_bases}

    print(f"\n{'='*60}")
    print(f"Spells — {len(changed)} changed, {len(unchanged)} unchanged")
    print(f"{len(new_spells)} new in handbook, {len(not_in_handbook)} in JSON only")
    print(f"{'='*60}")

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
                log(f"  + ADDED spell: {hname} ({aff}) mana={hdata['mana']}")
            for a in spells_json:
                spells_json[a].sort(key=lambda x: (x.get('affinity_required',0), x.get('mana',0)))

    for (aff_name, spell_name), overrides in DAMAGE_OVERRIDES.items():
        if aff_name not in spells_json: continue
        for s in spells_json[aff_name]:
            if s.get('name') == spell_name:
                for k, v in overrides.items():
                    if s.get(k) != v:
                        log(f"  OVERRIDE: {spell_name} ({aff_name}): {k}: {s.get(k)} -> {v}")
                        s[k] = v
                break

    for aff, slist in spells_json.items():
        aff_lower = aff.lower()
        for s in slist:
            if 'damage_type' not in s: s['damage_type'] = aff_lower

    with open(SPELLS_JSON, 'w') as f:
        json.dump(spells_json, f, indent=2); f.write('\n')

    log(f"\nSpells: {len(changed)} changed, {len(unchanged)} unchanged, {len(new_spells)} new")


# ── Feat syncing ─────────────────────────────────────────────────

STAT_ABBREV = {'str': 'STR', 'dex': 'DEX', 'con': 'CON', 'wis': 'WIS', 'int': 'INT', 'cha': 'CHA'}
STAT_REV = {v: k for k, v in STAT_ABBREV.items()}

def parse_feat_handbook(filepath):
    """Parse the 3.4 Feats.md markdown table."""
    with open(filepath, 'r') as f: text = f.read()
    feats = {}
    in_table = False
    for line in text.split('\n'):
        s = line.strip()
        if s.startswith('| Name') and 'Type' in s:
            in_table = True; continue
        if in_table and s == '':
            in_table = False; continue
        if not in_table or not s.startswith('| '):
            continue
        cells = [c.strip() for c in s.split('|')]
        if len(cells) < 4: continue
        name = cells[1].replace('<br>', '').strip()
        if not name or name.startswith('---') or name == 'Name': continue
        feat_type = cells[2] if len(cells) > 2 else ''
        desc = cells[3] if len(cells) > 3 else ''
        prereq_raw = cells[4] if len(cells) > 4 else ''
        feats[name] = {'type': feat_type, 'desc': desc, 'prereq_raw': prereq_raw}
    return feats


def parse_feat_prereqs(prereq_str):
    """Parse feat prerequisite string into structured data."""
    prereq = {}
    if not prereq_str or prereq_str.lower() == 'none':
        return prereq

    # Level: "Level 6", "Level 9"
    m = re.search(r'Level\s+(\d+)', prereq_str, re.IGNORECASE)
    if m: prereq['level'] = int(m.group(1))

    # Stats: "Dex 12", "Str 14", "Con 18", etc.
    for abbr, full in STAT_ABBREV.items():
        m = re.search(rf'\b{full}\s+(\d+)', prereq_str, re.IGNORECASE)
        if m:
            prereq.setdefault('stat', {})[abbr] = int(m.group(1))

    # Path/Archetype: "Marksman Lvl 2", "Pyromancer Lvl 1", "Indomitable Lvl 3"
    m = re.search(r'(\w[\w\s]*?)\s+Lvl\s+(\d+)', prereq_str, re.IGNORECASE)
    if m:
        arch_name = m.group(1).strip()
        prereq.setdefault('path', {})[arch_name] = int(m.group(2))

    # Specific affinities: "Psychic Aff 5+", "Lightning Aff 3+"
    m = re.search(r'(\w[\w/]*)\s+Aff\s*(\d+)\+', prereq_str, re.IGNORECASE)
    if m:
        prereq.setdefault('affinity', {})[m.group(1)] = int(m.group(2))

    # Other feat: "Rounded Mage"
    for fn in ('Rounded Mage', 'Weapon Master', 'All Rounded Mage'):
        if fn.lower() in prereq_str.lower():
            prereq.setdefault('feat', []).append(fn)

    # Armor proficiency
    if 'armor' in prereq_str.lower() or 'proficient' in prereq_str.lower():
        prereq['armor_proficiency'] = True

    # Medicine proficiency
    if 'medicine' in prereq_str.lower():
        prereq['medicine_proficiency'] = True

    # Multiple proficiencies
    m = re.search(r'Proficiency with more than (\d+)', prereq_str, re.IGNORECASE)
    if m: prereq['min_proficiencies'] = int(m.group(1))

    # Multiple affinities
    m = re.search(r'>(\d+)\s+affinity in at least (\d+) affinities', prereq_str, re.IGNORECASE)
    if m: prereq['min_affinity'] = int(m.group(1)); prereq['min_affinity_count'] = int(m.group(2))

    return prereq


# ── Feat effects mapping (handbook text -> generator effects) ──

def feat_effects_to_json(name, desc):
    """Convert feat description text to generator-compatible effect keys."""
    effects = {}

    # Damage dice on crit
    m = re.search(r'deal an additional \+(\d+d\d+) damage', desc, re.IGNORECASE)
    if m: effects['crit_damage_die'] = m.group(1)

    # Charge damage
    m = re.search(r'deal \+(\d+d\d+) bludgeoning', desc, re.IGNORECASE)
    if m: effects['charge_die'] = m.group(1)

    # Prone damage bonus
    m = re.search(r'Deal \+(\d+d\d+) damage to targets that are Prone', desc, re.IGNORECASE)
    if m: effects['prone_die'] = m.group(1)

    # Unarmed die upgrade
    if 'unarmed strikes damage go up by a dice tier' in desc.lower():
        effects['unarmed_die_upgrade'] = 1

    # Dual wield accuracy
    m2 = re.search(r'gain \+(\d+) to all attack rolls', desc, re.IGNORECASE)
    if m2 and ('dual wielding' in desc.lower() or 'two weapons' in desc.lower()):
        effects['dual_wield_accuracy'] = int(m2.group(1))

    # AC bonus (armor training)
    if 'Gain +1 HP' in desc and 'Gain +2 Vit' in desc:
        effects['vit_per_level'] = 2
        effects['hp_per_level'] = 1

    # Toughness
    m = re.search(r'Gain \+(\d+) HP and \+(\d+) Vit per level', desc)
    if m: effects['hp_per_level'] = int(m.group(1)); effects['vit_per_level'] = int(m.group(2))

    # Mana Flow
    m = re.search(r'Increase Max Mana by \+(\d+) per level', desc)
    if m: effects['mana_per_level'] = int(m.group(1))

    # Extra BAp
    if 'gain a Bonus Action Point' in desc.lower() or 'gain an additional Bonus Action' in desc.lower():
        effects['bap'] = 1

    # Extra Rp
    if 'gain an additional Reaction Point' in desc.lower():
        effects['rp'] = 1

    # Extra Ap (none exist but handle)
    if 'gain an additional Action Point' in desc.lower():
        effects['ap'] = 1

    # Shield Master
    if 'Shields AC bonus by 50%' in desc or 'shield' in desc.lower() and '50%' in desc:
        effects['shield_master'] = True

    # Steady Aim
    m = re.search(r'gain \+(\d+) Base Ranged Accuracy', desc)
    if m and 'move' in desc.lower():
        effects['steady_aim_accuracy'] = int(m.group(1))

    # Point Blank
    if 'disadvantage on Ranged attacks within 5ft' in desc:
        effects['point_blank'] = True

    # Great Cleave
    m = re.search(r'this attack.*deals \+(\d+) damage', desc, re.IGNORECASE)
    if m and 'kill an enemy' in desc.lower():
        effects['cleave_damage'] = int(m.group(1))

    # Heavy Hitter
    m = re.search(r'add \+(\d+) to Melee Damage', desc)
    if m: effects['melee_damage'] = int(m.group(1))

    # Save half magic
    if 'deal 0 damage on a save now deal half' in desc.lower():
        effects['save_half_magic'] = True

    # Eternal mana
    m = re.search(r'below (\d+) mana gain (\d+) mana', desc)
    if m: effects['eternal_mana_threshold'] = int(m.group(1)); effects['eternal_mana_amount'] = int(m.group(2))

    # Execute threshold
    if 'less than 10% HP are always Crits' in desc:
        effects['execute_threshold'] = 0.1

    # Speed
    m = re.search(r'Increase base Speed by \+(\d+)ft', desc)
    if m: effects['speed'] = int(m.group(1))

    # AC bonus from Stone Skin, Armor Training, etc.
    m = re.search(r'gain \+(\d+) AC', desc)
    if m and name != 'Shield Master' and 'Dex' not in desc.split('AC')[0]:
        effects['ac_bonus'] = int(m.group(1))

    # Armor Training AC bonuses
    if 'Light: +1' in desc and 'Medium: +2' in desc:
        effects['armor_training_ac_light'] = 1
        effects['armor_training_ac_medium'] = 2
        effects['armor_training_ac_heavy'] = 3

    # Dodge Master
    m = re.search(r'max AC bonus from Dex raises by \+(\d+)', desc)
    if m: effects['maximum_dex_ac_bonus'] = int(m.group(1))

    # Generic affinity
    m = re.search(r'gain \+(\d+) to Generic Affinity', desc)
    if m: effects['generic_affinity'] = int(m.group(1))

    # Affinity bonus (specific)
    m = re.search(r'Increase (Fire|Earth|Water|Air|Radiant|Necrotic|Psychic) Affinity by \+(\d+)', desc)
    if m:
        effects.setdefault('affinity', {})[m.group(1)] = int(m.group(2))

    # Affinity Master
    if 'gain +2 affinity in Fire, Earth Water, and air' in desc.lower():
        effects['affinity'] = {'Fire': 2, 'Earth': 2, 'Water': 2, 'Air': 2}

    # Affinity Specialist
    if 'Choose one Affinity; increase it by' in desc:
        m = re.search(r'increase it by \+(\d+)', desc)
        if m: effects['affinity_points'] = 3

    if 'gain +3 Affinity Points' in desc: effects['affinity_points'] = 3

    # Defensive Duelist
    if 'Add your Proficiency Bonus to AC' in desc:
        effects['defensive_duelist_ac'] = True

    return effects if effects else {}


def sync_feats(log_lines, log):
    if not os.path.exists(FEATS_PATH):
        log("Feats handbook not found — skipping feat sync")
        return

    handbook = parse_feat_handbook(FEATS_PATH)
    log(f"Parsed {len(handbook)} feats from handbook")

    if not os.path.exists(FEATS_JSON):
        log("feats.json not found — creating from handbook")
        feats_json = {}
    else:
        with open(FEATS_JSON, 'r') as f:
            feats_json = json.load(f)

    changed = []; removed = []

    # Sync existing + add new
    for name, hdata in handbook.items():
        prereq = parse_feat_prereqs(hdata['prereq_raw'])
        effects = feat_effects_to_json(name, hdata['desc'])

        if name not in feats_json:
            # New feat
            feats_json[name] = {
                'type': hdata['type'],
                'description': hdata['desc'],
                'prerequisites': prereq,
                'effects': effects,
                'value': 0
            }
            changed.append(f"  + NEW: {name} ({hdata['type']})")
            log(f"  + NEW feat: {name} ({hdata['type']}) — prereq: {hdata['prereq_raw']}")
            continue

        old = feats_json[name]
        diffs = []

        # Update type
        if old.get('type') != hdata['type']:
            diffs.append(f"type: {old.get('type')} -> {hdata['type']}")
            old['type'] = hdata['type']

        # Update description
        if old.get('description') != hdata['desc']:
            diffs.append("description updated")
            old['description'] = hdata['desc']

        # Update prerequisites
        old_prereq = old.get('prerequisites', {})
        if old_prereq != prereq:
            diffs.append(f"prerequisites: {old_prereq} -> {prereq}")
            old['prerequisites'] = prereq

        # Update effects (preserve value score)
        old_effects = old.get('effects', {})
        if old_effects != effects and effects:
            diffs.append(f"effects updated: {old_effects} -> {effects}")
            old['effects'] = effects

        if diffs:
            changed.append(f"  ~ {name}: {'; '.join(diffs)}")
            log(f"  ~ {name}: {'; '.join(diffs)}")

    # Remove feats no longer in handbook
    to_remove = [n for n in feats_json if n not in handbook]
    for n in to_remove:
        removed.append(n)
        del feats_json[n]
        log(f"  - REMOVED feat: {n} (no longer in handbook)")

    with open(FEATS_JSON, 'w') as f:
        json.dump(feats_json, f, indent=2); f.write('\n')

    print(f"\nFeats — {len([c for c in changed if c.startswith('  ~')])} updated, "
          f"{len([c for c in changed if c.startswith('  +')])} new, "
          f"{len(removed)} removed")
    log(f"\nFeats: {len([c for c in changed if c.startswith('  ~')])} updated, "
        f"{len([c for c in changed if c.startswith('  +')])} new, "
        f"{len(removed)} removed")


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
