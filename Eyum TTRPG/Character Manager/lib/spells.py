from .die_avg import die_average
from .character import dc_bonus_generic, dc_bonus_standard, affinity_mod

AFFINITY_DAMAGE_BONUS_ATTRS = {
    'Fire': 'fire_damage_bonus',
    'Earth': 'earth_damage_bonus',
    'Water': 'water_damage_bonus',
    'Air': 'air_damage_bonus',
    'Radiant': 'radiant_damage_bonus',
    'Necrotic': 'necrotic_damage_bonus',
    'Psychic': 'psychic_damage_bonus',
}

CONDITION_DMG = {
    'Burned': (2.5, 2), 'Burn': (2.5, 2), 'On Fire': (3.5, 3),
    'Bleeding': (2.5, 3), 'Bleed': (2.5, 3),
    'Necrosis': (4.5, 3), 'Diseased': (3.5, 2),
    'Shocked': (2.5, 2), 'Poisoned': (7.0, 3),
    'Corrupt': (2.5, 3), 'Hurting': (1.0, 3),
    'Suffocating': (3.5, 2), 'Frozen': (2.5, 2),
    'Slow Death': (2.5, 3), 'Frostbitten': (2.5, 3),
    'Hellfire': (4.5, 2), 'Radiation': (3.5, 3),
    'Withered': (7.5, 2), 'Plagued': (6.0, 3),
    'Eldritch Curse': (0, 2), 'Psychic Drain': (0, 2),
    'Storm Shocked': (2.5, 2),
    'Frostburned': (2.5, 3),
    'Taboo': (2.5, 3),
    'Prone': (0, 2), 'Slowed': (0, 2), 'Stunned': (0, 2),
    'Blinded': (0, 2), 'Mute': (0, 2), 'Deafened': (0, 2),
    'Frightened': (0, 2), 'Demoralized': (0, 2), 'Despair': (0, 2),
    'Enraged': (0, 2), 'Paralyzed': (0, 2), 'Petrified': (0, 2),
    'Entangled': (0, 2), 'Restrained': (0, 2), 'Pinned': (0, 2),
    'Blessed': (0, 2), 'Cursed': (0, 2), 'Soaked': (0, 2),
    'Difficult Terrain': (0, 2), 'Pierced': (0, 2), 'Push': (0, 0),
    'Pull': (0, 0), 'Heal': (0, 0), 'NoFlight': (0, 2),
    'NoAdvantage': (0, 2), 'DoT': (7.0, 2), 'GroundBurn': (7.0, 2),
    'Scaling': (0, 2), 'Collision': (0, 0),
    'Vibrating': (1.0, 3),
    'Nauseated': (0, 2), 'Charmed': (0, 2), 'Hypnotized': (0, 2),
    'Silenced': (0, 2), 'Hexed': (0, 2), 'Hexproof': (0, 2),
    'Blurred': (0, 2), 'Grounded': (0, 2), 'Purged': (0, 2),
    'Gelled': (0, 2), 'Pinned': (0, 2), 'Sickened': (0, 2),
    'Addicted': (0, 2), 'Overcrowded': (0, 2),
    'Arsenic Poisoning': (5.0, 3), 'Bromine Toxin': (4.5, 3),
    'Cancer': (0, 3), 'Paralytic Toxin': (2.5, 3),
    'Skorren Venom': (3.5, 3), 'Infernal Brand': (0, 2),
    'Infernal Ally Brand': (0, 2),
}


def _get_condition_damage(spell):
    extra = spell.get('extra_effect', '')
    if not extra:
        return 0, []
    total_dmg = 0
    conditions_found = []
    parts = [p.strip() for p in extra.split('+')]
    for part in parts:
        multiplier = 1
        cond_name = part
        if ' x' in part:
            cond_name, mult_str = part.rsplit(' x', 1)
            cond_name = cond_name.strip()
            try:
                multiplier = int(mult_str.strip())
            except ValueError:
                multiplier = 1
        if cond_name in CONDITION_DMG:
            dmg_per_tick, duration = CONDITION_DMG[cond_name]
            total_dmg += dmg_per_tick * duration * multiplier
            conditions_found.append(f'{cond_name} x{multiplier}' if multiplier > 1 else cond_name)
    return total_dmg, conditions_found


