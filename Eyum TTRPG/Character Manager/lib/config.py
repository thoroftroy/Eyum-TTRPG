import json
import os


def load_settings(settings_dir=None):
    if settings_dir is None:
        settings_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    settings = {}
    files = {
        'rules': 'rules.json',
        'weapons': os.path.join('gear', 'weapons.json'),
        'armor_types': 'armor_types.json',
        'paths': 'paths.json',
        'gear_tiers': 'gear_tiers.json',
        'races': 'races.json',
        'builds': 'builds.json',
        'spells': 'spells.json',
        'feats': 'feats.json',
        'generation': 'generation.json',
    }
    for key, filename in files.items():
        path = os.path.join(settings_dir, filename)
        with open(path, 'r') as f:
            settings[key] = json.load(f)

    # Convert gear/weapons.json from array to dict keyed by weapon name
    # for backward compat with build pipeline lookups.
    # Also add tier-prefixed variants for iron/nerite/dragonbone.
    raw_weapons = settings.get('weapons', [])
    if isinstance(raw_weapons, list):
        weapon_dict = {}
        for w in raw_weapons:
            base_name = w['name'].lower().replace(' ', '_').replace('(', '').replace(')', '')
            # Base (iron) version
            iron_key = f"iron_{base_name}" if not base_name.startswith('iron_') else base_name
            entry = {
                'die': w.get('die'),
                'damage_type': w.get('dmg_type', '').lower(),
                'type': 'melee',
            }
            if 'Ranged' in w.get('categories', []):
                entry['type'] = 'ranged'
            if 'Magical' in w.get('categories', []):
                entry['type'] = 'magic'
            if w.get('magic_die'):
                entry['magic_damage_die'] = w['magic_die']
                entry['magic_bonus'] = 0
            weapon_dict[iron_key] = entry

            # Nerite version: +6 damage, +6 accuracy
            nerite_key = f"nerite_{base_name}"
            nerite_entry = dict(entry)
            nerite_entry['damage_bonus'] = 6
            nerite_entry['accuracy_bonus'] = 6
            if w.get('magic_die'):
                nerite_entry['magic_bonus'] = 6
            weapon_dict[nerite_key] = nerite_entry

            # Dragonbone version: +10 damage, +6 accuracy, +1d10 force
            dragon_key = f"dragonbone_{base_name}"
            dragon_entry = dict(entry)
            dragon_entry['damage_bonus'] = 10
            dragon_entry['accuracy_bonus'] = 6
            dragon_entry['extra_damage_die'] = '1d10'
            dragon_entry['extra_damage_type'] = 'force'
            if w.get('magic_die'):
                dragon_entry['magic_bonus'] = 10
                dragon_entry['extra_magic_damage_die'] = '1d10'
            weapon_dict[dragon_key] = dragon_entry

        # Special: wand and quarterstaff without prefix
        for special in ['wand', 'quarterstaff']:
            if f"iron_{special}" in weapon_dict:
                weapon_dict[special] = weapon_dict[f"iron_{special}"]

        settings['weapons'] = weapon_dict

    return settings
