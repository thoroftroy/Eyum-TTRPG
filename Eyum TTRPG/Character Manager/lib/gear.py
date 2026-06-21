"""
Dynamic gear selection using equipment.json rankings and character gold budget.
Returns weapons.json and armor_types.json compatible keys.
"""
import json, os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

TIER_BUDGETS = {
    'no_gear': 0,
    'bad_gear': 1,
    'good_gear': 100,
    'amazing_gear': 10000,
}

# Map gear tier to weapons.json prefix
TIER_PREFIX = {
    'bad_gear': 'iron_',
    'good_gear': 'nerite_',
    'amazing_gear': 'dragonbone_',
}

# Map gear tier to armor_types.json suffix (armor keys)
ARMOR_TIER_SUFFIX = {
    'bad_gear': '',          # just "light", "medium", etc.
    'good_gear': 'nerite_',  # "nerite_light", "nerite_medium", etc.
    'amazing_gear': 'dragon_', # "dragon_light", "dragon_medium", etc.
}

# Shield tier suffix
SHIELD_TIER_SUFFIX = {
    'bad_gear': '',
    'good_gear': 'nerite_',
    'amazing_gear': 'dragon_',
}

# Weapon name mapping: equipment.json weapon name -> weapons.json key suffix
# The prefix (iron_, nerite_, dragonbone_) is prepended based on tier
WEAPON_KEY_MAP = {
    'Longsword': 'longsword', 'Greatsword': 'greatsword', 'Shortsword': 'shortsword',
    'Dagger': 'dagger', 'Rapier': 'rapier', 'Scimitar': 'scimitar',
    'Handaxe': 'handaxe', 'Battleaxe': 'battleaxe', 'Greataxe': 'greataxe',
    'Warhammer': 'warhammer', 'Maul': 'maul', 'Morningstar': 'morningstar',
    'Flail': 'flail', 'Katar': 'katar', 'Khopesh': 'khopesh',
    'Nunchaku': 'nunchaku', 'Scythe': 'scythe', 'Whip': 'whip',
    'Spear': 'spear', 'Trident': 'trident', 'Halberd': 'halberd', 'Glaive': 'glaive',
    'Lance': 'lance', 'War Pick': 'war_pick', 'Sickle': 'sickle',
    'Greatclub': 'greatclub', 'Macuahuitl': 'macuahuitl',
    'Shortbow': 'shortbow', 'Longbow': 'longbow',
    'Light Crossbow': 'light_crossbow', 'Heavy Crossbow': 'heavy_crossbow',
    'Hand Crossbow': 'hand_crossbow', 'Sling': 'sling', 'Blowgun': 'blowgun',
    'Atlatl': 'atlatl', 'Chakram': 'chakram', 'Bolas': 'bolas',
    'Knuckles': 'knuckles', 'Fist': 'fist', 'Throwing Shield': 'throwing_shield',
    'Wand': 'wand', 'Quarterstaff': 'quarterstaff',
    # Focus isn't in weapons.json directly, use wand as fallback
}

# Armor key mapping
ARMOR_KEY_MAP = {
    'light': 'light', 'medium': 'medium', 'heavy': 'heavy',
    'none': 'none', 'None': 'none',
}

# Shield key mapping
SHIELD_KEY_MAP = {
    'Medium Shield': 'shield_medium', 'Large Shield': 'shield_large',
    'Heater Shield': 'shield_heater', 'Small Shield': 'shield_small',
    'Buckler': 'shield_buckler', 'Tower Shield': 'shield_tower',
    'Throwing Shield': 'shield_throwing', 'Kite Shield': 'shield_kite',
    'Targe': 'shield_targe', 'Aspis': 'shield_aspis',
    'Pavise': 'shield_pavise', 'Bouche Shield': 'shield_bouche',
}

def _load_equipment():
    paths = [
        os.path.join(DATA_DIR, 'equipment.json'),
        os.path.join(os.path.dirname(DATA_DIR), '..', 'dist', 'equipment.json'),
    ]
    for p in paths:
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            continue
    return None

_eq_cache = None
def get_equipment():
    global _eq_cache
    if _eq_cache is None:
        _eq_cache = _load_equipment()
    return _eq_cache


def select_gear(build_config, tier_name, level):
    """
    Pick best gear the character can afford. Returns dict with weapons.json and
    armor_types.json compatible keys like:
    {'weapon': 'nerite_longsword', 'armor': 'nerite_heavy', 'shield': 'nerite_shield_heater'}
    """
    if tier_name == 'no_gear':
        return {'weapon': None, 'armor': 'none'}

    eq = get_equipment()
    budget = TIER_BUDGETS.get(tier_name, 0) * level
    prefix = TIER_PREFIX.get(tier_name, 'iron_')
    armor_suffix = ARMOR_TIER_SUFFIX.get(tier_name, '')
    shield_suffix = SHIELD_TIER_SUFFIX.get(tier_name, '')
    orig_gear = build_config.get('gear', {})

    result = {}

    # --- Weapon ---
    weapon_name = orig_gear.get('weapon', 'iron_longsword')
    # Strip existing prefix to get base weapon name
    base_weapon = weapon_name
    for p in ['iron_', 'nerite_', 'dragonbone_']:
        if base_weapon.startswith(p):
            base_weapon = base_weapon[len(p):]
            break

    # Get best available weapon from equipment.json for this budget
    if eq:
        weapons = eq.get('weapons', [])
        candidates = [w for w in weapons
                      if w.get('weapon', '').lower() == base_weapon.replace('_', ' ').lower()
                      and w.get('price_gold', 999999) <= budget]
        if not candidates:
            # Fallback: any weapon of this type family
            family = [base_weapon]
            if base_weapon == 'longsword':
                family = ['Longsword', 'Greatsword', 'Shortsword']
            elif base_weapon in ('shortbow', 'longbow'):
                family = ['Longbow', 'Shortbow', 'Longsword']
            candidates = [w for w in weapons
                          if w['weapon'] in family
                          and w.get('price_gold', 999999) <= budget]
        if candidates:
            candidates.sort(key=lambda w: w.get('dpr_vs_ac16', 0), reverse=True)
            best = candidates[0]
            best_weapon_name = best['weapon']
            key_suffix = WEAPON_KEY_MAP.get(best_weapon_name)
            if key_suffix:
                result['weapon'] = prefix + key_suffix
            else:
                result['weapon'] = weapon_name  # fallback
        else:
            result['weapon'] = weapon_name
    else:
        result['weapon'] = weapon_name

    # --- Armor ---
    armor_type = orig_gear.get('armor', 'light')
    if armor_type == 'none':
        result['armor'] = 'none'
    else:
        result['armor'] = armor_suffix + armor_type if armor_suffix else armor_type

    # --- Shield ---
    shield_type = orig_gear.get('shield', '')
    if shield_type:
        # Extract base shield name (e.g., 'nerite_shield_medium' -> 'shield_medium')
        base_shield = shield_type
        for s in ['nerite_', 'dragon_']:
            if base_shield.startswith(s):
                base_shield = base_shield[len(s):]
                break
        result['shield'] = shield_suffix + base_shield if shield_suffix else base_shield
    else:
        result['shield'] = None

    return result


def resolve_gear(build_config, tier_config):
    """Legacy wrapper kept for backward compatibility."""
    tier_name = tier_config.get('name', '')
    if tier_name == 'no_gear':
        return {'weapon': None, 'armor': 'none'}
    if tier_name == 'bad_gear':
        return dict(build_config.get('gear', {}))
    # For other tiers, use select_gear at level 1
    return select_gear(build_config, tier_name, 1)
