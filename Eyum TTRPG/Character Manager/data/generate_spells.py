import re
import json
import sys

sys.path.insert(0, '/tmp')
from spells_merged import spells

AFFINITY_UNLOCK = {
    "Psychic":     {"Radiant": 3, "Necrotic": 3},
    "Lightning":   {"Fire": 10, "Air": 10},
    "Steam":       {"Fire": 10, "Water": 10},
    "Magma":       {"Fire": 10, "Earth": 10},
    "Ice/Cold":    {"Air": 10, "Water": 10},
    "Dust":        {"Air": 10, "Earth": 10},
    "Mud":         {"Water": 10, "Earth": 10},
    "Nova":        {"Radiant": 10, "Fire": 10},
    "Solar":       {"Radiant": 10, "Earth": 10},
    "Starlight":   {"Radiant": 10, "Air": 10},
    "Ash":         {"Necrotic": 10, "Fire": 10},
    "Blight":      {"Necrotic": 10, "Earth": 10},
    "Poison":      {"Necrotic": 10, "Water": 10},
    "Toxin":       {"Necrotic": 10, "Air": 10},
    "Bloodfire":   {"Psychic": 10, "Fire": 10},
    "Shatter":     {"Psychic": 10, "Air": 10},
    "Sorrow":      {"Psychic": 10, "Radiant": 10},
    "Chaos":       {"Psychic": 10, "Necrotic": 10},
    "Infernal":    {"Force": 10, "Fire": 10},
    "Metal":       {"Force": 10, "Earth": 10},
    "Torrent":     {"Force": 10, "Water": 10},
    "Thunder":     {"Force": 10, "Air": 10},
    "Mirage":      {"Force": 10, "Radiant": 10},
    "Vacuum":      {"Force": 10, "Necrotic": 10},
    "Warp":        {"Force": 10, "Psychic": 10},
    "Storm":       {"Fire": 10, "Earth": 10, "Water": 10, "Air": 10},
    "Void":        {"Water": 10, "Air": 10, "Force": 10},
    "Obsidian":    {"Water": 10, "Air": 10, "Earth": 10, "Necrotic": 20},
    "Quake":       {"Earth": 10, "Air": 10, "Force": 10},
    "Corruption":  {"Radiant": 10, "Water": 10, "Air": 10, "Earth": 10, "Necrotic": 20},
    "Miasma":      {"Air": 10, "Water": 10, "Necrotic": 20},
    "Gel":         {"Water": 10, "Necrotic": 10, "Earth": 20},
    "Atomic":      {"Fire": 10, "Earth": 10, "Water": 10, "Air": 10, "Radiant": 10, "Necrotic": 10},
    "Eldritch":    {"Fire": 50, "Earth": 50, "Water": 50, "Air": 50, "Radiant": 50, "Necrotic": 50},
}


def get_damage_type(affinity_name):
    mapping = {
        "Special": None,
        "Generic": None,
        "HealingSpells": None,
        "Force": None,
        "Eldritch": None,
        "Ice/Cold": "cold",
    }
    return mapping.get(affinity_name, affinity_name.lower())


def parse_prerequisite(prereq, affinity_name):
    result = {}
    if not prereq or prereq == "None":
        return result
    if "The Healer" in prereq or "Eldritch Horror" in prereq or "Level" in prereq:
        return result
    if "Magical Path" in prereq or "1 Eldritch" in prereq:
        return result

    m = re.search(r'>(\d+)\s+in\s+any\s+affinity', prereq)
    if m:
        result['affinity_required'] = int(m.group(1))

    m = re.search(r'>(\d+)\s+in\s+at\s+least\s+(\d+)\s+affinities', prereq)
    if m:
        result['affinity_required'] = int(m.group(1))
        ep = result.get('extra_prereqs', {})
        ep['affinities_at'] = {str(result['affinity_required']): int(m.group(2))}
        result['extra_prereqs'] = ep

    m = re.search(r'>(\d+)\s+in\s+at\s+least\s+(\d+)\s+affinities?\s+and\s+>(\d+)\s+Int', prereq)
    if m:
        result['affinity_required'] = int(m.group(1))
        result['int_required'] = int(m.group(3))
        ep = result.get('extra_prereqs', {})
        ep['affinities_at'] = {str(result['affinity_required']): int(m.group(2))}
        result['extra_prereqs'] = ep

    m = re.search(r'>(\d+)\s+Int\s+and\s+>(\d+)\s+in\s+at\s+least\s+(\d+)\s+affinities', prereq)
    if m:
        result['int_required'] = int(m.group(1))
        result['affinity_required'] = int(m.group(2))
        ep = result.get('extra_prereqs', {})
        ep['affinities_at'] = {str(result['affinity_required']): int(m.group(3))}
        result['extra_prereqs'] = ep

    m = re.search(r'>(\d+)\s+Int', prereq)
    if m:
        result['int_required'] = int(m.group(1))

    escaped = re.escape(affinity_name)
    m = re.search(r'>(\d+)\s+' + escaped + r'(?:\s+Affinity)?', prereq, re.IGNORECASE)
    if m:
        result['affinity_required'] = int(m.group(1))

    return result


