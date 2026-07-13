from .stats import cost_for_stat


def apply_effects(char, effects, cost_table=None):
    if not effects:
        return
    if 'stat' in effects:
        for stat_name, bonus in effects['stat'].items():
            if stat_name in ('str', 'dex', 'con', 'wis', 'int', 'cha'):
                current = getattr(char, stat_name)
                if cost_table is not None and bonus > 0:
                    if stat_name not in char.stat_points_banked:
                        char.stat_points_banked[stat_name] = 0
                    spent = 0
                    while spent < bonus:
                        cost = cost_for_stat(current, cost_table)
                        char.stat_points_banked[stat_name] += 1
                        if char.stat_points_banked[stat_name] >= cost:
                            current += 1
                            setattr(char, stat_name, current)
                            char.stat_points_banked[stat_name] -= cost
                        spent += 1
                else:
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
    if 'psychic_damage_bonus' in effects:
        char.psychic_damage_bonus = effects['psychic_damage_bonus']
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
    if 'claw_die' in effects:
        char.tull_claw_die = effects['claw_die']
        char.tull_claw_flat = effects.get('claw_flat', 0)
    if 'pack_tactics' in effects:
        char.pack_tactics = True
    if 'extra_attack_bap' in effects:
        char.extra_attack_bap = True
    if 'flat_vit' in effects:
        char.flat_vit += effects['flat_vit']
    if 'flat_hp' in effects:
        char.flat_hp += effects['flat_hp']
    if 'speed' in effects:
        char.speed = getattr(char, 'speed', 30) + effects['speed']
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
    if 'initiative' in effects:
        char.initiative += effects['initiative']
    if 'bonus_action_sprint' in effects:
        char.bonus_action_sprint = True
    if 'melee_kill_bonus' in effects:
        char.melee_kill_bonus = True
    if 'melee_expertise' in effects:
        char.melee_accuracy += 2
        char.melee_damage += 1
    if 'ranged_ignore_half_cover' in effects:
        char.ranged_ignore_half_cover = True
    if 'skill_points_per_level' in effects:
        char.skill_points_per_level = max(char.skill_points_per_level, effects['skill_points_per_level'])
    if 'proficiency_per_level' in effects:
        char.proficiency_per_level = max(char.proficiency_per_level, effects['proficiency_per_level'])
    if 'expertise_per_level' in effects:
        char.expertise_per_level = max(char.expertise_per_level, effects['expertise_per_level'])
    if 'affinity_per_level' in effects:
        char.affinity_per_level = max(char.affinity_per_level, effects['affinity_per_level'])
    if 'magic_blast' in effects:
        char.magic_blast = True
    if 'magic_accuracy_non_water' in effects:
        char.magic_accuracy_non_water += effects['magic_accuracy_non_water']
    if 'magic_accuracy_non_air' in effects:
        char.magic_accuracy_non_air += effects['magic_accuracy_non_air']
    if 'magic_accuracy_non_fire' in effects:
        char.magic_accuracy_non_fire += effects['magic_accuracy_non_fire']
    if 'magic_accuracy_non_earth' in effects:
        char.magic_accuracy_non_earth += effects['magic_accuracy_non_earth']
    if 'magic_accuracy_non_necrotic' in effects:
        char.magic_accuracy_non_necrotic += effects['magic_accuracy_non_necrotic']
    if 'magic_accuracy_non_radiant' in effects:
        char.magic_accuracy_non_radiant += effects['magic_accuracy_non_radiant']
    if 'proficiency_weapon' in effects:
        pass
    if 'expertise_weapon' in effects:
        pass
    if 'initiative_advantage' in effects:
        char.initiative_advantage = True
    if 'darkvision_range' in effects:
        char.darkvision_range = max(char.darkvision_range, effects['darkvision_range'])
    if 'immunity_threatened' in effects:
        char.immunity_threatened = True
    if 'immunity_surprised' in effects:
        char.immunity_surprised = True
    if 'fly_speed' in effects:
        char.fly_speed = max(char.fly_speed, effects['fly_speed'])
    if 'true_sight_range' in effects:
        char.true_sight_range = max(char.true_sight_range, effects['true_sight_range'])
    if 'karma' in effects:
        char.karma += effects['karma']
    if 'pact_access_tier' in effects:
        char.pact_access_tier = max(char.pact_access_tier, effects['pact_access_tier'])
    if 'anti_deity_damage' in effects:
        pass  # Conditional: vs deities only
    if 'hallowed_affinity' in effects:
        char.hallowed_affinity += effects['hallowed_affinity']
    if 'eldritch_affinity' in effects:
        char.eldritch_affinity += effects['eldritch_affinity']
    if 'eldritch_blast_damage' in effects:
        char.eldritch_blast_damage = max(char.eldritch_blast_damage, effects['eldritch_blast_damage'])
    if 'eldritch_blast_range' in effects:
        char.eldritch_blast_range += effects['eldritch_blast_range']
    if 'healing_maximize' in effects:
        char.healing_maximize = True
    if 'cleansing' in effects:
        char.cleansing = max(char.cleansing, effects['cleansing'])
    if 'concentration_two_spells' in effects:
        char.concentration_two_spells = True
    if 'free_heal' in effects:
        char.free_heal = True
    if 'reaction_save_ally' in effects:
        char.reaction_save_ally = True
    if 'weapon_group_accuracy' in effects:
        char.weapon_group_accuracy += effects['weapon_group_accuracy']
    if 'damage_reduction' in effects:
        char.damage_reduction += effects['damage_reduction']
    if 'vit_per_level' in effects:
        char.vit_per_level_bonus += effects['vit_per_level']
    if 'hp_per_level' in effects:
        char.hp_per_level_bonus += effects['hp_per_level']
    if 'mana_per_level' in effects:
        char.mana_per_level_bonus += effects['mana_per_level']
    if 'crit_block' in effects:
        char.crit_block = True
    if 'second_chance' in effects:
        char.second_chance = True
    if 'brawler_stacks' in effects:
        char.brawler_stacks += effects['brawler_stacks']
    if 'skill_tree_level_bonus' in effects:
        char.skill_tree_level_bonus = True
    if 'spell_damage_mult' in effects:
        char.spell_damage_mult = max(char.spell_damage_mult, effects['spell_damage_mult'])
    if 'spell_mana_mult' in effects:
        char.spell_mana_mult = max(char.spell_mana_mult, effects['spell_mana_mult'])
    if 'generic_affinity_spendable' in effects:
        char.generic_affinity_spendable = True
    if 'monster_damage' in effects:
        pass  # Conditional bonus vs monsters — not applied universally
    if 'humanoid_attack_penalty' in effects:
        pass  # Conditional bonus vs humanoids — not applied universally
    if 'monster_attack_penalty' in effects:
        pass  # Conditional bonus vs monsters — not applied universally
    if 'melee_damage_two_handed' in effects:
        pass  # Conditional: 2H weapons only
    if 'riposte_damage' in effects:
        pass  # Conditional: riposte only
    if 'melee_pierce_attack' in effects:
        pass  # Conditional: pierce attack only
    if 'dueling_damage_bonus' in effects:
        pass  # Conditional: 1v1 duel only
    if 'retaliation_damage_flat' in effects:
        pass  # Conditional: retaliation only
    if 'aura_ac' in effects:
        char.ac_bonus += effects['aura_ac']
    if 'aura_attack_bonus' in effects:
        char.melee_accuracy += effects['aura_attack_bonus']
        char.ranged_accuracy += effects['aura_attack_bonus']
    if 'aura_ability_bonus' in effects:
        char.melee_accuracy += effects['aura_ability_bonus']
        char.ranged_accuracy += effects['aura_ability_bonus']
        char.magic_accuracy += effects['aura_ability_bonus']
    if 'aura_damage_reduction' in effects:
        char.damage_reduction += effects['aura_damage_reduction']
    if 'caster_enemy_damage_bonus' in effects:
        pass  # Conditional: vs magic-users only
    if 'caster_enemy_hit_bonus' in effects:
        pass  # Conditional: accuracy vs magic-users only
    if 'caster_enemy_damage_mult' in effects:
        pass  # Conditional: dmg mult vs magic-users only
    if 'psychic_save_dc_bonus' in effects:
        char.magic_damage += effects['psychic_save_dc_bonus']
    if 'spell_add_damage_bonus' in effects:
        char.magic_damage += 3
    if 'affinity_bonus_next_bracket' in effects:
        char.magic_damage += 2
    if 'affinity_boost_20pct' in effects:
        for aff in list(char.affinities.keys()):
            if aff != 'Generic':
                char.affinities[aff] = int(char.affinities[aff] * 1.2)
    if 'affinity_double_spend' in effects:
        char.affinity_points *= 2
    if 'ritual_damage_bonus_pct' in effects:
        pass  # Conditional: ritual spells only
    if 'rp_bonus' in effects:
        char.rp += effects['rp_bonus']
    if 'heavy_reach' in effects:
        char.melee_damage += effects['heavy_reach']
    if 'charging_strike' in effects:
        pass  # Conditional: only when charging
    if 'skirmish_movement_damage' in effects:
        pass  # Conditional: only with movement
    if 'disengage_dash_bonus' in effects:
        char.speed += 5
    if 'ac_bonus_shield' in effects:
        char.ac_bonus += effects['ac_bonus_shield']