def avg_ac(proficiency):
    return 13 + min(5, proficiency // 6)


def avg_save_mod(proficiency):
    return proficiency + 3


def spell_save_dc(char, element):
    generic = char.affinities.get('Generic', 0)
    relevant = char.affinities.get(element, 0) if element else 0
    return 10 + dc_bonus_generic(generic) + dc_bonus_standard(relevant)


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


def spell_avg_damage(spell, element, aff_val, hit_chance, char=None, weapon_info=None):
    if 'damage_dice' in spell:
        dmg = die_average(spell['damage_dice'], 0)
        dmg += spell.get('damage_flat', 0)
    elif spell.get('damage_flat', 0) > 0:
        dmg = spell['damage_flat']
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
                    dmg += die_average(bonus_die, 0)

    if weapon_info:
        magic_die = weapon_info.get('magic_damage_die')
        if magic_die:
            dmg += die_average(magic_die, 0)
        extra_magic_die = weapon_info.get('extra_magic_damage_die')
        if extra_magic_die:
            dmg += die_average(extra_magic_die, 0)
        dmg += weapon_info.get('magic_bonus', 0)

    if spell.get('attack_roll'):
        dmg *= hit_chance

    cond_dmg, _ = _get_condition_damage(spell)
    dmg += cond_dmg
    if char and getattr(char, 'spell_damage_mult', 1) > 1:
        if spell.get('mana', 0) > 0:
            dmg = (dmg - cond_dmg) * char.spell_damage_mult + cond_dmg

    return dmg


def _add_spell_candidate(spell, element, aff_val, candidates, char, settings,
                         spell_hit_chance, target_save, max_mana, mana_mult,
                         affinity_prereqs, weapon_info):
    if not check_spell_prereqs(char, spell, element, aff_val if element else 0, affinity_prereqs):
        return

    save = spell.get('save')
    if save:
        dc = spell_save_dc(char, element) if element else 0
        if spell.get('save_half', False):
            fail_chance = min(0.95, max(0.05, (dc - 1 - target_save) / 20.0))
            save_mul = fail_chance + (1 - fail_chance) * 0.5
        else:
            fail_chance = min(0.95, max(0.05, (dc - 1 - target_save) / 20.0))
            save_mul = fail_chance
        dmg = spell_avg_damage(spell, element, aff_val, spell_hit_chance, char, weapon_info)
        dmg *= save_mul
    else:
        dmg = spell_avg_damage(spell, element, aff_val, spell_hit_chance, char, weapon_info)

    if dmg <= 0:
        return

    base_mana = spell['mana']
    multiplied_mana = base_mana * mana_mult
    affordable_mult = max_mana is None or multiplied_mana <= max_mana
    affordable_base = max_mana is None or base_mana <= max_mana

    if affordable_mult:
        candidates.append((dmg, spell, element, True))
    elif affordable_base and mana_mult > 1:
        base_dmg = dmg / getattr(char, 'spell_damage_mult', 1)
        if base_dmg > 0:
            candidates.append((base_dmg, spell, element, False))


def select_spell(char, settings, max_mana=None, exclude_concentration=False):
    spells_data = settings.get('spells', {})
    best_element, best_aff_val = get_best_affinity(char)
    weapons = settings.get('weapons', {})
    weapon_info = weapons.get(char.gear.get('weapon', ''), {})

    prof = getattr(char, 'prof', 1)
    target_ac = avg_ac(prof)
    target_save = avg_save_mod(prof)

    magic_to_hit = char.to_hit_magic() if hasattr(char, 'to_hit_magic') else 0
    if magic_to_hit >= target_ac:
        spell_hit_chance = min(0.95, 1.0 - (target_ac - magic_to_hit - 1) / 20.0)
    else:
        spell_hit_chance = min(0.95, max(0.05, (21 - target_ac + magic_to_hit) / 20.0))

    mana_mult = getattr(char, 'spell_mana_mult', 1)
    affinity_prereqs = settings.get('rules', {}).get('affinity_prerequisites', {})

    primary_candidates = []
    element_candidates = []
    generic_candidates = []

    primary = getattr(char, 'primary_affinity', None)
    primary_val = char.affinities.get(primary, 0) if primary else 0
    if primary and primary != best_element and primary in spells_data:
        for spell in spells_data[primary]:
            _add_spell_candidate(spell, primary, primary_val, primary_candidates, char, settings,
                                spell_hit_chance, target_save, max_mana, mana_mult,
                                affinity_prereqs, weapon_info)

    if best_element:
        sorted_affs = sorted(char.affinities.items(), key=lambda x: x[1] if x[0] != 'Generic' else -1, reverse=True)
        for aff_name, aff_val in sorted_affs:
            if aff_name == 'Generic':
                continue
            if aff_name not in spells_data:
                continue
            for spell in spells_data.get(aff_name, []):
                _add_spell_candidate(spell, aff_name, aff_val, element_candidates, char, settings,
                                    spell_hit_chance, target_save, max_mana, mana_mult,
                                    affinity_prereqs, weapon_info)
            if element_candidates:
                break

    for gname in ('Mana Decimation', 'Mana Explosion', 'Mana Bomb', 'Mana Bolt', 'Mana Blast'):
        gspell = None
        for s in spells_data.get('Generic', []):
            if s['name'] == gname:
                gspell = s
                break
        if not gspell:
            continue
        _add_spell_candidate(gspell, None, best_aff_val, generic_candidates, char, settings,
                            spell_hit_chance, target_save, max_mana, mana_mult,
                            affinity_prereqs, weapon_info)

    candidates = primary_candidates or element_candidates or generic_candidates

    if exclude_concentration and candidates:
        candidates = [c for c in candidates if not c[1].get('concentration')]
        if not candidates:
            candidates = primary_candidates or element_candidates or generic_candidates

    total_known = getattr(char, 'starting_spells', 0) + getattr(char, 'spells_from_levels', 0)
    total_known = max(1, total_known)
    if len(candidates) > total_known:
        candidates.sort(key=lambda x: x[0], reverse=True)
        candidates = candidates[:total_known]

    if not candidates:
        return None, 0

    # Pick the highest-damage castable spell from the primary/element candidates.
    # Sort by raw damage first, then by mana cost as tiebreaker for equal-damage spells.
    best = max(candidates, key=lambda x: (x[0], x[1].get('mana', 0)))
    use_mult = len(best) > 3 and best[3]
    cond_dmg, cond_names = _get_condition_damage(best[1])

    # Track skipped primary-affinity spells for summary reporting
    spell_skip_info = {}
    primary = getattr(char, 'primary_affinity', None)
    if primary and primary in spells_data:
        primary_spells = spells_data[primary]
        skipped = []
        primary_val = char.affinities.get(primary, 0)
        for ps in primary_spells:
            if ps['name'] == best[1]['name']:
                continue
            if not check_spell_prereqs(char, ps, primary, primary_val, affinity_prereqs):
                continue
            pdmg = spell_avg_damage(ps, primary, primary_val, spell_hit_chance, char, weapon_info)
            if pdmg <= 0:
                skipped.append({'name': ps['name'], 'mana': ps['mana'],
                               'reason': 'non_damaging', 'dmg': 0})
            elif pdmg < best[0] and pdmg > 0:
                skipped.append({'name': ps['name'], 'mana': ps['mana'],
                               'reason': 'lower_damage', 'dmg': pdmg, 'best_dmg': best[0]})
        if skipped:
            spell_skip_info = {'affinity': primary, 'skipped': skipped,
                              'chosen': best[1]['name'], 'chosen_dmg': best[0]}

    return {'spell': best[1], 'element': best[2], 'damage_per_cast': best[0],
            'use_multiplier': use_mult,
            'cond_dmg': cond_dmg, 'cond_names': cond_names,
            'extra_effect': best[1].get('extra_effect', ''),
            'skip_info': spell_skip_info}, best[0]
