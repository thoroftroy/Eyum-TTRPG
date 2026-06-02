from .effects import apply_effects, _repeatable_priority


def apply_level_progression(char, target_level, settings):
    r = settings['rules']
    per = r['per_level']
    e2 = r['every_2_levels']
    e3 = r['every_3_levels']
    e8 = r.get('every_8_levels', {})
    e10 = r.get('every_10_levels', {})
    prof = r['proficiency']

    for lvl in range(2, target_level + 1):
        char.level = lvl
        char.skill_points += per['skill_points']
        char.vit_n += per['vit_dice_count']
        char.hp_n += per['hp_dice_count']
        char.mana_n += per['mana_dice_count']

        if lvl % 2 == 0:
            if char.has_physical and 'if_physical' in e2:
                char.flat_vit += e2['if_physical']['flat_vit']
                char.flat_hp += e2['if_physical']['flat_hp']

        if lvl % 3 == 0:
            char.stat_points += e3['stat_points']
            char.affinity_points += e3['affinity_points']
            char.skill_points += e3.get('skill_points', 0)
            if char.has_magical and e3.get('if_magical_spell', False):
                char.spells_from_levels += 1

        if lvl % 8 == 0 and 'bap' in e8:
            char.bap += e8['bap']
            char.skill_points += e8.get('skill_points', 0)

        if lvl % 10 == 0 and 'ap' in e10:
            char.ap += e10['ap']

        char.prof = prof['base'] + (lvl // 3)


def apply_paths(char, target_level, build_config, settings):
    r = settings['rules']
    paths_rules = settings['paths']
    cost_table = r['stat_point_cost']

    path_list = build_config.get('paths', [])
    if not path_list:
        return

    available_stp = 1 + (target_level // 2)
    if getattr(char, 'skill_tree_level_bonus', False):
        available_stp += max(0, (target_level - 1) // 2)

    # Step 1: Pay 1 STP per unique path name to unlock its initial
    path_initial_paid = set()
    stp_remaining = available_stp
    for pconf in path_list:
        path_name = pconf['path']
        if path_name in path_initial_paid:
            continue
        path_initial_paid.add(path_name)
        path_rule = paths_rules.get(path_name, {})
        if 'initial' in path_rule and stp_remaining > 0:
            apply_effects(char, path_rule['initial'], cost_table)
            stp_remaining -= 1
            if path_name == 'Magical':
                char.starting_spells = r['magical_start']['spells_at_level_1']

    # Step 2: Distribute remaining STP for archetype levels
    total_paths = len(path_list)
    if total_paths == 0:
        return

    stp_for_archetypes = stp_remaining
    if stp_for_archetypes > 0:
        points_per = stp_for_archetypes // total_paths
        remainder = stp_for_archetypes % total_paths
    else:
        points_per = 0
        remainder = 0

    repeat_taken_global = {}

    for i, pconf in enumerate(path_list):
        path_name = pconf['path']
        arch_name = pconf['archetype']
        desired_points = int(pconf['level'])
        repeatables = pconf.get('repeatables', {})

        share = points_per + (1 if i < remainder else 0)

        arch_rule = paths_rules.get(path_name, {}).get('archetypes', {}).get(arch_name, {})

        achievements = 0
        whole_levels = 0
        sorted_keys = sorted(arch_rule.keys(), key=lambda k: float(k))

        # Apply base levels up to desired_points (capped by share)
        whole_keys = sorted([k for k in sorted_keys if float(k) == int(float(k))], key=float)
        sub_keys = sorted([k for k in sorted_keys if float(k) != int(float(k)) and not arch_rule[k].get('repeatable', False)], key=float)
        base_keys = whole_keys + sub_keys
        for key in base_keys:
            if achievements >= min(share, desired_points):
                break
            apply_effects(char, arch_rule[key], cost_table)
            achievements += 1
            if float(key) == int(float(key)):
                whole_levels += 1

        # Apply repeatable sub-levels with remaining points
        remaining = share - achievements
        if remaining > 0:
            repeat_keys = sorted([k for k in sorted_keys if float(k) != int(float(k)) and arch_rule[k].get('repeatable', False)], key=lambda k: -_repeatable_priority(arch_rule[k]))
            for key in repeat_keys:
                max_count = repeatables.get(key, 999)
                already = repeat_taken_global.get((path_name, arch_name, key), 0)
                can_take = min(remaining, max_count - already)
                for _ in range(can_take):
                    apply_effects(char, arch_rule[key], cost_table)
                    remaining -= 1
                repeat_taken_global[(path_name, arch_name, key)] = already + can_take
                achievements += can_take

        remaining = share - achievements
        if remaining > 0:
            for key in repeat_keys:
                max_count = repeatables.get(key, 999)
                already = repeat_taken_global.get((path_name, arch_name, key), 0)
                can_take = min(remaining, max_count - already)
                for _ in range(can_take):
                    apply_effects(char, arch_rule[key], cost_table)
                    remaining -= 1
                repeat_taken_global[(path_name, arch_name, key)] = already + can_take
                achievements += can_take

        char.archetype_levels[(path_name, arch_name)] = achievements
        char.archetype_whole_levels[(path_name, arch_name)] = whole_levels

    all_remaining = 0
    path_repeat_data = []
    for i, pconf in enumerate(path_list):
        path_name = pconf['path']
        arch_name = pconf['archetype']
        desired_points = int(pconf['level'])
        repeatables = pconf.get('repeatables', {})
        share = points_per + (1 if i < remainder else 0)
        achieved = char.archetype_levels.get((path_name, arch_name), 0)
        path_remaining = share - achieved
        if path_remaining > 0:
            all_remaining += path_remaining
        arch_rule = paths_rules.get(path_name, {}).get('archetypes', {}).get(arch_name, {})
        sorted_keys = sorted(arch_rule.keys(), key=lambda k: float(k))
        repeat_keys = sorted([k for k in sorted_keys if float(k) != int(float(k)) and arch_rule[k].get('repeatable', False)], key=lambda k: -_repeatable_priority(arch_rule[k]))
        for key in repeat_keys:
            max_count = repeatables.get(key, 999)
            achieved_count = repeat_taken_global.get((path_name, arch_name, key), 0)
            path_repeat_data.append((path_name, arch_name, key, max_count, arch_rule[key], achieved_count))

    if all_remaining > 0 and path_repeat_data:
        path_repeat_data.sort(key=lambda x: _repeatable_priority(x[4]), reverse=True)
        for path_name, arch_name, key, max_count, effects, achieved_count in path_repeat_data:
            can_take = max_count - achieved_count
            take = min(all_remaining, can_take)
            if take > 0:
                for _ in range(take):
                    apply_effects(char, effects, cost_table)
                old_achieved = char.archetype_levels.get((path_name, arch_name), 0)
                char.archetype_levels[(path_name, arch_name)] = old_achieved + take
                all_remaining -= take
            if all_remaining <= 0:
                break

    apply_per_level_bonuses(char, target_level)

    die_order = settings['rules']['die_upgrade_order']
    for (path_name, arch_name), whole_levels in char.archetype_whole_levels.items():
        if arch_name == 'Indomitable':
            for _ in range(whole_levels):
                idx = die_order.index(char.mana_die)
                if idx > 0:
                    char.mana_die = die_order[idx - 1]
        if arch_name == 'Magician':
            for _ in range(whole_levels):
                idx = die_order.index(char.vit_die)
                if idx > 0:
                    char.vit_die = die_order[idx - 1]

    # Magician tier 5 applies only when 5+ whole levels achieved in Magician
    magician_achieved = char.archetype_levels.get(('Magical', 'Magician'), 0)
    if magician_achieved >= 5:
        magician_t5 = paths_rules.get('Magical', {}).get('archetypes', {}).get('Magician', {}).get('5', {})
        apply_effects(char, magician_t5, cost_table)


def apply_per_level_bonuses(char, target_level):
    sp_bonus = getattr(char, 'skill_points_per_level', 0)
    prof_bonus = getattr(char, 'proficiency_per_level', 0)
    expr_bonus = getattr(char, 'expertise_per_level', 0)
    aff_bonus = getattr(char, 'affinity_per_level', 0)

    if sp_bonus:
        retro = max(0, target_level - 1) * sp_bonus
        char.skill_points += retro
        if target_level >= 6:
            char.skill_points += 10
    if prof_bonus:
        prof_gains = target_level // 3 + 1
        char.skill_points += prof_gains * 3 * prof_bonus
    if expr_bonus:
        expr_gains = target_level // 8
        char.skill_points += expr_gains * 5 * expr_bonus
    if aff_bonus:
        char.affinity_points += max(0, target_level - 1) * aff_bonus