def die_average_sub(die_str):
    if isinstance(die_str, (int, float)):
        return die_str
    from .die_avg import die_average
    return die_average(die_str, 0)


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
    if 'shield_master' in effects:
        char.shield_master = True
    if 'overdrive_bap' in effects:
        char.overdrive_bonus += effects['overdrive_bap']
    if 'twin_cast' in effects:
        char.twin_cast = effects['twin_cast']
    if 'damage_reduction' in effects:
        char.damage_reduction += effects['damage_reduction']
    if 'brawler_stacks' in effects:
        char.brawler_stacks += effects['brawler_stacks']
    if 'crit_block' in effects:
        char.crit_block = True
    if 'second_chance' in effects:
        char.second_chance = True


def _repeatable_priority(effects):
    """Score repeatable effects: higher = more valuable to take.
    Damage > tanking > stats > utility > accuracy."""
    if not effects:
        return 0
    score = 0
    damage_keys = ('melee_damage', 'ranged_damage', 'magic_damage', 'ranged_adv_damage',
                   'melee_damage_two_handed', 'riposte_damage', 'melee_pierce_attack',
                   'dueling_damage_bonus', 'charging_strike', 'skirmish_movement_damage',
                   'retaliation_damage_flat')
    if any(k in effects for k in damage_keys):
        score = 5
    elif 'generic_affinity' in effects:
        score = 6
    elif 'flat_vit' in effects or 'flat_hp' in effects or 'ac_bonus' in effects or 'ac_bonus_shield' in effects or 'vit_per_level' in effects:
        score = 4
    elif 'speed' in effects or 'initiative' in effects:
        score = 3
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