def parse_damage(damage_text):
    result = {}
    if not damage_text:
        return result

    if 'Affinity Mod' in damage_text:
        formula = damage_text.replace('(', '').replace(')', '').replace(' ', '').lower()
        formula = formula.replace('affinitymod', 'affinity_mod')
        result['damage_formula'] = formula
        return result

    dice_match = re.search(r'(\d+d\d+)', damage_text)
    if dice_match:
        result['damage_dice'] = dice_match.group(1)

    extra = extract_extra(damage_text, dice_match)
    if extra:
        result['extra_effect'] = extra

    return result


def extract_extra(damage_text, dice_match=None):
    if dice_match:
        rest = damage_text[dice_match.end():].strip()
    else:
        rest = damage_text

    rest = re.sub(r'^\+', '', rest).strip()
    rest = re.sub(r'\+\s*\d+d\d+(?:/[a-zA-Z]+)?(?:\s+\d+\s+(?:turns?|turn))?', '', rest).strip()
    rest = re.sub(r'\b\d+d\d+(?:/[a-zA-Z]+)?(?:\s+\d+\s+(?:turns?|turn|min|hr))?', '', rest).strip()
    rest = re.sub(r'\([^)]*\)', '', rest).strip()
    rest = re.sub(r'^\s*x\d+\s*,?\s*', '', rest).strip()
    rest = re.sub(r'\s+', ' ', rest).strip()

    if not rest:
        return None

    parts = [p.strip() for p in rest.split('+') if p.strip()]
    parts = [p[0].upper() + p[1:] if len(p) > 0 else p for p in parts]

    return '+'.join(parts) if parts else None


def parse_save(save_text):
    if not save_text or save_text == 'None':
        return None
    first_word = save_text.split()[0].lower()
    first_word = first_word.split('(')[0].strip()
    return first_word


def parse_aoe(aoe_text, range_text):
    result = {}
    if not aoe_text:
        return result

    aoe_lower = aoe_text.lower()

    if 'cone' in aoe_lower:
        result['aoe_cone'] = True
        m = re.search(r'(\d+)\s*ft', aoe_text)
        if m:
            result['aoe_radius'] = int(m.group(1))
        elif range_text:
            m = re.search(r'(\d+)\s*ft', range_text)
            if m:
                result['aoe_radius'] = int(m.group(1))
        return result

    if 'line' in aoe_lower:
        result['aoe_line'] = True
        m = re.search(r'(\d+)\s*ft', aoe_text)
        if m:
            result['aoe_radius'] = int(m.group(1))
        return result

    m = re.search(r'(\d+)\s*ft\s*(?:radius|burst|square|cube|cloud|aura|sphere|zone|splash|impact|wide|wall|line)', aoe_lower)
    if m:
        result['aoe_radius'] = int(m.group(1))
        return result

    m = re.search(r'(\d+)\s*ft', aoe_lower)
    if m:
        result['aoe_radius'] = int(m.group(1))

    return result


def convert_spell(spell, affinity_name):
    result = {'name': spell['name']}
    result['mana'] = spell['mana']

    prereq_result = parse_prerequisite(spell.get('prerequisite', ''), affinity_name)
    if 'affinity_required' in prereq_result:
        result['affinity_required'] = prereq_result['affinity_required']
    if 'int_required' in prereq_result:
        result['int_required'] = prereq_result['int_required']

    damage_result = parse_damage(spell.get('damage', ''))
    if 'damage_dice' in damage_result:
        result['damage_dice'] = damage_result['damage_dice']
    if 'damage_formula' in damage_result:
        result['damage_formula'] = damage_result['damage_formula']

    damage_type = get_damage_type(affinity_name)
    if damage_type:
        result['damage_type'] = damage_type

    save = parse_save(spell.get('save'))
    if save:
        result['save'] = save

    if spell.get('attack_roll'):
        result['attack_roll'] = True

    aoe_result = parse_aoe(spell.get('aoe'), spell.get('range'))
    result.update(aoe_result)

    rng = spell.get('range')
    if rng and str(rng).lower().startswith('self') and spell.get('aoe'):
        result['aoe_self'] = True

    if spell.get('concentration'):
        result['concentration'] = True

    if 'extra_effect' in damage_result:
        result['extra_effect'] = damage_result['extra_effect']

    if affinity_name in AFFINITY_UNLOCK:
        unlock_reqs = AFFINITY_UNLOCK[affinity_name]
        ep = result.get('extra_prereqs', {})
        ep['unlock'] = unlock_reqs
        result['extra_prereqs'] = ep

    if 'extra_prereqs' in result and not result['extra_prereqs']:
        del result['extra_prereqs']

    return result


def main():
    output = {}
    for affinity_name, spell_list in spells.items():
        output[affinity_name] = []
        for spell in spell_list:
            converted = convert_spell(spell, affinity_name)
            output[affinity_name].append(converted)

    output_path = '/home/microwavedthebaby/Documents/Eyum-TTRPG/Eyum TTRPG/Character Manager/data/spells.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    total = sum(len(v) for v in output.values())
    print(f"Total spells: {total}")
    print(f"Affinity groups: {len(output)}")
    print()
    for name, entries in sorted(output.items()):
        print(f"  {name}: {len(entries)} spells")


if __name__ == '__main__':
    main()
