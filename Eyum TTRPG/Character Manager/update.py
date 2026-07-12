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
SAVE_RE = re.compile(
    r'make\s+a(?:n)?\s+(Strength|Dexterity|Constitution|Wisdom|Intelligence|Charisma)\s+save',
    re.IGNORECASE)
SAVE_MAP = {s.lower(): s[:3].lower() for s in
            ['Strength','Dexterity','Constitution','Wisdom','Intelligence','Charisma']}

# ── Table parser ─────────────────────────────────────────────────
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
            cells = [c.strip() for c in tl.strip().split('|')]
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

    # Conditions
    conditions = []
    for cond in ALL_CONDITIONS:
        p = re.search(rf'{re.escape(cond)}\s*[×xX]\s*(\d+)', desc)
        if p:
            conditions.append(f'{cond} x{p.group(1)}')
        elif re.search(rf'\b{re.escape(cond)}\b', desc, re.IGNORECASE):
            conditions.append(cond)
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
    if 'touch' in rng: info['range'] = 'Touch'
    else:
        m = re.match(r'^(\d+)', rng)
        if m: info['range'] = int(m.group(1))

    # Concentration
    if re.search(r'(?<!not )\brequires\s+[Cc]oncentration\b', desc):
        info['concentration'] = True

    # Bonus action
    if 'bonus action' in desc.lower() and 'cast' in desc.lower():
        info['costs_bonus_action'] = True

    # Stat prereqs from prerequisite string
    for m in re.finditer(r'>\s*(\d+)\s*(Str|Dex|Con|Wis|Int|Cha)\b', prereq_str, re.IGNORECASE):
        info[f'{m.group(2).lower()}_required'] = int(m.group(1)) + 1

    # Affinity required
    m = re.search(r'>\s*(\d+)\s*([A-Z][\w/]+)\s*(?:Affinity)?', prereq_str, re.IGNORECASE)
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


# ── Main ──────────────────────────────────────────────────────────
def main():
    log_lines = []
    def log(s=''): log_lines.append(s)

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log(f"EYUM TTRPG — UNIVERSAL HANDBOOK SYNCER")
    log(f"Run at: {ts}")
    log("=" * 70)

    sync_races(log_lines, log)
    sync_spells(log_lines, log)
    sync_conditions(log_lines, log)

    log(f"\n{'='*70}\nEnd of log — {ts}")

    with open(LOG_PATH, 'w') as f:
        f.write('\n'.join(log_lines) + '\n')

    print(f"\nFull report: {LOG_PATH}")


if __name__ == '__main__':
    main()
