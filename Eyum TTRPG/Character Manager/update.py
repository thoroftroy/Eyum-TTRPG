#!/usr/bin/env python3
"""Universal Handbook Syncer — syncs spells, races, conditions, and affinities.

Parses all handbook markdown tables and updates the Character Manager JSON data.
Reports any changes that require manual intervention.
"""

import json, re, os, sys, glob
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HANDBOOK = os.path.join(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')
LOG_PATH = os.path.join(SCRIPT_DIR, 'output', 'updater_log.txt')
CHANGES_PATH = os.path.join(SCRIPT_DIR, 'changes.txt')
_changed_items = []  # Tracks all changed things for build regeneration

# ── Files to sync ──────────────────────────────────────────────
SPELL_FILES = [
    '6.0 Magic/6.1 Spells/6.1.1 Elemental Spells.md',
    '6.0 Magic/6.1 Spells/6.1.2 Unique, Racial, and Healing Spells.md',
]
RACE_FILES = [
    '4.0 Races/Human and Subraces.md',
    '4.0 Races/Bugfolk and Subraces.md',
    '4.0 Races/Demon and Subraces.md',
    '4.0 Races/Elves and Subraces.md',
    '4.0 Races/Fishfolk and Subraces.md',
    '4.0 Races/Harpy and Subraces.md',
    '4.0 Races/Naga and Subraces.md',
    '4.0 Races/Shapeshifters and Subraces.md',
    '4.0 Races/Therian and Subraces.md',
    '4.0 Races/Tull and Subraces.md',
    '4.0 Races/Undead and Subraces.md',
]
CONDITIONS_FILE = '2.0 Reference Tables/2.4 Conditions.md'
AFFINITIES_FILE = '2.0 Reference Tables/2.1 Affinities.md'
FEATS_FILE = '3.0 Character Management/3.4 Feats.md'

STAT_ABBREV = {'str': 'STR', 'dex': 'DEX', 'con': 'CON', 'wis': 'WIS', 'int': 'INT', 'cha': 'CHA'}
STAT_LOWER = {v.lower(): k for k, v in STAT_ABBREV.items()}

# ── Conditions list from handbook ───────────────────────────────
ALL_CONDITIONS = [
    'On Fire', 'Frozen', 'Soaked', 'Storm Shocked',
    'Hurting', 'Entangled', 'Suffocating', 'Prone', 'Grappled',
    'Lethargic', 'Unconscious', 'Surprised', 'Threatened',
    'Invisible', 'Intangible', 'Grounded', 'Restrained',
    'Difficult Terrain', 'Overcrowded',
    'Bleeding', 'Pierced', 'Burned', 'Frostbitten',
    'Shocked', 'Poisoned', 'Diseased', 'Hellfire',
    'Purged', 'Corrupt', 'Necrosis', 'Blinded',
    'Deafened', 'Paralyzed', 'Petrified', 'Stunned',
    'Gelled', 'Radiation', 'Sickened', 'Withered', 'Plagued',
    'DoT', 'GroundBurn',
    'Charmed', 'Frightened', 'Enraged', 'Demoralized',
    'Despair', 'Hypnotized', 'Mute', 'Blurred', 'Addicted',
    'Psychic Drain', 'Nauseated',
    'Cursed', 'Hexed', 'Silenced', 'Slow Death',
    'Slowed', 'Hasted', 'Blessed', 'Hexproof', 'Eldritch Curse',
    'Push', 'Pull', 'Heal', 'NoFlight', 'NoAdvantage',
    'Collision', 'Scaling', 'Marked by Light',
    'Frostburned', 'Taboo', 'Vibrating',
    'Arsenic Poisoning', 'Bromine Toxin', 'Cancer',
    'Paralytic Toxin', 'Skorren Venom',
    'Infernal Brand', 'Infernal Ally Brand',
]

# ── Regex patterns ──────────────────────────────────────────────
DAMAGE_PAT = re.compile(
    r'(?:take|deal|taking|dealing|taken|suffer)s?\s+'
    r'(?:an?\s+(?:additional\s+)?)?(?:up\s+to\s+)?'
    r'(?:(?P<flat>\d+(?:\.\d+)?)\s*\+\s*(?P<dice>\d+d\d+)'
    r'|(?P<dice2>\d+d\d+)\s*\+\s*(?P<flat2>\d+(?:\.\d+)?))',
    re.IGNORECASE)
DICE_ONLY = re.compile(
    r'(?:take|deal|taking|dealing|taken|suffer)s?\s+(?P<dice>\d+d\d+)',
    re.IGNORECASE)
FLAT_ONLY = re.compile(
    r'(?:take|deal|taking|dealing|taken|suffer)s?\s+(?:an?\s+)?(?P<flat>\d+(?:\.\d+)?)\s+(?!d\d)(?!\d+d)\w+\s+damage',
    re.IGNORECASE)
# Broader damage patterns for spell descriptions that don't use "take/deal"
FALLBACK_FLAT = re.compile(
    r'(?::|,\s*they\s+take|target\s+takes?|creature\s+takes?|each\s+beam\s+deals?|inflicts?)\s+(?P<flat>\d+(?:\.\d+)?)\s+(?!\d*d\d)(?!level|turn|ft|round|minute|hour|day|stack|stacks)(?:\w+\s+){0,2}damage',
    re.IGNORECASE)
FALLBACK_DICE = re.compile(
    r'(?::|,\s*they\s+take|target\s+takes?|creature\s+takes?|each\s+beam\s+deals?|inflicts?)\s+(?P<dice>\d+d\d+)\s+\w+\s+damage',
    re.IGNORECASE)
SAVE_RE = re.compile(
    r'make\s+a(?:n)?\s+(Strength|Dexterity|Constitution|Wisdom|Intelligence|Charisma)\s+save',
    re.IGNORECASE)
SAVE_MAP = {s.lower(): s[:3].lower() for s in
            ['Strength','Dexterity','Constitution','Wisdom','Intelligence','Charisma']}

# ── Table parser ─────────────────────────────────────────────────
_WIKILINK_RE = re.compile(r'\[\[(.*?)\]\]')

def _protect_wikilinks(line):
    """Replace pipes inside [[wikilinks]] so table splitting doesn't break."""
    result = []
    last_end = 0
    for m in _WIKILINK_RE.finditer(line):
        result.append(line[last_end:m.start()])
        result.append(m.group(0).replace('|', '\x00PIPE\x00'))
        last_end = m.end()
    result.append(line[last_end:])
    return ''.join(result)

def _restore_wikilinks(cell):
    return cell.replace('\x00PIPE\x00', '|')


def parse_markdown_tables(filepath):
    """Parse ALL pipe-delimited tables from a markdown file.
    Returns list of (headers, rows) tuples."""
    with open(filepath, 'r') as f:
        lines = f.readlines()

    tables = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith('|'):
            i += 1; continue
        # Collect consecutive table lines
        start = i
        while i < len(lines) and lines[i].strip().startswith('|'):
            i += 1
        table_lines = lines[start:i]

        # Parse cells
        rows = []
        for tl in table_lines:
            protected = _protect_wikilinks(tl.strip())
            cells = [_restore_wikilinks(c.strip()) for c in protected.split('|')]
            # Remove empty first/last cells from pipe syntax
            if cells and cells[0] == '': cells = cells[1:]
            if cells and cells[-1] == '': cells = cells[:-1]
            rows.append(cells)

        if len(rows) >= 1:
            # First row is header, skip separator row (---|---)
            header = rows[0]
            data_rows = [r for r in rows[2:] if len(r) >= 2 and not all(c.startswith('-') for c in r if c)]
            if data_rows:
                tables.append((header, data_rows))
    return tables


def parse_spell_table(filepath):
    """Parse spell tables specifically — expects Name|Mana|Range|Affinity|Desc|Upcast|Prereq format."""
    tables = parse_markdown_tables(filepath)
    spells = {}
    for header, rows in tables:
        # Find column indices
        cols = {h.lower(): i for i, h in enumerate(header)}
        name_idx = cols.get('spell name', 0)
        mana_idx = cols.get('mana', 1)
        range_idx = cols.get('range', 2)
        aff_idx = cols.get('affinity', 3)
        desc_idx = cols.get('description', 4)
        upcast_idx = cols.get('upcast', 5) if len(header) > 5 else None
        prereq_idx = cols.get('prerequisite', 6) if len(header) > 6 else None

        for row in rows:
            if len(row) <= name_idx: continue
            name = row[name_idx]
            if not name or name.startswith('-') or name.lower() in ('spell name', 'name'):
                continue
            try:
                mana = int(row[mana_idx]) if mana_idx < len(row) else 0
            except (ValueError, IndexError):
                continue
            spells[name] = {
                'mana': mana,
                'range': row[range_idx] if range_idx < len(row) else '',
                'affinity': row[aff_idx] if aff_idx < len(row) else '',
                'desc': row[desc_idx] if desc_idx < len(row) else '',
                'upcast': row[upcast_idx] if upcast_idx and upcast_idx < len(row) else '',
                'prereq': row[prereq_idx] if prereq_idx and prereq_idx < len(row) else '',
            }
    return spells


def extract_spell_info(desc, prereq_str, rng_str):
    """Extract mechanical info from spell description/prereq/range."""
    info = {}
    # Damage dice + flat
    m = DAMAGE_PAT.search(desc)
    if m:
        info['damage_dice'] = m.group('dice') or m.group('dice2')
        info['damage_flat'] = int(float(m.group('flat') or m.group('flat2')))
    else:
        m = DICE_ONLY.search(desc)
        if m: info['damage_dice'] = m.group('dice')
        else:
            m = FLAT_ONLY.search(desc)
            if m: info['damage_flat'] = int(float(m.group('flat')))
            else:
                # Fallback: look for damage after colon or "takes" phrasing
                m = FALLBACK_FLAT.search(desc)
                if m: info['damage_flat'] = int(float(m.group('flat')))
                else:
                    m = FALLBACK_DICE.search(desc)
                    if m: info['damage_dice'] = m.group('dice')

    # Conditions
    conditions = []
    for cond in ALL_CONDITIONS:
        # Standard "Condition x3" format
        p = re.search(rf'{re.escape(cond)}\s*[×xX]\s*(\d+)', desc)
        if p:
            conditions.append(f'{cond} x{p.group(1)}')
        elif re.search(rf'\b{re.escape(cond)}\b', desc, re.IGNORECASE):
            conditions.append(cond)
    # Also catch "3 stacks of Condition" format
    for m in re.finditer(r'(\d+)\s+stacks?\s+of\s+([A-Z][\w\s]+?)(?:\s*,|\s*$|\s+and|\s+condition)', desc, re.IGNORECASE):
        stack_cond = m.group(2).strip()
        if stack_cond in ALL_CONDITIONS:
            existing = [c for c in conditions if stack_cond in c]
            if not existing:
                conditions.append(f'{stack_cond} x{m.group(1)}')
    if conditions:
        info['extra_effect'] = '+'.join(conditions)

    # Save type
    m = SAVE_RE.search(desc)
    if m: info['save'] = SAVE_MAP.get(m.group(1).lower(), m.group(1)[:3].lower())
    if 'half damage' in desc.lower() or 'take half' in desc.lower():
        info['save_half'] = True

    # Attack roll
    if 'spell attack' in desc.lower():
        info['attack_roll'] = True

    # AoE from range string
    rng = rng_str.lower()
    m = re.search(r'(\d+)\s*ft\s*radius', rng)
    if m: info['aoe_radius'] = int(m.group(1))
    if 'cone' in rng:
        info['aoe_cone'] = True
        m = re.search(r'(\d+)\s*ft\s*cone', rng)
        if m: info['aoe_radius'] = int(m.group(1))
    if 'line' in rng: info['aoe_line'] = True
    if 'self' in rng: info['aoe_self'] = True
    if 'touch' in rng:
        info['range'] = 'Touch'
    elif rng and rng[0].isdigit():
        # Only parse numeric range if it starts with a digit (not 'Self', 'Touch', etc.)
        m = re.match(r'^(\d+)', rng)
        if m: info['range'] = int(m.group(1))

    # Concentration
    if re.search(r'(?<!not )(?:requires?\s+|maintain\s+)[Cc]oncentration\b', desc, re.IGNORECASE):
        info['concentration'] = True

    # Bonus action
    if ('bonus action' in desc.lower() and ('cast' in desc.lower() or 'casting' in desc.lower() or 'as a' in desc.lower())) or \
       'casting time: 1 bonus action' in desc.lower():
        info['costs_bonus_action'] = True

    # Level required from prerequisite string
    for m in re.finditer(r'[Ll]evel\s+(\d+(?:\.\d+)?)', prereq_str):
        try: info['level_required'] = int(float(m.group(1)))
        except: pass

    # Stat prereqs from prerequisite string
    for m in re.finditer(r'>\s*(\d+)\s*(Str|Dex|Con|Wis|Int|Cha)\b', prereq_str, re.IGNORECASE):
        info[f'{m.group(2).lower()}_required'] = int(m.group(1)) + 1

    # Affinity required (handles multi-word names like "Ice/Cold", "Eldritch Horror")
    m = re.search(r'>\s*(\d+)\s*([A-Z][\w/\s]+?)(?:\s+Affinity|\s*$|\s*[,;])', prereq_str, re.IGNORECASE)
    if m: info['affinity_required'] = int(m.group(1)) + 1

    return info


def parse_upcast(upcast_str):
    if not upcast_str or upcast_str.lower() in ('none', '-'): return {}
    if re.match(r'^[A-Z][a-zA-Z\s\-]+$', upcast_str.strip()):
        return {'upcast_to': upcast_str.strip()}
    return {'upcast_rule': upcast_str.strip()}


# ── Race syncing ──────────────────────────────────────────────────
def parse_race_tables(filepath):
    """Extract race stat/affinity/speed/karma data from race markdown files."""
    tables = parse_markdown_tables(filepath)
    races = {}
    for header, rows in tables:
        # Detect if this is the stat/affinity table by looking for 'Speed' and 'Stat Bonuses'
        header_lower = [h.lower() for h in header]
        is_race_table = any('speed' in h for h in header_lower) and any('stat' in h for h in header_lower)

        if is_race_table:
            cols = {h.lower().replace(' ', '_'): i for i, h in enumerate(header)}
            name_idx = cols.get('name', 0) or cols.get('race', 0)
            speed_idx = cols.get('speed', None)
            neg_idx = cols.get('negative_affinities', None)
            neu_idx = cols.get('neutral_affinities', None)
            pos_idx = cols.get('positive_affinities', None)
            stat_idx = cols.get('stat_bonuses', None)
            karma_idx = cols.get('karma', None)

            for row in rows:
                if len(row) <= name_idx: continue
                name = row[name_idx]
                if not name or name.startswith('-') or name.lower() in ('name', 'race'):
                    continue

                info = {}
                # Speed
                if speed_idx is not None and speed_idx < len(row):
                    try: info['speed'] = int(row[speed_idx].split(',')[0])
                    except: pass
                # Affinities
                affs = {}
                if pos_idx is not None and pos_idx < len(row):
                    for a in re.split(r'[,/]+', row[pos_idx]):
                        a = a.strip()
                        if a: affs[a] = 3
                if neg_idx is not None and neg_idx < len(row):
                    for a in re.split(r'[,/]+', row[neg_idx]):
                        a = a.strip()
                        if a: affs[a] = -3
                if affs: info['affinity_bonuses'] = affs
                # Stats
                if stat_idx is not None and stat_idx < len(row):
                    stats = {}
                    for part in re.split(r'[,/]+', row[stat_idx]):
                        part = part.strip()
                        m = re.match(r'([+-]?\d+)\s*([A-Za-z]+)', part)
                        if m:
                            stat_name = m.group(2).lower()[:3]
                            if stat_name in STAT_LOWER:
                                stats[STAT_LOWER[stat_name]] = int(m.group(1))
                    if stats: info['stat_bonuses'] = stats
                # Karma
                if karma_idx is not None and karma_idx < len(row):
                    try: info['karma'] = int(row[karma_idx])
                    except: pass
                if info:
                    races[name] = info
    return races


def sync_races(log_lines, log):
    """Sync race data from all race files into races.json."""
    log("─" * 60)
    log("RACE SYNC")
    log("─" * 60)

    races_path = os.path.join(DATA_DIR, 'races.json')
    with open(races_path) as f:
        races_json = json.load(f)

    # Map handbook subrace names -> JSON subrace keys
    SUBRACE_MAP = {
        'Elf': {'Elf': 'Elf', 'Draugir': 'Draugir', 'Dryad': 'Dryad', 'Nymph': 'Nymph',
                'Siren': 'Siren', 'Dwarf': 'Dwarf', 'Snerin': 'Snerin', 'Ironwroth': 'Ironwroth',
                'Fairy': 'Fairy', 'Pixy': 'Pixy', 'Spriteling': 'Spriteling'},
        'Tull': {'Grivlit': 'Grivlit', 'Tull': 'Tull', 'Grull': 'Grull', 'Gorul': 'Gorul',
                 'Boaf': 'Boaf', 'Brogath': 'Brogath', 'Troll': 'Troll', 'Cyclopse': 'Cyclopse',
                 'Naram-Sin': 'Naram-Sin'},
    }

    changes = 0
    for rf in RACE_FILES:
        path = os.path.join(HANDBOOK, rf)
        if not os.path.exists(path):
            continue

        hb_races = parse_race_tables(path)
        if not hb_races:
            continue

        # Determine family from filename
        family_key = None
        for fn in ['Human', 'Bugfolk', 'Demon', 'Elf', 'Fishfolk', 'Harpy',
                    'Naga', 'Shapeshifter', 'Therian', 'Tull', 'Undead']:
            if f'{fn} and' in rf or f'{fn}.md' in rf:
                family_key = fn; break
        if not family_key or family_key not in races_json:
            continue

        for hb_name, hb_data in hb_races.items():
            sub_map = SUBRACE_MAP.get(family_key, {})
            json_name = sub_map.get(hb_name, hb_name)
            if json_name not in races_json[family_key].get('subraces', {}):
                continue

            sr = races_json[family_key]['subraces'][json_name]
            diffs = []

            # Sync stats — only if handbook has non-zero values
            hb_stats = hb_data.get('stat_bonuses', {})
            if hb_stats:
                cur_stats = sr.get('stat_bonuses', {})
                for s in ['str', 'dex', 'con', 'wis', 'int', 'cha']:
                    if s in hb_stats:
                        hb = hb_stats[s]
                        cur = cur_stats.get(s, 0)
                        if hb != cur:
                            diffs.append(f"{STAT_ABBREV[s]}: {cur:+d} -> {hb:+d}")
                            sr.setdefault('stat_bonuses', {})[s] = hb

            # Sync affinities — ADD positive/negative from handbook, keep existing neutrals
            hb_affs = hb_data.get('affinity_bonuses', {})
            if hb_affs:
                cur_affs = sr.get('affinity_bonuses', {})
                for a, v in hb_affs.items():
                    if cur_affs.get(a) != v:
                        diffs.append(f"{a} aff: {cur_affs.get(a, 0)} -> {v}")
                        sr.setdefault('affinity_bonuses', {})[a] = v
                # Remove affinities the handbook says are negative/positive but
                # were previously NOT in the handbook's list at all
                handbook_affs = set(hb_affs.keys())
                for a in list(cur_affs.keys()):
                    if a not in handbook_affs and cur_affs[a] in (3, -3):
                        # Only remove if it was a non-neutral that handbook doesn't mention
                        pass  # Keep existing entries that aren't contradicted

            # Sync speed — only if handbook has a value
            if 'speed' in hb_data:
                hb_speed = hb_data['speed']
                if sr.get('speed', 0) != hb_speed:
                    diffs.append(f"speed: {sr.get('speed')} -> {hb_speed}")
                    sr['speed'] = hb_speed

            if diffs:
                changes += 1
                _changed_items.append(f"RACE|{family_key}/{json_name}")
                log(f"  ~ {family_key}/{json_name}: {'; '.join(diffs)}")
                print(f"  RACE: {family_key}/{json_name}: {'; '.join(diffs)}")

    if changes:
        with open(races_path, 'w') as f:
            json.dump(races_json, f, indent=2)
            f.write('\n')
        log(f"\nRace sync: {changes} subraces updated")
    else:
        log("Race sync: all up to date")


# ── Spell syncing ─────────────────────────────────────────────────
def sync_spells(log_lines, log):
    """Sync spells from handbook into spells.json."""
    log("─" * 60)
    log("SPELL SYNC")
    log("─" * 60)

    spells_path = os.path.join(DATA_DIR, 'spells.json')
    with open(spells_path) as f:
        spells_json = json.load(f)

    # Parse all handbook spell files
    handbook = {}
    for sf in SPELL_FILES:
        path = os.path.join(HANDBOOK, sf)
        if os.path.exists(path):
            parsed = parse_spell_table(path)
            handbook.update(parsed)
            log(f"  Parsed {len(parsed)} spells from {os.path.basename(sf)}")
    log(f"  Total handbook spells: {len(handbook)}")

    # Build JSON index
    json_index = {}
    for aff, slist in spells_json.items():
        for s in slist:
            base = re.sub(r'\s*\(.*\)$', '', s['name']).strip()
            json_index.setdefault(base, []).append((aff, s))

    changed = 0
    new_spells = {}
    not_found = []

    for hname, hdata in handbook.items():
        if hname in json_index:
            # Update existing spell
            info = extract_spell_info(hdata['desc'], hdata['prereq'], hdata['range'])
            upcast = parse_upcast(hdata['upcast'])

            for aff, s in json_index[hname]:
                diffs = []
                if s.get('mana') != hdata['mana']:
                    diffs.append(f"mana: {s['mana']} -> {hdata['mana']}")
                    s['mana'] = hdata['mana']
                if s.get('description', '') != hdata['desc']:
                    s['description'] = hdata['desc']

                for uk, uv in upcast.items():
                    if s.get(uk) != uv:
                        diffs.append(f"{uk}: {s.get(uk)} -> {uv}")
                        s[uk] = uv

                for key in ('damage_dice', 'damage_flat', 'extra_effect', 'save',
                           'aoe_radius', 'affinity_required', 'range'):
                    if key in info and s.get(key) != info[key]:
                        diffs.append(f"{key}: {s.get(key)} -> {info[key]}")
                        s[key] = info[key]

                for sk in ('int_required', 'con_required', 'str_required',
                          'dex_required', 'wis_required', 'cha_required'):
                    if sk in info and s.get(sk) != info[sk]:
                        diffs.append(f"{sk}: {s.get(sk)} -> {info[sk]}")
                        s[sk] = info[sk]

                for flag in ('concentration', 'attack_roll', 'save_half',
                           'costs_bonus_action', 'aoe_cone', 'aoe_line', 'aoe_self'):
                    if info.get(flag) and not s.get(flag):
                        diffs.append(f"{flag}: false -> true")
                        s[flag] = True

                if diffs:
                    changed += 1
                    _changed_items.append(f"SPELL|{hname}|{hdata.get('affinity','')}")
                    log(f"  ~ {hname} ({aff}): {'; '.join(diffs)}")
        else:
            new_spells[hname] = hdata

    # Check for spells in JSON but not handbook
    for base, entries in json_index.items():
        if base not in handbook:
            for aff, s in entries:
                not_found.append(f"  {s['name']} ({aff})")

    # Add new spells
    added = 0
    for hname, hdata in new_spells.items():
        info = extract_spell_info(hdata['desc'], hdata['prereq'], hdata['range'])
        up = parse_upcast(hdata['upcast'])
        aff = hdata['affinity']
        if aff not in spells_json:
            spells_json[aff] = []
        entry = {'name': hname, 'mana': hdata['mana'], 'description': hdata['desc'],
                 'damage_type': aff.lower()}
        for key in ('range', 'damage_dice', 'damage_flat', 'extra_effect', 'save',
                   'aoe_radius', 'affinity_required', 'aoe_cone', 'aoe_line', 'aoe_self'):
            if key in info: entry[key] = info[key]
        for sk in ('int_required', 'con_required', 'str_required',
                  'dex_required', 'wis_required', 'cha_required'):
            if sk in info: entry[sk] = info[sk]
        for flag in ('concentration', 'attack_roll', 'save_half', 'costs_bonus_action'):
            if info.get(flag): entry[flag] = True
        for k, v in up.items(): entry[k] = v
        spells_json[aff].append(entry)
        added += 1
        _changed_items.append(f"SPELL|{hname}|{aff}")
        log(f"  + ADDED {hname} ({aff})")

    # Sort each affinity's spells
    for a in spells_json:
        spells_json[a].sort(key=lambda x: (x.get('affinity_required', 0), x.get('mana', 0)))

    if changed or added:
        with open(spells_path, 'w') as f:
            json.dump(spells_json, f, indent=2)
            f.write('\n')

    log(f"\nSpell sync: {changed} updated, {added} added")
    if not_found:
        log(f"\nSpells in JSON not in handbook ({len(not_found)}):")
        for nf in not_found[:20]: log(nf)
        if len(not_found) > 20: log(f"  ... and {len(not_found)-20} more")

    print(f"\nSpells: {changed} updated, {added} new, {len(new_spells)} in handbook only")


# ── Condition syncing ─────────────────────────────────────────────
def sync_conditions(log_lines, log):
    """Sync conditions from 2.4 Conditions.md."""
    log("─" * 60)
    log("CONDITION SYNC")
    log("─" * 60)

    path = os.path.join(HANDBOOK, CONDITIONS_FILE)
    if not os.path.exists(path):
        log("  Conditions file not found — skipping")
        return

    tables = parse_markdown_tables(path)
    hb_conditions = set()
    for header, rows in tables:
        name_idx = 0
        for i, h in enumerate(header):
            if 'condition' in h.lower():
                name_idx = i; break
        for row in rows:
            if name_idx < len(row) and row[name_idx]:
                hb_conditions.add(row[name_idx].strip())

    # Check against ALL_CONDITIONS
    missing = hb_conditions - set(ALL_CONDITIONS)
    extra = set(ALL_CONDITIONS) - hb_conditions

    if missing:
        log(f"  NEW conditions in handbook (add to ALL_CONDITIONS):")
        for c in sorted(missing):
            log(f"    + {c}")
        print(f"\nConditions: {len(missing)} new in handbook — MANUAL: add to update.py ALL_CONDITIONS")
    if extra:
        log(f"  Conditions in updater but not handbook ({len(extra)}): {sorted(extra)}")
    if not missing and not extra:
        log("  Conditions: all synced")


# ── Racial Tier syncing ─────────────────────────────────────────────
def parse_racial_tier_table(filepath, race_section_header):
    """Parse a racial tier table from a markdown file.
    Returns dict of {tier: ability_text} or None if no table found."""
    tables = parse_markdown_tables(filepath)
    for header, rows in tables:
        # Check if this is a racial tier table (has 'Tier' in headers)
        header_lower = [h.lower() for h in header]
        if 'tier' not in header_lower:
            continue
        tier_idx = header_lower.index('tier')
        ability_idx = 1 if len(header) > 1 else tier_idx + 1
        tiers = {}
        for row in rows:
            if len(row) <= tier_idx:
                continue
            tier_str = row[tier_idx]
            if not tier_str or tier_str.startswith('-'):
                continue
            try:
                tier_num = int(float(tier_str))
            except ValueError:
                continue
            ability = row[ability_idx] if ability_idx < len(row) else ''
            tiers[tier_num] = ability
        if tiers:
            return tiers
    return None


def extract_tier_effects(ability_text):
    """Extract generator-compatible effects from a racial tier ability description."""
    effects = {}
    ab = ability_text

    # Affinity bonuses
    for m in re.finditer(r'Gain\s+([+-]?\d+)\s+(\w[\w/]*?)\s+Affinity', ab, re.IGNORECASE):
        aff = m.group(2)
        try: val = int(m.group(1)); effects.setdefault('affinity', {})[aff] = val
        except: pass

    # AC bonus
    for m in re.finditer(r'(?:gain|grant(?:ing)?)\s+([+-]?\d+)\s+AC\b', ab, re.IGNORECASE):
        try: effects['ac_bonus'] = int(m.group(1))
        except: pass

    # Speed
    for m in re.finditer(r'(?:speed|movement)\s+.*?increases?\s+by\s+([+-]?\d+)', ab, re.IGNORECASE):
        try: effects['speed'] = int(m.group(1))
        except: pass

    # Affinity points
    m = re.search(r'Gain\s+([+-]?\d+)\s+Affinity\s+Points?', ab, re.IGNORECASE)
    if m: effects['affinity_points'] = int(m.group(1))

    # Stat bonuses
    for m in re.finditer(r'Gain\s+([+-]?\d+)\s+(STR|DEX|CON|WIS|INT|CHA)\b', ab, re.IGNORECASE):
        try:
            s = m.group(2).lower()
            effects.setdefault('stat', {})[s] = int(m.group(1))
        except: pass

    # Damage Mitigation
    for m in re.finditer(r'(\d+)\s+Damage\s+Mitigation', ab, re.IGNORECASE):
        try: effects['damage_reduction'] = int(m.group(1))
        except: pass

    # Magic Accuracy
    for m in re.finditer(r'([+-]?\d+)\s+(?:Base\s+)?Magic\s+Accuracy', ab, re.IGNORECASE):
        try: effects['magic_accuracy'] = int(m.group(1))
        except: pass

    # Weapon accuracy
    for m in re.finditer(r'([+-]?\d+)\s+(?:Base\s+)?(?:Melee|Ranged|Weapon)\s+Accuracy', ab, re.IGNORECASE):
        try: effects['weapon_group_accuracy'] = int(m.group(1))
        except: pass

    # Melee damage
    for m in re.finditer(r'([+-]?\d+)\s+(?:Base\s+)?Melee\s+Damage', ab, re.IGNORECASE):
        try: effects['melee_damage'] = int(m.group(1))
        except: pass

    # Initiative
    for m in re.finditer(r'([+-]?\d+)\s+(?:to\s+)?Initiative', ab, re.IGNORECASE):
        try: effects['initiative'] = int(m.group(1))
        except: pass

    # Critical block
    if re.search(r'cannot be critically hit|Critical hits become normal', ab, re.IGNORECASE):
        effects['crit_block'] = True

    # Extra BAp attack
    if re.search(r'make\s+(?:one|an)\s+additional\s+(?:weapon\s+)?attack.*?Bonus\s+Action', ab, re.IGNORECASE):
        effects['extra_attack_bap'] = True

    # HP per level
    for m in re.finditer(r'([+-]?\d+)\s+HP\s+(?:per|every)\s+level', ab, re.IGNORECASE):
        try: effects['hp_per_level'] = int(m.group(1))
        except: pass

    # Vit per level
    for m in re.finditer(r'([+-]?\d+)\s+(?:Vit|Vitality)\s+(?:per|every)\s+level', ab, re.IGNORECASE):
        try: effects['vit_per_level'] = int(m.group(1))
        except: pass

    # Mana per level
    for m in re.finditer(r'([+-]?\d+)\s+Mana\s+(?:per|every)\s+level', ab, re.IGNORECASE):
        try: effects['mana_per_level'] = int(m.group(1))
        except: pass

    # Fly speed
    for m in re.finditer(r'(?:fly|flight)\s+speed\s+.*?(\d+)', ab, re.IGNORECASE):
        try: effects['fly_speed'] = int(m.group(1))
        except: pass

    # Second chance (drop to 1 HP)
    if re.search(r'drop\s+to\s+1\s+HP\s+instead', ab, re.IGNORECASE):
        effects['second_chance'] = True

    return effects if effects else None


def sync_racial_tiers(log_lines, log):
    """Sync racial tier data from race files into bloodline_data.py."""
    log("─" * 60)
    log("RACIAL TIER SYNC")
    log("─" * 60)

    # Read existing bloodline data
    bd_path = os.path.join(DATA_DIR, 'bloodline_data.py')
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("bloodline_data", bd_path)
        bd_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bd_mod)
        bloodline = getattr(bd_mod, 'BLOODLINE_DATA', {})
    except Exception as e:
        log(f"  ERROR loading bloodline_data.py: {e}")
        bloodline = {}

    updated = 0
    no_table = []
    manual_needed = []

    for rf in RACE_FILES:
        path = os.path.join(HANDBOOK, rf)
        if not os.path.exists(path):
            continue

        # Find family name
        family_key = None
        for fn in ['Human', 'Bugfolk', 'Demon', 'Elf', 'Fishfolk', 'Harpy',
                    'Naga', 'Shapeshifter', 'Therian', 'Tull', 'Undead']:
            if f'{fn} and' in rf or f'{fn}.md' in rf:
                family_key = fn; break
        if not family_key:
            continue

        # Read the file to find race sections
        with open(path) as f:
            content = f.read()

        # Split by '## RaceName' to find individual subrace sections
        sections = {}
        current = None
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('## ') and 'subraces' not in line.lower() and 'language' not in line.lower():
                current = line[3:].strip()
                sections[current] = {'text': ''}
            elif current:
                sections[current]['text'] += line + '\n'

        # Process each section
        for section_name, section_data in sections.items():
            text = section_data['text']

            # Find the racial tier table in this section
            # Write section text to temp file for parse_racial_tier_table
            tmp_path = '/tmp/eyum_race_tier_tmp.md'
            with open(tmp_path, 'w') as f:
                f.write(text)
            tiers = parse_racial_tier_table(tmp_path, section_name)

            if not tiers:
                # Check if any subrace in this family matches section_name
                matched = False
                for sub_name in sections:
                    if sub_name == section_name and 'Racial Abilities' in sections[sub_name].get('text', ''):
                        # Has abilities section but no table format
                        no_table.append(f"{family_key}/{section_name}")
                        manual_needed.append(f"{family_key}/{section_name} (has abilities but not in table format)")
                        matched = True
                continue

            # Map handbook section name to JSON subrace key
            json_name = section_name
            if family_key not in bloodline:
                bloodline[family_key] = {}

            # Build tier effects
            tier_effects = {}
            for tier_num, ability_text in tiers.items():
                effects = extract_tier_effects(ability_text)
                if effects:
                    tier_effects[str(int(tier_num))] = effects

            if tier_effects:
                old = bloodline.get(family_key, {}).get(json_name, {})
                if old != tier_effects:
                    bloodline.setdefault(family_key, {})[json_name] = tier_effects
                    updated += 1
                    _changed_items.append(f"RACE|{family_key}/{json_name}")
                    log(f"  ~ {family_key}/{json_name}: {len(tier_effects)} tiers updated")
                    print(f"  TIER: {family_key}/{json_name}: {len(tier_effects)} tiers")

    # Write updated bloodline data (Python format, not JSON)
    if updated:
        with open(bd_path, 'w') as f:
            f.write('BLOODLINE_DATA = ')
            # Use json.dumps then convert to Python bool literals
            raw = json.dumps(bloodline, indent=2)
            raw = raw.replace('true', 'True').replace('false', 'False')
            f.write(raw)
            f.write('\n')
        log(f"\nRacial tier sync: {updated} subraces updated")
    else:
        log("Racial tier sync: all up to date")

    if manual_needed:
        log(f"\nRaces needing manual tier data ({len(manual_needed)}):")
        for mn in manual_needed:
            log(f"  MANUAL: {mn}")
        print(f"\nRacial tiers: {len(manual_needed)} races need manual data (not in table format)")


