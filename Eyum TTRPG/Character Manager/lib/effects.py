def apply_effects(char, effects):
    if not effects:
        return
    if 'stat' in effects:
        for stat_name, bonus in effects['stat'].items():
            if stat_name in ('str', 'dex', 'con', 'wis', 'int', 'cha'):
                current = getattr(char, stat_name)
                setattr(char, stat_name, current + bonus)
    if 'vit_die_type' in effects:
        char.vit_die = effects['vit_die_type']
    if 'hp_die_type' in effects:
        char.hp_die = effects['hp_die_type']
    if 'mana_die_type' in effects:
        char.mana_die = effects['mana_die_type']
    if 'ac_bonus' in effects:
        char.ac_bonus += effects['ac_bonus']
    if 'affinity' in effects:
        for aff, val in effects['affinity'].items():
            char.affinities[aff] = char.affinities.get(aff, 0) + val
    if 'affinity_points' in effects:
        char.affinity_points += effects['affinity_points']
    if 'spell' in effects:
        char.spells_from_levels += effects['spell']
    if 'mana_dice_count' in effects:
        char.mana_n += effects['mana_dice_count']
    if 'generic_affinity' in effects:
        char.affinities['Generic'] = char.affinities.get('Generic', 0) + effects['generic_affinity']
    if 'melee_damage' in effects:
        char.melee_damage += effects['melee_damage']
    if 'melee_accuracy' in effects:
        char.melee_accuracy += effects['melee_accuracy']
    if 'ranged_damage' in effects:
        char.ranged_damage += effects['ranged_damage']
    if 'ranged_accuracy' in effects:
        char.ranged_accuracy += effects['ranged_accuracy']
    if 'magic_accuracy' in effects:
        char.magic_accuracy += effects['magic_accuracy']
    if 'magic_damage' in effects:
        char.magic_damage += effects['magic_damage']
    if 'fire_damage_bonus' in effects:
        char.fire_damage_bonus = effects['fire_damage_bonus']
    if 'earth_damage_bonus' in effects:
        char.earth_damage_bonus = effects['earth_damage_bonus']
    if 'water_damage_bonus' in effects:
        char.water_damage_bonus = effects['water_damage_bonus']
    if 'air_damage_bonus' in effects:
        char.air_damage_bonus = effects['air_damage_bonus']
    if 'radiant_damage_bonus' in effects:
        char.radiant_damage_bonus = effects['radiant_damage_bonus']
    if 'necrotic_damage_bonus' in effects:
        char.necrotic_damage_bonus = effects['necrotic_damage_bonus']
    if 'skill_points' in effects:
        char.skill_points += effects['skill_points']
    if 'stat_points' in effects:
        char.stat_points += effects['stat_points']
    if 'stat_point' in effects:
        char.stat_points += effects['stat_point']
    if 'feat_per_feat' in effects:
        char.feat_per_feat += effects['feat_per_feat']
    if 'tier1_racial' in effects:
        char.tull_tier = max(char.tull_tier, 1)
    if 'tier_racial' in effects:
        char.tull_tier = max(char.tull_tier, effects['tier_racial'])
    if 'pack_tactics' in effects:
        char.pack_tactics = True
    if 'extra_attack_bap' in effects:
        char.extra_attack_bap = True
    if 'flat_vit' in effects:
        char.flat_vit += effects['flat_vit']
    if 'flat_hp' in effects:
        char.flat_hp += effects['flat_hp']
    if 'speed' in effects:
        char.speed = max(getattr(char, 'speed', 30), effects['speed'])
    if 'first_round_damage' in effects:
        char.first_round_damage = effects['first_round_damage']
    if 'ap_first_round' in effects:
        char.ap_first_round = effects['ap_first_round']
    if 'first_round_advantage' in effects:
        char.first_round_advantage = effects['first_round_advantage']
    if 'ranged_adv_damage' in effects:
        char.ranged_adv_damage_stacks += effects['ranged_adv_damage']
    if 'ranged_expertise' in effects:
        char.ranged_expertise = effects['ranged_expertise']


