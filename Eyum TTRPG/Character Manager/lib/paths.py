from .effects import apply_effects, _repeatable_priority
from .stats import cost_for_stat


def _add_stat_bonus(char, stat_name, bonus, cost_table):
    """Apply a raw stat bonus using fractional tracking per handbook rules.
    When a stat costs N points to raise, +1 flat bonus grants 1/N of a stat point."""
    if bonus <= 0:
        return
    current = getattr(char, stat_name)
    cost = cost_for_stat(current, cost_table)
    if stat_name not in char.stat_points_banked:
        char.stat_points_banked[stat_name] = 0.0
    char.stat_points_banked[stat_name] += bonus / cost
    total_banked = char.stat_points_banked[stat_name]
    whole_points = int(total_banked)
    if whole_points >= 1:
        setattr(char, stat_name, current + whole_points)
        char.stat_points_banked[stat_name] = total_banked - whole_points


def apply_level_progression(char, target_level, settings):
    r = settings['rules']
    per = r['per_level']
    e2 = r['every_2_levels']
    e3 = r['every_3_levels']
    e8 = r.get('every_8_levels', {})
    e10 = r.get('every_10_levels', {})
    prof = r['proficiency']

    elemental_cycle = ['Fire', 'Earth', 'Water', 'Air']
    elem_idx = 0

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
            if char.has_magical and 'if_magical' in e2:
                elem = elemental_cycle[elem_idx % len(elemental_cycle)]
                char.affinities[elem] = char.affinities.get(elem, 0) + e2['if_magical']['elemental_affinity']
                elem_idx += 1
            if any(p == 'Utility' for (p, a), v in char.archetype_levels.items() if v > 0) and 'if_utility' in e2:
                char.skill_points += e2['if_utility']['skill_points']

        if lvl % 3 == 0:
            char.stat_points += e3['stat_points']
            char.affinity_points += e3['affinity_points']
            char.skill_points += e3.get('skill_points', 0)
            if char.has_magical and e3.get('if_magical_spell', False):
                char.spells_from_levels += 1
            magical_levels = sum(v for (p, a), v in char.archetype_levels.items() if p == 'Magical')
            physical_levels = sum(v for (p, a), v in char.archetype_levels.items() if p == 'Physical')
            if magical_levels > physical_levels and 'if_magical_stat_bonus' in e3:
                for stat, bonus in e3['if_magical_stat_bonus'].items():
                    _add_stat_bonus(char, stat, bonus, r['stat_point_cost'])
            elif physical_levels > magical_levels and 'if_physical_stat_bonus' in e3:
                for stat, bonus in e3['if_physical_stat_bonus'].items():
                    _add_stat_bonus(char, stat, bonus, r['stat_point_cost'])

        if lvl % 8 == 0 and 'bap' in e8:
            char.bap += e8['bap']
            char.skill_points += e8.get('skill_points', 0)

        if lvl % 10 == 0 and 'ap' in e10:
            char.ap += e10['ap']
            char.stat_points += e10.get('stat_points', 0)

        char.prof = prof['base'] + (lvl // 3)


def apply_paths(char, target_level, build_config, settings):
    r = settings['rules']
    paths_rules = settings['paths']
    cost_table = r['stat_point_cost']

    path_list = build_config.get('paths', [])
    if not path_list:
        return

    available_stp = target_level
    if getattr(char, 'skill_tree_level_bonus', False):
        available_stp += max(0, (target_level - 1) // 2)

    # Step 1: Pay 1 STP per unique path name to unlock its initial
    path_initial_paid = set()
    stp_remaining = available_stp
    for pconf in path_list:
        path_name = pconf['path']
        if path_name == 'Magical' and not char.has_magical:
            continue
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
        prev_key = (path_name, arch_name)
        prev_level = build_config.get('_prev_arch_levels', {}).get(prev_key, 0)
        share = max(share, prev_level)

        arch_rule = paths_rules.get(path_name, {}).get('archetypes', {}).get(arch_name, {})

        achievements = 0
        whole_levels = 0
        sorted_keys = sorted(arch_rule.keys(), key=lambda k: float(k))

        # Pass 1: Take EVERY tier (whole + sub + repeatable-sub) exactly once, in order.
        # This matches how a player levels: unlock the full tree before repeating anything.
        all_keys = sorted_keys
        for key in all_keys:
            if achievements >= min(share, desired_points):
                break
            apply_effects(char, arch_rule[key], cost_table)
            achievements += 1
            if float(key) == int(float(key)):
                whole_levels += 1

        # Pass 2: Spend any remaining STP on the single best repeatable tier.
        remaining = share - achievements
        if remaining > 0:
            repeat_keys = sorted([k for k in sorted_keys if float(k) != int(float(k)) and arch_rule[k].get('repeatable', False)],
                                key=lambda k: (-_repeatable_priority(arch_rule[k]),
                                               -arch_rule[k].get('melee_damage', 0) - arch_rule[k].get('ranged_damage', 0) - arch_rule[k].get('magic_damage', 0),
                                               float(k)))
            if repeat_keys:
                key = repeat_keys[0]
                max_count = repeatables.get(key, 999)
                already = repeat_taken_global.get((path_name, arch_name, key), 0)
                can_take = min(remaining, max_count - already)
                for _ in range(can_take):
                    apply_effects(char, arch_rule[key], cost_table)
                repeat_taken_global[(path_name, arch_name, key)] = already + can_take
                achievements += can_take

        char.archetype_levels[(path_name, arch_name)] = achievements
        char.archetype_whole_levels[(path_name, arch_name)] = whole_levels

    build_config.setdefault('_prev_arch_levels', {})
    for (pn, an), lv in char.archetype_levels.items():
        build_config['_prev_arch_levels'][(pn, an)] = lv

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
    magician_whole_levels = char.archetype_whole_levels.get(('Magical', 'Magician'), 0)
    if magician_whole_levels >= 5:
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
    if prof_bonus:
        prof_gains = target_level // 3 + 1
        char.skill_points += prof_gains * 3 * prof_bonus
    if expr_bonus:
        expr_gains = target_level // 8
        char.skill_points += expr_gains * 5 * expr_bonus
    if aff_bonus:
        char.affinity_points += max(0, target_level - 1) * aff_bonus
