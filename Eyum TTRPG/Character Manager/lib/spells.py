import math

AFFINITY_DAMAGE_BONUS_ATTRS = {
    'Fire': 'fire_damage_bonus',
    'Earth': 'earth_damage_bonus',
    'Water': 'water_damage_bonus',
    'Air': 'air_damage_bonus',
    'Radiant': 'radiant_damage_bonus',
    'Necrotic': 'necrotic_damage_bonus',
    'Psychic': 'psychic_damage_bonus',
}


def affinity_mod(affinity):
    return int(math.ceil((affinity - 2) / 2.0))


def avg_ac(proficiency):
    return 13 + min(5, proficiency // 6)


def avg_save_mod(proficiency):
    return proficiency + 3


def spell_save_dc(char, element):
    generic = char.affinities.get('Generic', 0)
    relevant = char.affinities.get(element, 0) if element else 0
    return 10 + generic + relevant


def get_best_affinity(char):
    best_aff = 0
    best_name = None
    for k, v in char.affinities.items():
        if k != 'Generic' and v > best_aff:
            best_aff = v
            best_name = k
    return best_name, best_aff


def check_spell_prereqs(char, spell, element, aff_val, affinity_prereqs=None):
    if spell.get('affinity_required', 0) > aff_val:
        return False
    if 'int_required' in spell and char.int < spell['int_required']:
        return False
    if affinity_prereqs and element and element in affinity_prereqs:
        prereq = affinity_prereqs[element]
        needs_all = prereq.get('needs_all', [])
        if needs_all:
            for tier in needs_all:
                for aff in tier.get('affinities', []):
                    if char.affinities.get(aff, 0) < tier.get('min_each', 0):
                        return False
        else:
            needs = prereq.get('needs', {})
            min_each = prereq.get('min_each', 0)
            affs = needs.get('all_of', []) or needs.get('any_of', [])
            if needs.get('any_of'):
                satisfied = any(char.affinities.get(aff, 0) >= min_each for aff in affs)
                if not satisfied:
                    return False
            else:
                for aff in affs:
                    if char.affinities.get(aff, 0) < min_each:
                        return False
    extra = spell.get('extra_prereqs', {})
    if 'affinities_at_10' in extra:
        count = sum(1 for v in char.affinities.values() if v >= 10)
        if count < extra['affinities_at_10']:
            return False
    if 'affinities_at' in extra:
        for threshold_str, required in extra['affinities_at'].items():
            threshold = int(threshold_str)
            count = sum(1 for v in char.affinities.values() if v >= threshold)
            if count < required:
                return False
    return True


def spell_avg_damage(spell, element, aff_val, die_avg, hit_chance, char=None, weapon_info=None):
    if 'damage_dice' in spell:
        dmg = die_avg.get(spell['damage_dice'], 0)
        dmg += spell.get('damage_flat', 0)
    elif 'damage_formula' in spell:
        formula = spell['damage_formula']
        if '+' in formula:
            parts = formula.split('+')
            base = int(parts[0])
            rest = parts[1]
            if 'affinity_mod' in rest:
                mod_val = affinity_mod(aff_val)
                div_parts = rest.split('/')
                if len(div_parts) > 1:
                    dmg = base + mod_val / float(div_parts[1])
                else:
                    dmg = base + mod_val
            elif '*' in rest:
                mul = int(rest.split('*')[1])
                dmg = base + aff_val * mul
            else:
                dmg = base + affinity_mod(aff_val)
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

    if spell.get('extra_effect') == 'Burned+DoT':
        dmg += die_avg.get('2d6', 7) * 2
    elif spell.get('extra_effect') == 'On Fire+GroundBurn':
        dmg += die_avg.get('2d6', 7) * 2
    elif spell.get('extra_effect') == 'Soaked+DoT':
        dmg += die_avg.get('2d6', 7) * 2

    if char and getattr(char, 'spell_damage_mult', 1) > 1:
        dmg *= char.spell_damage_mult

    return dmg


def select_spell(char, settings, max_mana=None):
    spells_data = settings.get('spells', {})
    die_avg = settings['rules']['die_averages']
    best_element, best_aff_val = get_best_affinity(char)
    weapons = settings.get('weapons', {})
    weapon_info = weapons.get(char.gear.get('weapon', ''), {})

    prof = getattr(char, 'prof', 1)
    target_ac = avg_ac(prof)
    target_save = avg_save_mod(prof)

    candidates = []

    magic_to_hit = char.to_hit_magic() if hasattr(char, 'to_hit_magic') else 0
    if magic_to_hit >= target_ac:
        spell_hit_chance = min(0.95, 1.0 - (target_ac - magic_to_hit - 1) / 20.0)
    else:
        spell_hit_chance = min(0.95, max(0.05, (21 - target_ac + magic_to_hit) / 20.0))

    mana_mult = getattr(char, 'spell_mana_mult', 1)
    affinity_prereqs = settings.get('rules', {}).get('affinity_prerequisites', {})

    primary = getattr(char, 'primary_affinity', None)
    primary_val = char.affinities.get(primary, 0) if primary else 0
    if primary and primary != best_element and primary in spells_data:
        primary_spells = spells_data[primary]
        for spell in primary_spells:
            if max_mana is not None and spell['mana'] * mana_mult > max_mana:
                continue
            if check_spell_prereqs(char, spell, primary, primary_val, affinity_prereqs):
                save = spell.get('save')
                if save:
                    dc = spell_save_dc(char, primary)
                    if spell.get('save_half', False):
                        fail_chance = min(0.95, max(0.05, (dc - 1 - target_save) / 20.0))
                        save_mul = fail_chance + (1 - fail_chance) * 0.5
                    else:
                        fail_chance = min(0.95, max(0.05, (dc - 1 - target_save) / 20.0))
                        save_mul = fail_chance
                    dmg = spell_avg_damage(spell, primary, primary_val, die_avg, spell_hit_chance, char, weapon_info)
                    dmg *= save_mul
                else:
                    dmg = spell_avg_damage(spell, primary, primary_val, die_avg, spell_hit_chance, char, weapon_info)
                if dmg > 0:
                    candidates.append((dmg, spell, primary))

    if best_element:
        elem_spells = spells_data.get(best_element, [])
        elem_aff_val = char.affinities.get(best_element, 0)
        for spell in elem_spells:
            if max_mana is not None and spell['mana'] * mana_mult > max_mana:
                continue
            if check_spell_prereqs(char, spell, best_element, elem_aff_val, affinity_prereqs):
                save = spell.get('save')
                if save:
                    aff_for_dc = elem_aff_val if spell.get('affinity_required', 0) > 0 else 0
                    dc = spell_save_dc(char, best_element)
                    if spell.get('save_half', False):
                        fail_chance = min(0.95, max(0.05, (dc - 1 - target_save) / 20.0))
                        save_mul = fail_chance + (1 - fail_chance) * 0.5
                    else:
                        fail_chance = min(0.95, max(0.05, (dc - 1 - target_save) / 20.0))
                        save_mul = fail_chance
                    dmg = spell_avg_damage(spell, best_element, elem_aff_val, die_avg, spell_hit_chance, char, weapon_info)
                    dmg *= save_mul
                else:
                    dmg = spell_avg_damage(spell, best_element, elem_aff_val, die_avg, spell_hit_chance, char, weapon_info)
                candidates.append((dmg, spell, best_element))

    for gname in ('Mana Decimation', 'Mana Explosion', 'Mana Bomb', 'Mana Bolt', 'Mana Blast'):
        gspell = None
        for s in spells_data.get('Generic', []):
            if s['name'] == gname:
                gspell = s
                break
        if not gspell:
            continue
        if max_mana is not None and gspell['mana'] * mana_mult > max_mana:
            continue
        if check_spell_prereqs(char, gspell, None, best_aff_val):
            save = gspell.get('save')
            if save:
                dc = spell_save_dc(char, best_element) if best_element else 0
                if gspell.get('save_half', False):
                    fail_chance = min(0.95, max(0.05, (dc - 1 - target_save) / 20.0))
                    save_mul = fail_chance + (1 - fail_chance) * 0.5
                else:
                    fail_chance = min(0.95, max(0.05, (dc - 1 - target_save) / 20.0))
                    save_mul = fail_chance
                dmg = spell_avg_damage(gspell, None, best_aff_val, die_avg, spell_hit_chance, char, weapon_info)
                dmg *= save_mul
            else:
                dmg = spell_avg_damage(gspell, None, best_aff_val, die_avg, spell_hit_chance, char, weapon_info)
            candidates.append((dmg, gspell, None))

    if not candidates:
        return None, 0

    if primary:
        primary_candidates = [c for c in candidates if c[2] == primary]
        if primary_candidates:
            candidates = primary_candidates
    best = max(candidates, key=lambda x: x[0])
    return {'spell': best[1], 'element': best[2], 'damage_per_cast': best[0]}, best[0]