def apply_feat_effects(char, effects):
    if not effects:
        return
    if 'vit_per_level' in effects:
        char.vit_per_level_bonus += effects['vit_per_level']
    if 'hp_per_level' in effects:
        char.hp_per_level_bonus += effects['hp_per_level']
    if 'mana_per_level' in effects:
        char.mana_per_level_bonus += effects['mana_per_level']
    if 'ac_bonus' in effects:
        char.ac_bonus += effects['ac_bonus']
    if 'bap' in effects:
        char.bap += effects['bap']
    if 'rp' in effects:
        char.rp += effects['rp']
    if 'stat_point' in effects:
        char.stat_points += effects['stat_point']
    if 'affinity_points' in effects:
        char.affinity_points += effects['affinity_points']
    if 'affinity' in effects:
        for aff, val in effects['affinity'].items():
            char.affinities[aff] = char.affinities.get(aff, 0) + val
    if 'melee_damage' in effects:
        char.melee_damage += effects['melee_damage']
    if 'ranged_damage' in effects:
        char.ranged_damage += effects['ranged_damage']
    if 'melee_accuracy' in effects:
        char.melee_accuracy += effects['melee_accuracy']
    if 'ranged_accuracy' in effects:
        char.ranged_accuracy += effects['ranged_accuracy']
    if 'magic_damage' in effects:
        char.magic_damage += effects['magic_damage']
    if 'crit_damage_die' in effects:
        char.crit_bonus_die = effects['crit_damage_die']
    if 'save_half_magic' in effects:
        char.save_half_magic = effects['save_half_magic']
    if 'dual_wield_accuracy' in effects:
        char.dual_wield_accuracy += effects['dual_wield_accuracy']
    if 'unarmed_die_upgrade' in effects:
        char.brawler_stacks += effects['unarmed_die_upgrade']
    if 'armor_training_ac_heavy' in effects:
        char.armor_training_ac_heavy = effects['armor_training_ac_heavy']
    if 'armor_training_ac_medium' in effects:
        char.armor_training_ac_medium = effects['armor_training_ac_medium']
    if 'maximum_dex_ac_bonus' in effects:
        char.max_dex_ac_extra += effects['maximum_dex_ac_bonus']
    if 'hunker_ac' in effects:
        char.hunker_ac = effects['hunker_ac']
    if 'mana_well_die' in effects:
        char.mana_well_die = effects['mana_well_die']
    if 'eternal_mana_threshold' in effects:
        char.eternal_mana_threshold = effects['eternal_mana_threshold']
    if 'eternal_mana_amount' in effects:
        char.eternal_mana_amount = effects['eternal_mana_amount']
    if 'charge_die' in effects:
        char.charge_die = effects['charge_die']
    if 'cleave_damage' in effects:
        char.cleave_damage += effects['cleave_damage']
    if 'prone_die' in effects:
        char.prone_die = effects['prone_die']
    if 'execute_threshold' in effects:
        char.execute_threshold = effects['execute_threshold']
    if 'weapon_group_accuracy' in effects:
        char.weapon_group_accuracy += effects['weapon_group_accuracy']
    if 'point_blank' in effects:
        char.point_blank = effects['point_blank']
    if 'steady_aim_accuracy' in effects:
        char.steady_aim_accuracy += effects['steady_aim_accuracy']
    if 'defensive_duelist_ac' in effects:
        char.defensive_duelist_ac = effects['defensive_duelist_ac']
    if 'overdrive_bap' in effects:
        char.overdrive_bonus += effects['overdrive_bap']
    if 'twin_cast' in effects:
        char.twin_cast = effects['twin_cast']


def _repeatable_priority(effects):
    """Score repeatable effects: higher = more valuable to take.
    Damage > tanking > stats > utility > accuracy."""
    if not effects:
        return 0
    score = 0
    if 'melee_damage' in effects or 'ranged_damage' in effects or 'magic_damage' in effects or 'ranged_adv_damage' in effects:
        score = 5
    elif 'flat_vit' in effects or 'flat_hp' in effects or 'ac_bonus' in effects:
        score = 4
    elif 'stat_point' in effects:
        score = 3
    elif 'affinity_points' in effects or 'affinity' in effects or 'generic_affinity' in effects:
        score = 2
    elif 'spell' in effects:
        score = 2
    elif 'melee_accuracy' in effects or 'ranged_accuracy' in effects or 'magic_accuracy' in effects:
        score = 1
    elif 'skill_points' in effects:
        score = 0
    return score
