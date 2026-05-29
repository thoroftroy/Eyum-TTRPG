def resolve_gear(build_config, tier_config):
    gear = dict(build_config.get('gear', {}))
    tier_name = tier_config.get('name', '')

    if tier_name == 'no_gear':
        return {'weapon': None, 'armor': 'none'}

    if tier_name == 'bad_gear':
        return gear

    weapon = gear.get('weapon', '')
    armor = gear.get('armor', '')
    shield = gear.get('shield', '')

    if tier_name == 'nerite_gear':
        weapon_map = {
            'iron_longsword': 'nerite_longsword',
            'iron_greatsword': 'nerite_greatsword',
            'iron_shortbow': 'nerite_shortbow',
            'iron_longbow': 'nerite_longbow',
            'iron_halberd': 'nerite_halberd',
            'iron_staff': 'nerite_staff',
            'iron_dagger': 'nerite_dagger',
            'iron_focus': 'nerite_focus',
            'wand': 'nerite_wand',
            'quarterstaff': 'nerite_quarterstaff',
        }
        armor_map = {
            'none': 'nerite_none',
            'light': 'nerite_light',
            'medium': 'nerite_medium',
            'heavy': 'nerite_heavy',
        }
        shield_map = {
            'shield_medium': 'nerite_shield_medium',
            'shield_large': 'nerite_shield_large',
            'shield_heater': 'nerite_shield_heater',
        }
    elif tier_name == 'dragon_gear':
        weapon_map = {
            'iron_longsword': 'dragonbone_longsword',
            'iron_greatsword': 'dragonbone_greatsword',
            'iron_shortbow': 'dragonbone_shortbow',
            'iron_longbow': 'dragonbone_longbow',
            'iron_halberd': 'dragonbone_halberd',
            'iron_staff': 'dragonbone_staff',
            'iron_dagger': 'dragonbone_dagger',
            'iron_focus': 'dragonbone_focus',
            'wand': 'dragonbone_wand',
            'quarterstaff': 'dragonbone_quarterstaff',
        }
        armor_map = {
            'none': 'dragon_none',
            'light': 'dragon_light',
            'medium': 'dragon_medium',
            'heavy': 'dragon_heavy',
        }
        shield_map = {
            'shield_medium': 'dragon_shield_medium',
            'shield_large': 'dragon_shield_large',
            'shield_heater': 'dragon_shield_heater',
        }
    else:
        return gear

    result = {
        'weapon': weapon_map.get(weapon, weapon),
        'armor': armor_map.get(armor, armor),
    }
    if shield:
        result['shield'] = shield_map.get(shield, shield)
    return result