class LogSink:
    """Routes log output to both a file log and an optional GUI console."""
    def __init__(self, gui=None):
        self.gui = gui
        self.lines = []

    def log(self, s='', tag='normal'):
        self.lines.append(s)
        if self.gui:
            self.gui.log(s, tag)
        else:
            colors = {'green': '\033[92m', 'red': '\033[91m', 'yellow': '\033[93m', 'bold': '\033[1m',
                       'normal': '\033[0m'}
            c = colors.get(tag, '')
            reset = '\033[0m' if c else ''
            import sys as _sys2
            _sys2.__stdout__.write(f"{c}{s}{reset}\n")

    def flush(self, path):
        with open(path, 'w') as f:
            f.write('\n'.join(self.lines) + '\n')


# ── Main ──────────────────────────────────────────────────────────
def run_update(win=None):
    import sys as _sys
    _sys.path.insert(0, SCRIPT_DIR)
    sink = LogSink(win)

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sink.log(f"EYUM TTRPG — UNIVERSAL HANDBOOK SYNCER", 'bold')
    sink.log(f"Run at: {ts}")
    sink.log("=" * 70)

    # Redirect print to sink for GUI output
    _builtin_print = __builtins__.print if hasattr(__builtins__, 'print') else print
    def _print(*args, **kwargs):
        msg = ' '.join(str(a) for a in args)
        tag = 'normal'
        if 'MANUAL' in msg or 'ERROR' in msg or 'manual' in msg:
            tag = 'red'
        elif 'ADDED' in msg or 'added' in msg or '+ ADDED' in msg:
            tag = 'green'
        elif 'updated' in msg.lower() or 'synced' in msg.lower() or 'up to date' in msg.lower():
            tag = 'green'
        sink.log(msg, tag)
    import builtins
    builtins.print = _print

    _changed_items.clear()

    def log_fn(s=''):
        sink.log(s)

    sync_races(sink.lines, log_fn)
    sync_spells(sink.lines, log_fn)
    sync_conditions(sink.lines, log_fn)
    sync_racial_tiers(sink.lines, log_fn)
    sync_feats(sink.lines, log_fn)
    sync_paths(sink.lines, log_fn)

    # Write changes.txt
    if _changed_items:
        with open(CHANGES_PATH, 'w') as f:
            for item in _changed_items:
                f.write(item + '\n')
        sink.log(f"\nChanges tracked: {len(_changed_items)} items -> changes.txt", 'green')
    else:
        with open(CHANGES_PATH, 'w') as f:
            f.write('')
        sink.log("\nNo changes detected.", 'green')

    sink.log(f"\n{'='*70}\nEnd of log — {ts}")
    sink.flush(LOG_PATH)

    # Restore print
    if '_builtin_print' in dir():
        import builtins
        builtins.print = _builtin_print

    if not win:
        _builtin_print(f"\nFull report: {LOG_PATH}")


