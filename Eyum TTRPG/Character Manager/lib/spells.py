AFFINITY_DAMAGE_BONUS_ATTRS = {
    'Fire': 'fire_damage_bonus',
    'Earth': 'earth_damage_bonus',
    'Water': 'water_damage_bonus',
    'Air': 'air_damage_bonus',
    'Radiant': 'radiant_damage_bonus',
    'Necrotic': 'necrotic_damage_bonus',
}


def get_best_affinity(char):
    best_aff = 0
    best_name = None
    for k, v in char.affinities.items():
        if k != 'Generic' and v > best_aff:
            best_aff = v
            best_name = k
    return best_name, best_aff


def check_spell_prereqs(char, spell, element, aff_val):
    if spell.get('affinity_required', 0) > aff_val:
        return False
    if 'int_required' in spell and char.int < spell['int_required']:
        return False
    extra = spell.get('extra_prereqs', {})
    if 'affinities_at_10' in extra:
        count = sum(1 for v in char.affinities.values() if v >= 10)
        if count < extra['affinities_at_10']:
            return False
    return True


def spell_avg_damage(spell, element, aff_val, die_avg, hit_chance, char=None, weapon_info=None):
    if 'damage_dice' in spell:
        dmg = die_avg.get(spell['damage_dice'], 0)
    elif 'damage_formula' in spell:
        formula = spell['damage_formula']
        if '+' in formula:
            parts = formula.split('+')
            base = int(parts[0])
            rest = parts[1]
            if '*' in rest:
                mul = int(rest.split('*')[1])
                dmg = base + aff_val * mul
            else:
                dmg = base + aff_val
        else:
            dmg = int(formula)
    else:
        return 0

    if char:
        dmg += getattr(char, 'magic_damage', 0)
        if element and element != 'Generic':
            bonus_attr = AFFINITY_DAMAGE_BONUS_ATTRS.get(element)
            if bonus_attr:
                bonus_die = getattr(char, bonus_attr, None)
                if bonus_die:
                    dmg += die_avg.get(bonus_die, 0)

    if weapon_info:
        magic_die = weapon_info.get('magic_damage_die')
        if magic_die:
            dmg += die_avg.get(magic_die, 0)
        extra_magic_die = weapon_info.get('extra_magic_damage_die')
        if extra_magic_die:
            dmg += die_avg.get(extra_magic_die, 0)
        dmg += weapon_info.get('magic_bonus', 0)

    if spell.get('attack_roll'):
        dmg *= hit_chance
    elif 'save' in spell:
        save_fail = 0.5
        save_half_effect = spell.get('save_half', False) or (char and getattr(char, 'save_half_magic', False))
        if save_half_effect:
            dmg *= save_fail + (1 - save_fail) * 0.5
        else:
            dmg *= save_fail

    if spell.get('aoe_radius', 0) > 0 or spell.get('aoe_cone') or spell.get('aoe_line') or spell.get('aoe_self'):
        dmg *= 2

    if spell.get('extra_effect') == 'Burned+DoT':
        dmg += die_avg.get('2d6', 7) * 2
    elif spell.get('extra_effect') == 'On Fire+GroundBurn':
        dmg += die_avg.get('2d6', 7) * 2
    elif spell.get('extra_effect') == 'Soaked+DoT':
        dmg += die_avg.get('2d6', 7) * 2

    return dmg


def select_spell(char, settings, max_mana=None):
    spells_data = settings.get('spells', {})
    die_avg = settings['rules']['die_averages']
    best_element, best_aff_val = get_best_affinity(char)
    hit_chance = 1.0
    weapons = settings.get('weapons', {})
    weapon_info = weapons.get(char.gear.get('weapon', ''), {})

    candidates = []

    for elem_name, elem_spells in spells_data.items():
        if elem_name == 'Generic':
            continue
        elem_aff_val = char.affinities.get(elem_name, 0)
        for spell in elem_spells:
            if max_mana is not None and spell['mana'] > max_mana:
                continue
            if check_spell_prereqs(char, spell, elem_name, elem_aff_val):
                dmg = spell_avg_damage(spell, elem_name, elem_aff_val, die_avg, hit_chance, char, weapon_info)
                candidates.append((dmg, spell, elem_name))

    for gname in ('Mana Decimation', 'Mana Explosion', 'Mana Bomb', 'Mana Bolt', 'Mana Blast'):
        gspell = None
        for s in spells_data.get('Generic', []):
            if s['name'] == gname:
                gspell = s
                break
        if not gspell:
            continue
        if max_mana is not None and gspell['mana'] > max_mana:
            continue
        if check_spell_prereqs(char, gspell, None, best_aff_val):
            dmg = spell_avg_damage(gspell, None, best_aff_val, die_avg, hit_chance, char, weapon_info)
            candidates.append((dmg, gspell, None))

    if not candidates:
        return None, 0

    best = max(candidates, key=lambda x: x[0])
    return {'spell': best[1], 'element': best[2], 'damage_per_cast': best[0]}, best[0]