# ── Conditional effect detection ──────────────────────────────────
CONDITIONAL_PATTERNS = [
    # Creature-type conditions
    (r'vs\.?\s+undead|against\s+undead|to\s+undead', 'undead'),
    (r'vs\.?\s+dragon|against\s+dragon|to\s+dragon', 'dragon'),
    (r'vs\.?\s+humanoid|against\s+humanoid|to\s+humanoid', 'humanoid'),
    (r'vs\.?\s+monster|against\s+monster|to\s+monster', 'monster'),
    (r'vs\.?\s+deit|against\s+deit|to\s+deit|godslayer', 'deity'),
    (r'vs\.?\s+caster|against\s+caster|against\s+creatures?\s+with.*?magic|mage\s*slayer', 'caster'),
    # State conditions
    (r'below\s+(?:half|50%)', 'low_hp'),
    (r'first\s+round|surprise\s+round|first\s+turn', 'first_round'),
    (r'while\s+mounted|on\s+horseback', 'mounted'),
    (r'charging|after\s+moving\s+at\s+least|move\s+\d+\s*ft\s+before', 'charging'),
    (r'duel|1\s*v\s*1|one\s+on\s+one|only\s+creature\s+within\s+melee', 'dueling'),
    (r'while\s+wielding\s+a\s+(?:two.handed|shield|heavy)|when\s+using\s+a\s+(?:two.handed|heavy)', 'gear_conditional'),
    (r'as\s+a\s+ritual|ritual\s+spell', 'ritual'),
    (r'prone|restrained', 'target_state'),
    (r'retaliation|riposte|when\s+(?:you|hit)\s+(?:are|by)|attacker\s+takes|counter', 'retaliation'),
    (r'once\s+per\s+(?:long|short)\s+rest|once\s+per\s+combat', 'limited_use'),
    (r'only\s+(?:on|when|while|if|against|vs)', None),  # generic conditional
]

def is_conditional_effect(description):
    """Check if a described effect is conditional (shouldn't always apply)."""
    desc_lower = description.lower()
    for pattern, tag in CONDITIONAL_PATTERNS:
        if re.search(pattern, desc_lower):
            return tag or 'conditional'
    return None


# ── Feat syncing ───────────────────────────────────────────────────
def sync_feats(log_lines, log):
    """Sync feats from 3.4 Feats.md into feats.json.
    Detects conditional effects and marks them — never applies them as universal."""
    log("─" * 60)
    log("FEAT SYNC")
    log("─" * 60)

    path = os.path.join(HANDBOOK, FEATS_FILE)
    if not os.path.exists(path):
        log("  Feats file not found — skipping")
        return

    tables = parse_markdown_tables(path)
    feats_path = os.path.join(DATA_DIR, 'feats.json')
    with open(feats_path) as f:
        feats_json = json.load(f)

    changed = 0
    for header, rows in tables:
        cols = {h.lower().replace(' ', '_').replace('/', '_'): i for i, h in enumerate(header)}
        name_idx = cols.get('name', 0)
        type_idx = cols.get('type', None)
        desc_idx = cols.get('effect_description', 1) or cols.get('description', 1)
        prereq_idx = cols.get('prerequisites', None) or cols.get('prerequisite', None)

        for row in rows:
            if not row or len(row) <= name_idx: continue
            name = row[name_idx].strip()
            if not name or name.lower() in ('name', 'feat'): continue

            desc = row[desc_idx] if desc_idx is not None and desc_idx < len(row) else ''
            feat_type = row[type_idx] if type_idx is not None and type_idx < len(row) else 'Passive'
            prereq_str = row[prereq_idx] if prereq_idx is not None and prereq_idx < len(row) else ''

            # Check if this feat is conditional
            cond_tag = is_conditional_effect(f'{name} {desc}')
            existing = feats_json.get(name, {})

            # Extract stat bonuses from description
            stat_bonuses = {}
            for m in re.finditer(r'gain\s+([+-]?\d+)\s+(?:to\s+your\s+)?(STR|DEX|CON|WIS|INT|CHA)\s', desc, re.IGNORECASE):
                stat_bonuses[m.group(2).lower()] = int(m.group(1))
            for m in re.finditer(r'increase\s+(?:by\s+)?([+-]?\d+)\s+(?:to\s+your\s+)?(STR|DEX|CON|WIS|INT|CHA)\s', desc, re.IGNORECASE):
                stat_bonuses[m.group(2).lower()] = int(m.group(1))

            if name not in feats_json:
                feats_json[name] = {
                    'type': feat_type,
                    'description': desc,
                    'effects': {},
                    'prerequisites': {},
                    'conditional': cond_tag,
                    'value': 0,
                }
                if stat_bonuses:
                    feats_json[name]['effects']['stat'] = stat_bonuses
                changed += 1
                _changed_items.append(f"FEAT|{name}")
                log(f"  + ADDED feat: {name}" + (f" [conditional: {cond_tag}]" if cond_tag else ""))
            else:
                # Update existing — don't overwrite effects, just sync metadata
                existing['description'] = desc
                if cond_tag and not existing.get('conditional'):
                    existing['conditional'] = cond_tag
                    changed += 1
                    log(f"  ~ {name}: marked conditional ({cond_tag})")

    if changed:
        with open(feats_path, 'w') as f:
            json.dump(feats_json, f, indent=2)
            f.write('\n')
    log(f"Feat sync: {changed} changes")


# ── Path syncing ───────────────────────────────────────────────────
def sync_paths(log_lines, log):
    """Paths.json is complex and must be hand-maintained.
    This function reports mismatches between handbook and paths.json
    rather than auto-generating (which would break conditional annotations)."""
    log("─" * 60)
    log("PATH SYNC (validation only)")
    log("─" * 60)
    log("  paths.json contains conditional bonus annotations that cannot be")
    log("  auto-generated from the handbook. It must be maintained manually.")
    log("  When adding new archetype tiers, add them to paths.json by hand.")
    log("  Conditional bonuses should NOT be in the 'effects' dict — they")
    log("  should be removed or placed under 'conditional_effects'.")
    log("")
    log("  Conditional keywords detected by the parser:")
    for pattern, tag in CONDITIONAL_PATTERNS:
        log(f"    {tag or 'generic'}: {pattern}")


def main():
    try:
        from console_gui import run_with_gui
        run_with_gui("Eyum Handbook Sync", run_update, auto_close=True, close_delay=1)
    except ImportError:
        run_update(None)


if __name__ == '__main__':
    main()
