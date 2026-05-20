#!/usr/bin/env python3
"""
Eyum TTRPG Character Sheet Generator
Fixed to properly account for:
- Stat point cost scaling (higher stats cost more)
- All Level-up bonuses per handbook
- Individual breakdown of each stat/pool
- Damage calculations
"""

import json
import os
import sys


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def cost_for_stat(current_val, cost_table):
    """Cost to increase a stat from current_val to current_val+1.
    Cost is based on the result (new value), not current value."""
    new_val = current_val + 1
    items = sorted(cost_table.items(), key=lambda x: int(x[0].split('-')[0]))
    for range_str, cost in items:
        parts = range_str.split('-')
        low = int(parts[0])
        high = int(parts[1]) if len(parts) > 1 else low
        if low <= new_val <= high:
            return cost
    tier = (new_val - 1) // 10
    return tier + 1


class Character:
    def __init__(self, name, stats, settings):
        self.name = name
        r = settings['rules']
        base = r['base_stat_value']

        self.str = stats.get('str', base)
        self.dex = stats.get('dex', base)
        self.con = stats.get('con', base)
        self.wis = stats.get('wis', base)
        self.int = stats.get('int', base)
        self.cha = stats.get('cha', base)

        self.starting_str = self.str
        self.starting_dex = self.dex
        self.starting_con = self.con
        self.starting_wis = self.wis
        self.starting_int = self.int
        self.starting_cha = self.cha

        sd = r['starting_dice']
        l1 = r['level_1_bonuses']

        self.vit_n = 1 + l1['vit_dice_count']
        self.hp_n = 1 + l1['hp_dice_count']
        self.mana_n = 1 + l1['mana_dice_count']

        self.vit_die = sd['vit_die']
        self.hp_die = sd['hp_die']
        self.mana_die = sd['mana_die']

        self.flat_vit = 0
        self.flat_hp = 0
        self.flat_mana = 0
        self.ac_bonus = 0
        self.armor_training_ac_heavy = 0
        self.armor_training_ac_medium = 0
        self.fire_damage_bonus = None
        self.earth_damage_bonus = None
        self.water_damage_bonus = None
        self.air_damage_bonus = None
        self.radiant_damage_bonus = None
        self.necrotic_damage_bonus = None

        sp = r['starting_points']
        sc = r['starting_combat']

        self.skill_points = sp['skill_points'] + l1['skill_points']
        self.stat_points = 0
        self.affinity_points = sp['affinity_points']

        self.ap = sc['ap']
        self.bap = sc['bap']
        self.rp = sc['rp']
        self.prof = r['proficiency']['base']

        self.feats = 0
        self.feat_per_feat = 0
        self.spells_from_levels = 0
        self.starting_spells = 0

        self.has_physical = False
        self.has_magical = False
        self.affinities = {"Generic": 1}
        self.archetype_levels = {}
        self.archetype_whole_levels = {}

        self.stat_points_spent = 0

        self.melee_damage = 0
        self.melee_accuracy = 0
        self.ranged_damage = 0
        self.ranged_accuracy = 0
        self.magic_accuracy = 0
        self.magic_damage = 0

        self.gear = {}

        self.level = 1

        self.feats_taken = []
        self.feat_fallback_notes = []
        self.vit_per_level_bonus = 0
        self.hp_per_level_bonus = 0
        self.mana_per_level_bonus = 0
        self.crit_bonus_die = None
        self.save_half_magic = False
        self.dual_wield_accuracy = 0
        self.brawler_stacks = 0
        self.max_dex_ac_extra = 0
        self.hunker_ac = 0
        self.mana_well_die = None
        self.eternal_mana_threshold = 0
        self.eternal_mana_amount = 0
        self.charge_die = None
        self.cleave_damage = 0
        self.prone_die = None
        self.execute_threshold = 0
        self.weapon_group_accuracy = 0
        self.point_blank = False
        self.steady_aim_accuracy = 0
        self.defensive_duelist_ac = False
        self.overdrive_bonus = 0
        self.quick_spells = False
        self.twin_cast = False
        self.is_unarmed = False
        self.tull_tier = 0
        self.melee_extra_info = None
        self.pack_tactics = False

    def mod(self, stat):
        val = getattr(self, stat)
        return (val - 10) // 2

    def vit_max(self, r):
        con_mod = self.mod('con')
        dice_avg = self.vit_n * r['die_averages'][self.vit_die]
        con_bonus = con_mod * self.vit_n
        return self.flat_vit + int(dice_avg + con_bonus)

    def hp_max(self, r):
        dice_avg = self.hp_n * r['die_averages'][self.hp_die]
        return self.flat_hp + int(dice_avg)

    def mana_max(self, r):
        wis_mod = self.mod('wis')
        dice_avg = self.mana_n * r['die_averages'][self.mana_die]
        return self.flat_mana + int(dice_avg + wis_mod * self.mana_n)

    def ac(self, armor_type, armor_types, dex_table=None):
        base = 10
        dex_mod = self.mod('dex')
        armor_info = armor_types.get(armor_type, armor_types.get('none', {'ac_bonus': 0, 'max_dex': 4}))
        armor_bonus = armor_info['ac_bonus']
        max_dex = armor_info['max_dex']

        if armor_type in ('heavy', 'nerite_heavy', 'dragon_heavy'):
            armor_bonus += getattr(self, 'armor_training_ac_heavy', 0)
        if armor_type in ('medium', 'nerite_medium', 'dragon_medium'):
            armor_bonus += getattr(self, 'armor_training_ac_medium', 0)

        max_dex += getattr(self, 'max_dex_ac_extra', 0)

        if armor_type == 'none':
            effective = dex_mod
        else:
            effective = max(0, min(dex_mod, max_dex))

        if dex_table and effective > 0:
            dex_bonus = dex_table.get(str(min(effective, 18)), min(effective, 7))
        elif effective <= 0:
            dex_bonus = effective if armor_type == 'none' else 0
        else:
            dex_bonus = effective

        return base + armor_bonus + dex_bonus + self.ac_bonus

    def to_hit_melee(self):
        acc = self.prof + self.melee_accuracy + self.weapon_group_accuracy + self.steady_aim_accuracy
        if self.dual_wield_accuracy > 0:
            acc += self.dual_wield_accuracy
        return acc + self.mod('str')

    def to_hit_ranged(self):
        acc = self.prof + self.ranged_accuracy + self.weapon_group_accuracy + self.steady_aim_accuracy
        return acc + self.mod('dex')

    def to_hit_magic(self):
        acc = self.prof + self.magic_accuracy
        return acc + self.mod('wis')


def format_mod(m):
    if m >= 0:
        return "+" + str(m)
    return str(m)


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
            if char.has_magical:
                cycle = ['Fire', 'Earth', 'Water', 'Air']
                idx = ((lvl // 2) - 1) % 4
                char.affinities[cycle[idx]] = char.affinities.get(cycle[idx], 0) + 1

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

    path_list = build_config.get('paths', [])
    if not path_list:
        return

    applied_initial = set()
    for pconf in path_list:
        path_name = pconf['path']
        if path_name in applied_initial:
            continue
        applied_initial.add(path_name)
        path_rule = paths_rules.get(path_name, {})
        if 'initial' in path_rule:
            apply_effects(char, path_rule['initial'])
            if path_name == 'Magical':
                char.starting_spells = r['magical_start']['spells_at_level_1']

    available_stp = 1 + (target_level // 2)
    total_paths = len(path_list)
    points_per = available_stp // total_paths
    remainder = available_stp % total_paths

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
        base_keys = [k for k in sorted_keys if float(k) == int(float(k)) or not arch_rule[k].get('repeatable', False)]
        for key in base_keys:
            if achievements >= min(share, desired_points):
                break
            apply_effects(char, arch_rule[key])
            achievements += 1
            if float(key) == int(float(key)):
                whole_levels += 1

        # Apply repeatable sub-levels with remaining points
        remaining = share - achievements
        if remaining > 0 and repeatables:
            repeat_keys = sorted([k for k in sorted_keys if float(k) != int(float(k)) and arch_rule[k].get('repeatable', False)], key=lambda k: float(k))
            for key in repeat_keys:
                max_count = repeatables.get(key, 0)
                count = min(remaining, max_count)
                for _ in range(count):
                    apply_effects(char, arch_rule[key])
                    remaining -= 1
                achievements += count

        remaining = share - achievements
        # If this path has leftover STP and has repeatables configured, consume them
        if remaining > 0 and repeatables:
            repeat_keys = sorted([k for k in sorted_keys if float(k) != int(float(k)) and arch_rule[k].get('repeatable', False)], key=lambda k: float(k))
            for key in repeat_keys:
                max_count = repeatables.get(key, 0)
                count = min(remaining, max_count)
                for _ in range(count):
                    apply_effects(char, arch_rule[key])
                    remaining -= 1
                achievements += count

        char.archetype_levels[(path_name, arch_name)] = achievements
        char.archetype_whole_levels[(path_name, arch_name)] = whole_levels

    # After distributing all paths, collect leftover STP from capped paths and redistribute
    # to path repeatables across the build
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
        if repeatables:
            arch_rule = paths_rules.get(path_name, {}).get('archetypes', {}).get(arch_name, {})
            sorted_keys = sorted(arch_rule.keys(), key=lambda k: float(k))
            repeat_keys = sorted([k for k in sorted_keys if float(k) != int(float(k)) and arch_rule[k].get('repeatable', False)], key=lambda k: float(k))
            for key in repeat_keys:
                max_count = repeatables.get(key, 0)
                achieved_count = 0
                # count how many of this key were already applied
                path_repeat_data.append((path_name, arch_name, key, max_count, arch_rule[key], achieved_count))

    if all_remaining > 0 and path_repeat_data:
        # Sort repeatables by value: prefer direct damage/defense boosts over skill points
        def repeat_score(item):
            key = item[2]
            effects = item[4]
            score = 0
            if 'melee_damage' in effects or 'ranged_damage' in effects:
                score = 5
            elif 'ac_bonus' in effects:
                score = 4
            elif 'flat_vit' in effects or 'flat_hp' in effects:
                score = 3
            elif 'magic_damage' in effects or 'magic_accuracy' in effects:
                score = 3
            elif 'skill_points' in effects or 'stat_point' in effects:
                score = 2
            elif 'affinity_points' in effects:
                score = 1
            return score

        path_repeat_data.sort(key=repeat_score, reverse=True)
        for path_name, arch_name, key, max_count, effects, achieved_count in path_repeat_data:
            can_take = max_count - achieved_count
            take = min(all_remaining, can_take)
            if take > 0:
                for _ in range(take):
                    apply_effects(char, effects)
                old_achieved = char.archetype_levels.get((path_name, arch_name), 0)
                char.archetype_levels[(path_name, arch_name)] = old_achieved + take
                all_remaining -= take
            if all_remaining <= 0:
                break

    # Apply archetype side effects (penalties)
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


def check_feat_prereq(char, prereq, settings):
    if not prereq:
        return True, None
    if 'level' in prereq and char.level < prereq['level']:
        return False, 'Requires Level ' + str(prereq['level'])
    if 'stat' in prereq:
        for stat_name, min_val in prereq['stat'].items():
            if getattr(char, stat_name, 0) < min_val:
                stat_upper = stat_name.upper()
                return False, 'Requires ' + stat_upper + ' ' + str(min_val)
    if 'path' in prereq:
        for arch_name, min_level in prereq['path'].items():
            found = False
            for (path, arch), lvl in char.archetype_levels.items():
                if arch == arch_name and lvl >= min_level:
                    found = True
                    break
            if not found:
                return False, 'Requires ' + arch_name + ' Lvl ' + str(min_level)
    if 'feat' in prereq:
        if prereq['feat'] not in char.feats_taken:
            return False, 'Requires feat: ' + prereq['feat']
    return True, None


def select_feats(char, target_level, settings):
    feats_data = settings.get('feats', {})
    feat_opportunities = target_level // 3
    feat_count = int(feat_opportunities * (1 + char.feat_per_feat))

    feat_count = min(feat_count, 500)

    taken_count = 0
    for milestone in range(3, min(target_level, 1000) + 1, 3):
        if taken_count >= feat_count:
            break

        old_level = char.level
        char.level = milestone

        eligible = []
        for feat_name, feat_data in feats_data.items():
            repeatable = feat_data.get('repeatable', False)
            if not repeatable and feat_name in char.feats_taken:
                continue
            if isinstance(repeatable, int) and not isinstance(repeatable, bool):
                times_taken = sum(1 for f in char.feats_taken if f == feat_name)
                if times_taken >= repeatable:
                    continue
            ok, _ = check_feat_prereq(char, feat_data.get('prereq', {}), settings)
            if ok:
                eligible.append((feat_name, feat_data))

        # Compute best feat ignoring prereqs for fallback tracking
        all_candidates = []
        for feat_name, feat_data in feats_data.items():
            repeatable = feat_data.get('repeatable', False)
            if not repeatable and feat_name in char.feats_taken:
                continue
            if isinstance(repeatable, int) and not isinstance(repeatable, bool):
                times_taken = sum(1 for f in char.feats_taken if f == feat_name)
                if times_taken >= repeatable:
                    continue
            all_candidates.append((feat_name, feat_data))
        best_wanted = max(all_candidates, key=lambda x: x[1].get('value', 0)) if all_candidates else None

        if eligible:
            best = max(eligible, key=lambda x: x[1].get('value', 0))
            best_value = best[1].get('value', 0)
            if best_value >= 2:
                char.feats_taken.append(best[0])
                apply_feat_effects(char, best[1].get('effects', {}))
                # Check if we wanted something else but couldn't
                if best_wanted and best_wanted[0] != best[0] and best_wanted[1].get('value', 0) > best_value:
                    _, reason = check_feat_prereq(char, best_wanted[1].get('prereq', {}), settings)
                    note = "    (Wanted " + best_wanted[0] + " but did not meet prerequisite: " + reason + ")"
                    if note not in char.feat_fallback_notes:
                        char.feat_fallback_notes.append(note)
            else:
                char.stat_points += 2
        else:
            char.stat_points += 2
            if best_wanted and best_wanted[1].get('value', 0) >= 2:
                _, reason = check_feat_prereq(char, best_wanted[1].get('prereq', {}), settings)
                if reason:
                    note = "    (No eligible feats worth taking. Best unavailable: " + best_wanted[0] + " - " + reason + ")"
                    if note not in char.feat_fallback_notes:
                        char.feat_fallback_notes.append(note)
        taken_count += 1
        char.level = old_level

    if char.vit_per_level_bonus:
        char.flat_vit += char.vit_per_level_bonus * target_level
    if char.hp_per_level_bonus:
        char.flat_hp += char.hp_per_level_bonus * target_level
    if char.mana_per_level_bonus:
        char.flat_mana += char.mana_per_level_bonus * target_level

    char.feats = feat_count


def spend_stat_points(char, priority, points, cost_table, char_type='balanced'):
    """Spend stat points to raise stats with realistic spread.
    char_type can be: 'tank', 'marksman', 'caster', 'jack', 'balanced'"""
    
    points_remaining = points
    
    stat_targets = {}
    
    if char_type == 'jack':
        target_vals = [12, 12, 12, 12, 12, 12]
        for i, stat in enumerate(['str', 'dex', 'con', 'wis', 'int', 'cha']):
            stat_targets[stat] = target_vals[i]
    elif char_type == 'tank':
        stat_targets = {'con': 20, 'str': 18, 'dex': 12, 'wis': 10, 'int': 8, 'cha': 8}
    elif char_type == 'marksman':
        stat_targets = {'dex': 20, 'con': 14, 'str': 12, 'wis': 10, 'int': 8, 'cha': 8}
    elif char_type == 'caster':
        stat_targets = {'wis': 18, 'int': 14, 'con': 12, 'dex': 10, 'cha': 8, 'str': 8}
    else:
        for stat in priority:
            if priority.index(stat) == 0:
                stat_targets[stat] = 20
            elif priority.index(stat) == 1:
                stat_targets[stat] = 14
            elif priority.index(stat) == 2:
                stat_targets[stat] = 10
            else:
                stat_targets[stat] = 8
    
    # First pass: reach targets
    for stat in priority:
        target = stat_targets.get(stat, 8)
        current = getattr(char, stat)
        while points_remaining > 0 and current < target:
            cost = cost_for_stat(current, cost_table)
            if cost > points_remaining:
                break
            setattr(char, stat, current + 1)
            points_remaining -= cost
            char.stat_points_spent += cost
            current += 1
    
    # Second pass: spend remaining points beyond targets (round-robin priority order)
    while points_remaining > 0:
        spent = False
        for stat in priority:
            if points_remaining <= 0:
                break
            current = getattr(char, stat)
            cost = cost_for_stat(current, cost_table)
            if cost <= points_remaining:
                setattr(char, stat, current + 1)
                points_remaining -= cost
                char.stat_points_spent += cost
                spent = True
        if not spent:
            break
    
    return points_remaining


def spend_affinity_points(char, settings):
    affp = char.affinity_points
    if affp <= 0:
        return
    
    pref_order = ['Fire', 'Earth', 'Water', 'Air', 'Radiant', 'Necrotic', 'Psychic']
    
    while affp > 0:
        for aff in pref_order:
            if affp <= 0:
                break
            char.affinities[aff] = char.affinities.get(aff, 0) + 1
            affp -= 1
    
    char.affinity_points = 0


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


def check_spell_prereqs(char, spell, element, best_aff_val):
    if spell.get('affinity_required', 0) > best_aff_val:
        return False
    if 'int_required' in spell and char.int < spell['int_required']:
        return False
    extra = spell.get('extra_prereqs', {})
    if 'affinities_at_10' in extra:
        count = sum(1 for v in char.affinities.values() if v >= 10)
        if count < extra['affinities_at_10']:
            return False
    return True


def spell_avg_damage(spell, element, best_aff_val, die_avg, hit_chance, weapon_info=None):
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
                dmg = base + best_aff_val * mul
            else:
                dmg = base + best_aff_val
        else:
            dmg = int(formula)
    else:
        return 0

    # Add weapon magic damage bonus
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
        if spell.get('save_half'):
            dmg *= save_fail + (1 - save_fail) * 0.5
        else:
            dmg *= save_fail

    # AoE bonus: assume 2 targets for AoE spells
    if spell.get('aoe_radius', 0) > 0 or spell.get('aoe_cone') or spell.get('aoe_line') or spell.get('aoe_self'):
        dmg *= 2

    # Extra damage from DoT effects
    if spell.get('extra_effect') == 'Burned+DoT':
        dmg += die_avg.get('2d6', 7) * 2
    elif spell.get('extra_effect') == 'On Fire+GroundBurn':
        dmg += die_avg.get('2d6', 7) * 2
    elif spell.get('extra_effect') == 'Soaked+DoT':
        dmg += die_avg.get('2d6', 7) * 2

    return dmg


def attacks_per_round(char):
    n = 1
    if char.bap >= 2:
        n += char.bap // 2
    return n


def select_spell(char, settings, max_mana=None):
    spells_data = settings.get('spells', {})
    die_avg = settings['rules']['die_averages']
    best_element, best_aff_val = get_best_affinity(char)
    hit_chance = 0.75
    weapons = settings.get('weapons', {})
    weapon_info = weapons.get(char.gear.get('weapon', ''), {})

    candidates = []

    # Check elemental spells for best element
    if best_element and best_element in spells_data:
        for spell in spells_data[best_element]:
            if max_mana is not None and spell['mana'] > max_mana:
                continue
            if check_spell_prereqs(char, spell, best_element, best_aff_val):
                dmg = spell_avg_damage(spell, best_element, best_aff_val, die_avg, hit_chance, weapon_info)
                candidates.append((dmg, spell, best_element))

    # Check Generic spells
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
            dmg = spell_avg_damage(gspell, None, best_aff_val, die_avg, hit_chance, weapon_info)
            candidates.append((dmg, gspell, None))

    if not candidates:
        return None, 0

    # Pick highest damage per cast
    best = max(candidates, key=lambda x: x[0])
    return {'spell': best[1], 'element': best[2], 'damage_per_cast': best[0]}, best[0]


def calculate_damage(char, settings):
    result = {'melee': 0, 'ranged': 0, 'magic': 0, 'mana_cost': 0, 'magic_dmg': 0,
              'melee_per_hit': 0, 'ranged_per_hit': 0, 'attacks_per_turn': 1}

    hit_chance_base = 0.75
    die_avg = settings['rules']['die_averages']
    weapons = settings.get('weapons', {})
    weapon_name = char.gear.get('weapon', '')
    weapon_info = weapons.get(weapon_name, {})
    weapon_type = weapon_info.get('type', '')
    weapon_die = weapon_info.get('die')

    is_unarmed = char.is_unarmed or weapon_name == 'none' or weapon_name is None

    if is_unarmed:
        base_weapon = 0
        damage_bonus = 0
        extra_damage = 0
        weapon_type = 'melee'
    else:
        base_weapon = die_avg.get(weapon_die, 0) if weapon_die else 0
        damage_bonus = weapon_info.get('damage_bonus', 0)
        extra_damage_die = weapon_info.get('extra_damage_die')
        extra_damage = die_avg.get(extra_damage_die, 0) if extra_damage_die else 0

    accuracy_bonus = char.weapon_group_accuracy + char.steady_aim_accuracy
    if weapon_type == 'melee' and char.dual_wield_accuracy > 0 and not is_unarmed:
        accuracy_bonus += char.dual_wield_accuracy
    hit_chance = min(0.95, hit_chance_base + accuracy_bonus * 0.05)

    atk_per_round = attacks_per_round(char)

    if char.has_physical:
        pack_mult = 1.25 if getattr(char, 'pack_tactics', False) else 1.0

        melee_total_die = base_weapon + damage_bonus + extra_damage + char.melee_damage
        melee_per_hit = (melee_total_die + char.mod('str')) * pack_mult
        result['melee_per_hit'] = int(melee_per_hit * hit_chance)
        result['melee'] = result['melee_per_hit'] * atk_per_round

        ranged_total_die = base_weapon + damage_bonus + extra_damage + char.ranged_damage
        ranged_per_hit = ranged_total_die + char.mod('dex')
        result['ranged_per_hit'] = int(ranged_per_hit * hit_chance)
        result['ranged'] = result['ranged_per_hit'] * atk_per_round

    if char.has_magical:
        spell_info, spell_dmg = select_spell(char, settings)
        if spell_info:
            result['magic'] = int(spell_dmg)
            result['magic_dmg'] = spell_dmg
            result['mana_cost'] = spell_info['spell']['mana']

    result['per_turn'] = max(result['melee'], result['ranged'], result['magic'])
    result['attacks_per_turn'] = atk_per_round

    return result


def calculate_10_round_damage(char, r, dmg_per_turn, settings):
    atk_per_round = dmg_per_turn.get('attacks_per_turn', attacks_per_round(char))
    best_phys_dmg = max(dmg_per_turn['melee'], dmg_per_turn['ranged'])
    magic_dmg = dmg_per_turn['magic']
    mana_cost = dmg_per_turn['mana_cost']

    if not (magic_dmg > best_phys_dmg and mana_cost > 0):
        return {'total': 10 * best_phys_dmg,
                'mana_start': 0, 'mana_end': 0,
                'rounds_casting': 0,
                'mana_per_round': 0}

    max_mana = char.mana_max(r)
    total = 0
    remaining_mana = max_mana
    rounds_casting = 0

    for round_idx in range(10):
        spell_info, spell_dmg = select_spell(char, settings, max_mana=remaining_mana)
        if spell_info and spell_dmg > best_phys_dmg:
            cost = spell_info['spell']['mana']
            r_casts = min(atk_per_round, remaining_mana // cost) if cost > 0 else atk_per_round
            round_dmg = r_casts * spell_dmg
            remaining_mana -= r_casts * cost
            if r_casts > 0:
                rounds_casting += 1
        else:
            round_dmg = atk_per_round * best_phys_dmg
        total += round_dmg

    return {'total': int(total),
            'mana_start': int(max_mana),
            'mana_end': int(max(0, remaining_mana)),
            'rounds_casting': rounds_casting,
            'mana_per_round': int(mana_cost)}


def format_sheet(char, level, settings, dmg_perturn, dmg_10round, tier_label=None):
    r = settings['rules']
    lines = []
    sep = "=" * 60
    lines.append(sep)
    title = "  " + char.name + " - Level " + str(level)
    if tier_label:
        title += " (" + tier_label + ")"
    lines.append(title)
    lines.append(sep)
    lines.append("")

    die_avg = r['die_averages']
    con_mod = char.mod('con')
    wis_mod = char.mod('wis')
    
    vd = str(char.vit_n) + "d" + char.vit_die.split('d')[1]
    hd = str(char.hp_n) + "d" + char.hp_die.split('d')[1]
    md = str(char.mana_n) + "d" + char.mana_die.split('d')[1]

    lines.append("  STATS:")
    for stat in ['str', 'dex', 'con', 'wis', 'int', 'cha']:
        val = getattr(char, stat)
        start = getattr(char, 'starting_' + stat)
        if stat == 'str':
            lines.append("    STR: " + str(val).rjust(2) + " (" + format_mod(char.mod(stat)) + ") = " + str(start) + " + " + str(val - start))
        elif stat == 'dex':
            lines.append("    DEX: " + str(val).rjust(2) + " (" + format_mod(char.mod(stat)) + ") = " + str(start) + " + " + str(val - start))
        elif stat == 'con':
            lines.append("    CON: " + str(val).rjust(2) + " (" + format_mod(char.mod(stat)) + ") = " + str(start) + " + " + str(val - start))
        elif stat == 'wis':
            lines.append("    WIS: " + str(val).rjust(2) + " (" + format_mod(char.mod(stat)) + ") = " + str(start) + " + " + str(val - start))
        elif stat == 'int':
            lines.append("    INT: " + str(val).rjust(2) + " (" + format_mod(char.mod(stat)) + ") = " + str(start) + " + " + str(val - start))
        else:
            lines.append("    CHA: " + str(val).rjust(2) + " (" + format_mod(char.mod(stat)) + ") = " + str(start) + " + " + str(val - start))
    lines.append("")

    armor_type = char.gear.get('armor', 'none')
    lines.append("  COMBAT:")
    lines.append("    AC: " + str(char.ac(armor_type, settings.get('armor_types', {}), r['ac']['dex_bonus_table'])))
    lines.append("    Initiative: " + format_mod(char.mod('dex')))
    lines.append("    Speed: 30 ft")
    lines.append("    AP: " + str(char.ap) + "  BAP: " + str(char.bap) + "  RP: " + str(char.rp))
    lines.append("    Proficiency: +" + str(char.prof))
    if char.has_physical or char.has_magical:
        hit_parts = []
        if char.has_physical:
            if char.melee_accuracy > 0 or char.str >= 10:
                hit_parts.append("Melee: " + format_mod(char.to_hit_melee()))
            if char.ranged_accuracy > 0 or char.dex >= 10:
                hit_parts.append("Ranged: " + format_mod(char.to_hit_ranged()))
        if char.has_magical:
            hit_parts.append("Magic: " + format_mod(char.to_hit_magic()))
        lines.append("    To Hit: " + " | ".join(hit_parts))
    lines.append("")

    lines.append("  HEALTH POOLS:")
    lines.append("    Vitality: " + str(char.vit_max(r)) + " = " + vd + " (" + str(int(die_avg[char.vit_die])) + " x " + str(char.vit_n) + ") + " + str(char.flat_vit) + "(flat) + " + str(con_mod) + " x " + str(char.vit_n) + "(Con)")
    lines.append("    Health:  " + str(char.hp_max(r)) + " = " + hd + " (" + str(int(die_avg[char.hp_die])) + " x " + str(char.hp_n) + ") + " + str(char.flat_hp) + "(flat)")
    lines.append("    Mana:   " + str(char.mana_max(r)) + " = " + md + " (" + str(int(die_avg[char.mana_die])) + " x " + str(char.mana_n) + ") + " + str(wis_mod) + " x " + str(char.mana_n) + "(Wis)")
    lines.append("")

    lines.append("  DAMAGE:")
    atk = dmg_perturn.get('attacks_per_turn', 1)
    lines.append("    Attacks/Turn: " + str(atk))
    melee_hit = dmg_perturn.get('melee_per_hit', 0)
    ranged_hit = dmg_perturn.get('ranged_per_hit', 0)
    if melee_hit > 0:
        lines.append("    Melee Dmg/Hit: " + str(melee_hit) + " | Dmg/Turn: " + str(dmg_perturn['melee']))
    if ranged_hit > 0:
        lines.append("    Ranged Dmg/Hit: " + str(ranged_hit) + " | Dmg/Turn: " + str(dmg_perturn['ranged']))
    mana_cost = dmg_perturn['mana_cost']
    if mana_cost > 0:
        lines.append("    Magic Dmg/Cast: " + str(dmg_perturn['magic']) + " (x" + str(mana_cost) + " mana)")
    lines.append("    Total Dmg/10R: " + str(int(dmg_10round['total'])))
    if mana_cost > 0:
        rounds_casting = dmg_10round.get('rounds_casting', 0)
        mana_end = dmg_10round.get('mana_end', 0)
        mana_start = dmg_10round.get('mana_start', 0)
        lines.append("    Mana: " + str(mana_start) + " start, " + str(mana_end) + " after 10R" +
                      " (cast magic " + str(rounds_casting) + "/10 rounds)")
    lines.append("")

    lines.append("  RESOURCES:")
    lines.append("    Skill Points:  " + str(char.skill_points))
    lines.append("    Stat Points:   " + str(char.stat_points))
    lines.append("    Affinity Pts:  " + str(char.affinity_points))
    lines.append("    Stat Spent:    " + str(char.stat_points_spent))
    lines.append("")

    total_spells = char.starting_spells + char.spells_from_levels
    lines.append("  FEATS & SPELLS:")
    feat_count = char.feats
    if char.feats_taken:
        lines.append("    Feats:  " + str(feat_count) + " (taken: " + ", ".join(char.feats_taken) + ")")
    else:
        lines.append("    Feats:  " + str(feat_count))
    if char.feat_fallback_notes:
        for note in char.feat_fallback_notes:
            lines.append("    " + note)
    lines.append("    Spells:  " + str(total_spells))
    lines.append("")

    if char.archetype_levels:
        lines.append("  PATHS:")
        for (path, arch), lvl in char.archetype_levels.items():
            lines.append("    " + path + " -> " + arch + " (Lvl " + str(lvl) + ")")
        lines.append("")

    if char.affinities:
        lines.append("  AFFINITIES:")
        for aff, val in sorted(char.affinities.items()):
            lines.append("    " + aff.ljust(15) + ": " + str(val))
        lines.append("")

    if char.gear:
        lines.append("  GEAR:")
        weapons = settings.get('weapons', {})
        armor_types = settings.get('armor_types', {})
        weapon_info = weapons.get(char.gear.get('weapon', ''), {})
        armor_info = armor_types.get(char.gear.get('armor', ''), {})
        weapon_display = weapon_info.get('die') or ''
        weapon_name = char.gear.get('weapon', 'none')
        if weapon_name == 'none' or weapon_name is None:
            if char.is_unarmed and char.melee_extra_info:
                weapon_str = 'Unarmed (' + char.melee_extra_info + ')'
            else:
                weapon_str = 'Unarmed (1d4 Bludgeoning)'
        else:
            weapon_str = weapon_name + (f" ({weapon_display} {weapon_info.get('damage_type', '')})" if weapon_display else '')
        armor_str = char.gear.get('armor', 'none') + " (" + armor_info.get('label', '') + ")" if char.gear.get('armor') else 'none'
        lines.append("    Weapon: " + weapon_str)
        lines.append("    Armor: " + armor_str)
        lines.append("")

    return "\n".join(lines)


def resolve_gear(build_config, tier_config):
    gear = dict(build_config.get('gear', {}))
    tier_name = tier_config.get('name', '')

    if tier_name == 'no_gear':
        return {'weapon': None, 'armor': 'none'}

    if tier_name == 'bad_gear':
        return gear

    weapon = gear.get('weapon', '')
    armor = gear.get('armor', '')

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
    else:
        return gear

    return {
        'weapon': weapon_map.get(weapon, weapon),
        'armor': armor_map.get(armor, armor),
    }


def select_best_race(build_config, races_data):
    pickup = build_config.get('race', 'auto')
    if pickup != 'auto':
        for family_name, family in races_data.items():
            for subrace_name, data in family.get('subraces', {}).items():
                if subrace_name == pickup or family_name == pickup:
                    return family_name, subrace_name
        return None, None

    stat_priority = build_config.get('stat_priority', ['str', 'dex', 'con', 'wis', 'int', 'cha'])
    base_affinities = build_config.get('starting_affinities', {})
    is_magical = build_config.get('has_magical', False)
    primary_affinity = None
    if is_magical and base_affinities:
        sorted_affs = sorted(base_affinities.items(), key=lambda x: x[1], reverse=True)
        for aff, val in sorted_affs:
            if aff != 'Generic':
                primary_affinity = aff
                break

    best_score = -9999
    best_family = None
    best_subrace = None

    stat_weights = [10, 4, 2, 1, 0.5, 0.25]

    for family_name, family in races_data.items():
        for subrace_name, data in family.get('subraces', {}).items():
            if data.get('evolution_only'):
                continue

            score = 0
            bonuses = data.get('stat_bonuses', {})
            for i, stat in enumerate(stat_priority):
                if i >= len(stat_weights):
                    break
                bonus = bonuses.get(stat, 0)
                score += bonus * stat_weights[i]

            affinity_bonuses = data.get('affinity_bonuses', {})
            for aff, val in affinity_bonuses.items():
                if val > 0:
                    if aff == 'Generic':
                        score += 1
                    elif is_magical and aff == primary_affinity:
                        score += 10
                    elif aff in base_affinities:
                        score += 5
                    else:
                        score += 1
                elif val < 0:
                    if is_magical and aff == primary_affinity:
                        score -= 15
                    elif aff in base_affinities:
                        score -= 5
                    else:
                        score -= 1

            if score > best_score:
                best_score = score
                best_family = family_name
                best_subrace = subrace_name

    return best_family, best_subrace


def build_racial_archetype(race_data, race_family):
    archetype = {}
    for tier_num in range(1, 11):
        effects = {}
        effects['stat_points'] = tier_num // 2 + 1
        effects['affinity_points'] = tier_num
        if tier_num == 1:
            effects['tier1_racial'] = True
            effects['skill_points'] = 2
        elif tier_num == 3:
            effects['skill_points'] = 2
        elif tier_num == 5:
            effects['ac_bonus'] = 1
        elif tier_num == 7:
            effects['speed'] = 5
        elif tier_num == 10:
            effects['ac_bonus'] = 1
            effects['stat_points'] = 5
            effects['flat_vit'] = 20
            effects['flat_hp'] = 10
        archetype[str(tier_num)] = effects
    return archetype


def build_race_data(settings):
    races = settings.get('races', {})
    paths_rules = settings.get('paths', {})
    racial_path = paths_rules.get('Racial', {})
    if 'archetypes' not in racial_path:
        racial_path['archetypes'] = {}
    for family_name, family in races.items():
        for subrace_name, data in family.get('subraces', {}).items():
            arch_name = f"{family_name} {subrace_name}"
            if arch_name not in racial_path['archetypes']:
                racial_path['archetypes'][arch_name] = build_racial_archetype(data, family_name)
    return races


def generate_build(build_name, build_config, settings, levels, gear_override=None, tier_label=None):
    results = []

    # Build race data and ensure all racial archetypes exist
    all_races = build_race_data(settings)

    # Auto-select best race if set to "auto", otherwise use specified race
    race_pickup = build_config.get('race', None)
    if race_pickup:
        family_name, subrace_name = select_best_race(build_config, all_races)
        if family_name and subrace_name:
            race_data = all_races[family_name]['subraces'][subrace_name]
            arch_name = f"{family_name} {subrace_name}"
            # Inject the Racial path into the build config
            has_racial_path = any(p.get('path') == 'Racial' for p in build_config.get('paths', []))
            if not has_racial_path:
                build_config.setdefault('paths', []).append(
                    {"path": "Racial", "archetype": arch_name, "level": 10, "repeatables": {}}
                )
            # Ensure the archetype exists in paths data
            if arch_name not in settings['paths'].get('Racial', {}).get('archetypes', {}):
                settings['paths']['Racial']['archetypes'][arch_name] = build_racial_archetype(race_data, family_name)

    for level in levels:
        stats = build_config['base_stats']
        char = Character(build_name, stats, settings)
        char.has_physical = build_config.get('has_physical', False)
        char.has_magical = build_config.get('has_magical', False)
        char.affinities = build_config.get('starting_affinities', {"Generic": 1}).copy()
        char.gear = gear_override if gear_override is not None else build_config.get('gear', {})
        char.is_unarmed = build_config.get('unarmed_fighter', False) or char.gear.get('weapon', '') == 'none'
        char.tull_tier = 0

        # Apply race stat and affinity bonuses
        if race_pickup and family_name and subrace_name:
            race_data = all_races[family_name]['subraces'][subrace_name]
            race_bonuses = race_data.get('stat_bonuses', {})
            affinity_bonuses = race_data.get('affinity_bonuses', {})
            for stat, bonus in race_bonuses.items():
                if stat in ('str', 'dex', 'con', 'wis', 'int', 'cha'):
                    current = getattr(char, stat)
                    setattr(char, stat, current + bonus)
                    setattr(char, 'starting_' + stat, getattr(char, 'starting_' + stat) + bonus)
            for aff, val in affinity_bonuses.items():
                char.affinities[aff] = char.affinities.get(aff, 0) + val

        apply_level_progression(char, level, settings)

        if build_config.get('spend_stat_points') == 'all':
            priority = build_config.get('stat_priority', ['str','dex','con','wis','int','cha'])
            total_pts = char.stat_points + settings['rules']['starting_points']['stat_points']
            cost_table = settings['rules']['stat_point_cost']
            
            char_type = 'balanced'
            lower_name = build_name.lower()
            if 'tank' in lower_name:
                char_type = 'tank'
            elif 'archer' in lower_name:
                char_type = 'marksman'
            elif 'mage' in lower_name:
                char_type = 'caster'
            elif 'jack' in lower_name:
                char_type = 'jack'
            elif 'fighter' in lower_name:
                char_type = 'balanced'
            
            spend_stat_points(char, priority, total_pts, cost_table, char_type)
            char.stat_points = 0

        apply_paths(char, level, build_config, settings)

        # Apply Scholar ongoing bonuses retroactively
        for (path, arch), lvl in char.archetype_levels.items():
            if arch == 'Scholar':
                if lvl >= 1:
                    char.skill_points += max(0, level - 1)
                if lvl >= 2:
                    prof_gains = level // 3 + 1
                    char.skill_points += prof_gains * 3
                if lvl >= 3:
                    expr_gains = level // 8
                    char.skill_points += expr_gains * 5

        # Apply Tull unarmed damage based on racial tier
        if char.is_unarmed:
            tull_tier = char.tull_tier
            if tull_tier >= 9:
                char.melee_damage += 16  # 1d20 + 1d12 avg = 10.5 + 6.5 = 17
                char.melee_extra_info = "1d20 Slashing + 1d12 Bludgeoning (Tull Claws)"
            elif tull_tier >= 5:
                char.melee_damage += 10  # 1d10 + 1d8 avg = 5.5 + 4.5 = 10
                char.melee_extra_info = "1d10 Slashing + 1d8 Bludgeoning (Tull Claws)"
            elif tull_tier >= 1:
                char.melee_damage += 5  # 1d6 + 1d4 avg = 3.5 + 2.5 = 6
                char.melee_extra_info = "1d6 Slashing + 1d4 Bludgeoning (Tull Claws)"
            else:
                char.melee_damage += 2  # 1d4 Bludgeoning (fist)
                char.melee_extra_info = "1d4 Bludgeoning (Fist)"

            if tull_tier >= 3:
                char.pack_tactics = True

        select_feats(char, level, settings)

        spend_affinity_points(char, settings)

        dmg_perturn = calculate_damage(char, settings)
        dmg_10round = calculate_10_round_damage(char, settings['rules'], dmg_perturn, settings)

        sheet = format_sheet(char, level, settings, dmg_perturn, dmg_10round, tier_label)
        results.append({'level': level, 'char': char, 'sheet': sheet, 'dmg_perturn': dmg_perturn, 'dmg_10round': dmg_10round,
                        'race': f"{family_name} {subrace_name}" if race_pickup and family_name else 'none'})
    return results


def write_build_file(build_name, results, output_dir, tier_label=None):
    safe = build_name.replace(' ', '_').replace('/', '_')
    path = os.path.join(output_dir, safe + ".txt")
    with open(path, 'w') as f:
        header = "EYUM TTRPG - " + build_name.upper()
        if tier_label:
            header += " (" + tier_label.upper() + ")"
        f.write(header + "\n")
        f.write("=" * 60 + "\n\n")
        for r in results:
            f.write(r['sheet'] + "\n")
    return path


def write_average(all_results, settings, output_path):
    r = settings['rules']
    all_levels = set()
    for results in all_results.values():
        for res in results:
            all_levels.add(res['level'])
    all_levels = sorted(all_levels)

    with open(output_path, 'w') as f:
        f.write("EYUM TTRPG - AVERAGE STATS ACROSS ALL BUILDS\n")
        f.write("=" * 60 + "\n\n")

        for level in all_levels:
            f.write("LEVEL " + str(level) + "\n")
            f.write("-" * 40 + "\n")

            vitals = []
            healths = []
            manas = []
            acs = []
            feats = []
            spells = []
            dmg_per = []
            dmg_10r = []
            to_hits = []

            build_vitals = {}
            build_healths = {}
            build_manas = {}
            build_acs = {}
            build_feats = {}
            build_spells = {}
            build_dmg_per = {}
            build_dmg_10r = {}
            build_to_hits = {}

            for build_name, results in all_results.items():
                for res in results:
                    if res['level'] == level:
                        c = res['char']
                        d = res['dmg_perturn']
                        vit = c.vit_max(r)
                        hp = c.hp_max(r)
                        mana = c.mana_max(r)
                        ac_val = c.ac(c.gear.get('armor', 'none'), settings.get('armor_types', {}), r['ac']['dex_bonus_table'])
                        feat = c.feats
                        spell = c.starting_spells + c.spells_from_levels
                        dmg_t = d['per_turn']
                        dmg_10 = res['dmg_10round']['total'] if isinstance(res['dmg_10round'], dict) else res['dmg_10round']
                        best_hit = max(c.to_hit_melee(), c.to_hit_ranged(), c.to_hit_magic())

                        vitals.append(vit)
                        healths.append(hp)
                        manas.append(mana)
                        acs.append(ac_val)
                        feats.append(feat)
                        spells.append(spell)
                        dmg_per.append(dmg_t)
                        dmg_10r.append(dmg_10)
                        to_hits.append(best_hit)

                        build_vitals[build_name] = vit
                        build_healths[build_name] = hp
                        build_manas[build_name] = mana
                        build_acs[build_name] = ac_val
                        build_feats[build_name] = feat
                        build_spells[build_name] = spell
                        build_dmg_per[build_name] = dmg_t
                        build_dmg_10r[build_name] = dmg_10
                        build_to_hits[build_name] = best_hit
                        break

            if vitals:
                f.write("  Vitality:  avg=" + str(sum(vitals)//len(vitals)) +
                          "  min=" + str(min(vitals)) + "  max=" + str(max(vitals)) + "\n")
                f.write("  Health:    avg=" + str(sum(healths)//len(healths)) +
                          "  min=" + str(min(healths)) + "  max=" + str(max(healths)) + "\n")
                f.write("  Mana:      avg=" + str(sum(manas)//len(manas)) +
                          "  min=" + str(min(manas)) + "  max=" + str(max(manas)) + "\n")
                f.write("  AC:        avg=" + str(sum(acs)//len(acs)) +
                          "  min=" + str(min(acs)) + "  max=" + str(max(acs)) + "\n")
                f.write("  Feats:     avg=" + str(sum(feats)//len(feats)) +
                          "  min=" + str(min(feats)) + "  max=" + str(max(feats)) + "\n")
                f.write("  Spells:    avg=" + str(sum(spells)//len(spells)) +
                          "  min=" + str(min(spells)) + "  max=" + str(max(spells)) + "\n")
                f.write("  Dmg/Turn:  avg=" + str(sum(dmg_per)//len(dmg_per)) +
                          "  min=" + str(min(dmg_per)) + "  max=" + str(max(dmg_per)) + "\n")
                f.write("  Dmg/10R:   avg=" + str(sum(dmg_10r)//len(dmg_10r)) +
                          "  min=" + str(min(dmg_10r)) + "  max=" + str(max(dmg_10r)) + "\n")
                f.write("  To Hit:    avg=" + format_mod(sum(to_hits)//len(to_hits)) +
                          "  min=" + format_mod(min(to_hits)) + "  max=" + format_mod(max(to_hits)) + "\n")

                best_vit = max(build_vitals, key=build_vitals.get)
                best_hp = max(build_healths, key=build_healths.get)
                best_mana = max(build_manas, key=build_manas.get)
                best_ac = max(build_acs, key=build_acs.get)
                best_feat = max(build_feats, key=build_feats.get)
                best_spell = max(build_spells, key=build_spells.get)
                best_dmg = max(build_dmg_per, key=build_dmg_per.get)
                best_dmg10 = max(build_dmg_10r, key=build_dmg_10r.get)
                best_hit_name = max(build_to_hits, key=build_to_hits.get)

                f.write("\n  BEST:\n")
                f.write("    Vitality: " + best_vit + " (" + str(build_vitals[best_vit]) + ")\n")
                f.write("    Health:   " + best_hp + " (" + str(build_healths[best_hp]) + ")\n")
                f.write("    Mana:     " + best_mana + " (" + str(build_manas[best_mana]) + ")\n")
                f.write("    AC:       " + best_ac + " (" + str(build_acs[best_ac]) + ")\n")
                f.write("    Feats:    " + best_feat + " (" + str(build_feats[best_feat]) + ")\n")
                f.write("    Spells:   " + best_spell + " (" + str(build_spells[best_spell]) + ")\n")
                f.write("    Dmg:      " + best_dmg + " (" + str(build_dmg_per[best_dmg]) + ")\n")
                f.write("    Dmg/10R:  " + best_dmg10 + " (" + str(build_dmg_10r[best_dmg10]) + ")\n")
                f.write("    To Hit:   " + best_hit_name + " (" + format_mod(build_to_hits[best_hit_name]) + ")\n")
            f.write("\n")


def write_overall_averages(tier_data, all_tier_results, settings, output_path):
    with open(output_path, 'w') as f:
        f.write("EYUM TTRPG - OVERALL AVERAGES ACROSS ALL GEAR TIERS\n")
        f.write("=" * 60 + "\n\n")

        all_levels = set()
        for tier_name, all_results in all_tier_results:
            for results in all_results.values():
                for res in results:
                    all_levels.add(res['level'])
        all_levels = sorted(all_levels)

        for level in all_levels:
            f.write("LEVEL " + str(level) + "\n")
            f.write("-" * 40 + "\n")

            for tier_name, all_results in all_tier_results:
                vitals = []
                healths = []
                manas = []
                acs_vals = []
                dmg_t = []
                dmg_10 = []
                to_hits = []
                for build_name, results in all_results.items():
                    for res in results:
                        if res['level'] == level:
                            c = res['char']
                            vitals.append(c.vit_max(settings['rules']))
                            healths.append(c.hp_max(settings['rules']))
                            manas.append(c.mana_max(settings['rules']))
                            acs_vals.append(c.ac(c.gear.get('armor', 'none'), settings.get('armor_types', {}), settings['rules']['ac']['dex_bonus_table']))
                            dmg_t.append(res['dmg_perturn']['per_turn'])
                            dmg_10.append(res['dmg_10round']['total'] if isinstance(res['dmg_10round'], dict) else res['dmg_10round'])
                            to_hits.append(max(c.to_hit_melee(), c.to_hit_ranged(), c.to_hit_magic()))
                            break
                
                avg_hit = sum(to_hits) // len(to_hits)
                label_padded = tier_name.replace('_', ' ').title().ljust(15)
                f.write("  " + label_padded + ": AC=" + str(sum(acs_vals)//len(acs_vals)).rjust(2) +
                        "  Vit=" + str(sum(vitals)//len(vitals)).rjust(5) +
                        "  HP=" + str(sum(healths)//len(healths)).rjust(4) +
                        "  Mana=" + str(sum(manas)//len(manas)).rjust(5) +
                        "  Hit=" + format_mod(avg_hit).rjust(4) +
                        "  Dmg=" + str(sum(dmg_t)//len(dmg_t)).rjust(4) +
                        "  Dmg/10R=" + str(sum(dmg_10)//len(dmg_10)).rjust(6) + "\n")
            f.write("\n")


CATEGORIES = ['Vitality', 'Health', 'Mana', 'AC', 'Feats', 'Spells', 'To Hit', 'Dmg/Turn', 'Dmg/10R']


def get_best_per_build(results, level, r, armor_types, dex_table):
    r = r
    for res in results:
        if res['level'] == level:
            c = res['char']
            d = res['dmg_perturn']
            return {
                'Vitality': c.vit_max(r),
                'Health': c.hp_max(r),
                'Mana': c.mana_max(r),
                'AC': c.ac(c.gear.get('armor', 'none'), armor_types, dex_table),
                'Feats': c.feats,
                'Spells': c.starting_spells + c.spells_from_levels,
                'To Hit': max(c.to_hit_melee(), c.to_hit_ranged(), c.to_hit_magic()),
                'Dmg/Turn': d['per_turn'],
                'Dmg/10R': res['dmg_10round']['total'] if isinstance(res['dmg_10round'], dict) else res['dmg_10round'],
                'char': c,
            }
    return None


def write_summary(all_tier_results, settings, output_path, build_configs=None):
    r = settings['rules']
    armor_types = settings.get('armor_types', {})
    dex_table = r['ac']['dex_bonus_table']

    if build_configs is None:
        build_configs = {}

    all_levels = set()
    for tier_name, all_results in all_tier_results:
        for results in all_results.values():
            for res in results:
                all_levels.add(res['level'])
    all_levels = sorted(all_levels)

    # Collect: for each tier, each level, each category, which build won
    # tier_level_wins[tier_name][category][build_name] = count of levels won
    tier_level_wins = {}
    for tier_name, all_results in all_tier_results:
        tier_level_wins[tier_name] = {cat: {} for cat in CATEGORIES}
        for level in all_levels:
            build_scores = {}
            for build_name, results in all_results.items():
                scores = get_best_per_build(results, level, r, armor_types, dex_table)
                if scores:
                    build_scores[build_name] = scores
            for cat in CATEGORIES:
                best_val = -1
                winners = []
                for bn, sc in build_scores.items():
                    v = sc[cat]
                    if v > best_val:
                        best_val = v
                        winners = [bn]
                    elif v == best_val and v >= 0:
                        winners.append(bn)
                for w in winners:
                    tier_level_wins[tier_name][cat][w] = tier_level_wins[tier_name][cat].get(w, 0) + 1

    # Overall across all tiers
    all_build_names = set()
    for tier_name in tier_level_wins:
        for cat in CATEGORIES:
            for build_name in tier_level_wins[tier_name][cat]:
                all_build_names.add(build_name)

    overall_wins = {cat: {} for cat in CATEGORIES}
    for tier_name in tier_level_wins:
        for cat in CATEGORIES:
            for build_name, count in tier_level_wins[tier_name][cat].items():
                overall_wins[cat][build_name] = overall_wins[cat].get(build_name, 0) + count

    total_levels_per_tier = len(all_levels)
    total_wins_possible = total_levels_per_tier * len(CATEGORIES)

    with open(output_path, 'w') as f:
        f.write("EYUM TTRPG - BALANCE SUMMARY & RECOMMENDATIONS\n")
        f.write("=" * 60 + "\n\n")
        f.write("Generated from analysis of " + str(len(all_levels)) + " levels")
        f.write(" across " + str(len(all_tier_results)) + " gear tiers")
        f.write(" and " + str(len(all_build_names)) + " builds.\n\n")

        # --- OVERALL BUILD DOMINANCE ---
        f.write("OVERALL BUILD DOMINANCE\n")
        f.write("-" * 40 + "\n")
        sorted_builds = sorted(all_build_names,
                               key=lambda b: sum(overall_wins[c].get(b, 0) for c in CATEGORIES),
                               reverse=True)
        total_cross_cat_wins = sum(sum(overall_wins[c].values()) for c in CATEGORIES) or 1
        for bn in sorted_builds:
            total = sum(overall_wins[c].get(bn, 0) for c in CATEGORIES)
            pct = total * 100 / total_cross_cat_wins
            f.write("  " + bn.ljust(18) + ": " + str(total).rjust(3) + " category-level wins (" + format(pct, '.1f') + "%)\n")
        f.write("\n")

        # Detect domination
        if sorted_builds:
            top_build = sorted_builds[0]
            top_total = sum(overall_wins[c].get(top_build, 0) for c in CATEGORIES)
            top_pct = top_total * 100 / total_cross_cat_wins
            second_pct = 0
            if len(sorted_builds) > 1:
                second = sorted_builds[1]
                second_total = sum(overall_wins[c].get(second, 0) for c in CATEGORIES)
                second_pct = second_total * 100 / total_cross_cat_wins

            if top_pct > 50:
                f.write("  >>> WARNING: " + top_build + " dominates with " + format(top_pct, '.1f') +
                        "% of all BEST wins across all tiers.\n")
                f.write("      This suggests significant balance issues where other builds cannot compete.\n")
                if second_pct > 0:
                    f.write("      Next best (" + sorted_builds[1] + ") has only " + format(second_pct, '.1f') + "%.\n")
            elif top_pct > 35:
                f.write("  >>> NOTE: " + top_build + " leads with " + format(top_pct, '.1f') +
                        "% of BEST wins, which may indicate it is slightly over-tuned.\n")
            else:
                f.write("  >>> OK: No single build dominates. Top build (" + top_build + ") has " +
                        format(top_pct, '.1f') + "% of wins.\n")
        f.write("\n")

        # --- DAMAGE TYPE BALANCE ---
        f.write("DAMAGE TYPE BALANCE\n")
        f.write("-" * 40 + "\n")
        magical_builds = []
        physical_builds = []
        mixed_builds = []
        for bn in sorted_builds:
            bc = build_configs.get(bn, {})
            has_phys = bc.get('has_physical', False)
            has_mag = bc.get('has_magical', False)
            if has_phys and has_mag:
                mixed_builds.append(bn)
            elif has_mag:
                magical_builds.append(bn)
            else:
                physical_builds.append(bn)

        def total_dmg_wins(builds):
            return sum(overall_wins['Dmg/Turn'].get(b, 0) for b in builds) + \
                   sum(overall_wins['Dmg/10R'].get(b, 0) for b in builds)

        magic_dmg_wins = total_dmg_wins(magical_builds)
        phys_dmg_wins = total_dmg_wins(physical_builds)
        mixed_dmg_wins = total_dmg_wins(mixed_builds)
        total_dmg = magic_dmg_wins + phys_dmg_wins + mixed_dmg_wins or 1

        f.write("  Magical builds  : " + str(magic_dmg_wins).rjust(3) + " damage BEST wins (" +
                format(magic_dmg_wins * 100 / total_dmg, '.1f') + "%)\n")
        f.write("  Physical builds : " + str(phys_dmg_wins).rjust(3) + " damage BEST wins (" +
                format(phys_dmg_wins * 100 / total_dmg, '.1f') + "%)\n")
        if mixed_builds:
            f.write("  Mixed builds    : " + str(mixed_dmg_wins).rjust(3) + " damage BEST wins (" +
                    format(mixed_dmg_wins * 100 / total_dmg, '.1f') + "%)\n")

        ratio_magic = magic_dmg_wins / (phys_dmg_wins + 1)
        if ratio_magic < 0.5:
            f.write("\n  >>> Physical builds dominate damage output (" +
                    format(phys_dmg_wins * 100 / total_dmg, '.1f') +
                    "% vs " + format(magic_dmg_wins * 100 / total_dmg, '.1f') +
                    "% magical).\n")
            f.write("      Consider: increasing base spell damage, reducing spell mana cost,\n")
            f.write("      or adding more magical gear with magic_bonus.\n")
        elif ratio_magic > 2:
            f.write("\n  >>> Magical builds dominate damage output. Consider buffing physical options.\n")
        else:
            f.write("\n  >>> Damage type balance is reasonable.\n")
        f.write("\n")

        # --- CATEGORY MONOPOLY ---
        f.write("CATEGORY MONOPOLY ANALYSIS\n")
        f.write("-" * 40 + "\n")
        for cat in CATEGORIES:
            sorted_cat = sorted(overall_wins[cat].items(), key=lambda x: x[1], reverse=True)
            if not sorted_cat:
                continue
            top_name, top_count = sorted_cat[0]
            top_pct = top_count * 100 / (total_levels_per_tier * len(all_tier_results))

            all_same = len(set(overall_wins[cat].values())) <= 1
            if all_same and len(overall_wins[cat]) > 1:
                f.write("  " + cat.ljust(10) + ": tied across all builds")
                f.write(" (all " + str(top_count) + "/" + str(total_levels_per_tier * len(all_tier_results)) + ")\n")
                if cat == 'Feats':
                    f.write("    (Expected: every build gets +1 feat every 3 levels. No action needed.)\n")
                continue

            f.write("  " + cat.ljust(10) + ": mostly " + top_name + " (" +
                    str(top_count) + "/" + str(total_levels_per_tier * len(all_tier_results)) +
                    " levels, " + format(top_pct, '.1f') + "%)\n")

            if top_pct > 80:
                f.write("    >>> MONOPOLY: " + top_name + " wins " + cat + " almost exclusively.\n")
                if cat in ('Vitality', 'Health'):
                    f.write("    This is expected for dedicated tank builds. No action needed.\n")
                elif cat in ('Mana', 'Spells'):
                    f.write("    This is expected for magical builds. No action needed.\n")
                elif cat == 'AC':
                    f.write("    This is expected for tank/heavy-armor builds. No action needed.\n")
                elif cat == 'Feats':
                    f.write("    (Tied across all builds since every build gets +1 feat every 3 levels.)\n")
                elif cat in ('Dmg/Turn', 'Dmg/10R'):
                    f.write("    >>> IMBALANCE: Damage output is concentrated in one build.\n")
                    f.write("    Consider: rebalancing damage scaling so other builds can compete.\n")
            elif top_pct < 40:
                f.write("    (Well-distributed across multiple builds)\n")
            else:
                f.write("    (Moderate concentration)\n")
        f.write("\n")

        # --- TIER ANALYSIS ---
        f.write("GEAR TIER IMPACT\n")
        f.write("-" * 40 + "\n")
        for tier_name, all_results in all_tier_results:
            f.write("  " + tier_name.replace('_', ' ').title() + ":\n")
            tier_build_dmg = {}
            for build_name, results in all_results.items():
                build_dmg_sum = 0
                count = 0
                for res in results:
                    build_dmg_sum += res['dmg_perturn']['per_turn']
                    count += 1
                if count > 0:
                    tier_build_dmg[build_name] = build_dmg_sum / count
            sorted_tier = sorted(tier_build_dmg.items(), key=lambda x: x[1], reverse=True)
            for bn, avg_d in sorted_tier[:3]:
                f.write("    " + bn.ljust(18) + ": avg dmg/turn " + format(avg_d, '.1f') + "\n")

            if len(all_tier_results) > 1:
                prev_tier_name, prev_results = all_tier_results[0]
                if prev_results is not all_results:
                    prev_dmg = {}
                    for bn, results in prev_results.items():
                        prev_dmg_sum = 0
                        count = 0
                        for res in results:
                            prev_dmg_sum += res['dmg_perturn']['per_turn']
                            count += 1
                        if count > 0:
                            prev_dmg[bn] = prev_dmg_sum / count
                    biggest_gainer = None
                    biggest_gain = 0
                    for bn in tier_build_dmg:
                        if bn in prev_dmg and prev_dmg[bn] > 0:
                            gain = (tier_build_dmg[bn] - prev_dmg[bn]) / prev_dmg[bn] * 100
                            if gain > biggest_gain:
                                biggest_gain = gain
                                biggest_gainer = bn
                    if biggest_gainer and biggest_gain > 10:
                        f.write("    >> " + biggest_gainer + " benefits most from this tier (+" +
                                format(biggest_gain, '.0f') + "% dmg vs previous tier).\n")
        f.write("\n")

        # --- LEVEL RANGE ANALYSIS ---
        f.write("PROGRESSION BALANCE (EARLY vs LATE)\n")
        f.write("-" * 40 + "\n")
        brackets = [
            ("Level 5  (1-5)", [l for l in all_levels if l <= 5]),
            ("Level 10 (6-10)", [l for l in all_levels if 6 <= l <= 10]),
            ("Level 15 (11-15)", [l for l in all_levels if 11 <= l <= 15]),
            ("Level 20 (16-20)", [l for l in all_levels if 16 <= l <= 20]),
            ("Level 30 (21-30)", [l for l in all_levels if 21 <= l <= 30]),
            ("Level 50+ (50+)", [l for l in all_levels if l >= 50]),
        ]

        for tier_name, all_results in all_tier_results:
            f.write("  " + tier_name.replace('_', ' ').title() + ":\n")
            for label, lvls in brackets:
                if not lvls:
                    continue
                dmg_leaders = {}
                for lvl in lvls:
                    best_bn = None
                    best_d = -1
                    for bn, results in all_results.items():
                        for res in results:
                            if res['level'] == lvl:
                                d = res['dmg_perturn']['per_turn']
                                if d > best_d:
                                    best_d = d
                                    best_bn = bn
                                break
                    if best_bn:
                        dmg_leaders[best_bn] = dmg_leaders.get(best_bn, 0) + 1
                if dmg_leaders:
                    top_leader = max(dmg_leaders, key=dmg_leaders.get)
                    f.write("    " + label.ljust(15) + ": dmg leader " + top_leader +
                            " (" + str(dmg_leaders[top_leader]) + "/" + str(len(lvls)) + " levels)\n")
            f.write("\n")

        # --- DETAILED RECOMMENDATIONS ---
        f.write("DETAILED RECOMMENDATIONS\n")
        f.write("-" * 40 + "\n")
        reco_count = 0

        def write_reco(rec):
            nonlocal reco_count
            reco_count += 1
            f.write("  " + str(reco_count) + ". " + rec + "\n")

        if magic_dmg_wins < phys_dmg_wins * 0.5:
            write_reco(
                "Magical builds are significantly underperforming in damage (only " +
                format(magic_dmg_wins * 100 / total_dmg, '.0f') +
                "% of damage BEST wins vs " + format(phys_dmg_wins * 100 / total_dmg, '.0f') +
                "% for physical).\n"
                "       - Increase base spell damage formula (currently 1 + best_aff + gen_aff).\n"
                "       - Add more mana regeneration or reduce spell mana cost.\n"
                "       - Consider adding magic_bonus to more magical weapons (e.g., staff, focus).\n"
                "       - Verify affinity damage bonuses (e.g., fire_damage_bonus 1d4) scale with level."
            )
        elif phys_dmg_wins < magic_dmg_wins * 0.5:
            write_reco(
                "Physical builds are underperforming in damage (" +
                format(phys_dmg_wins * 100 / total_dmg, '.0f') +
                "% of damage BEST wins vs " + format(magic_dmg_wins * 100 / total_dmg, '.0f') +
                "% for magical).\n"
                "       - Increase base weapon damage or weapon damage_bonus values.\n"
                "       - Add more damage-boosting feats for physical builds.\n"
                "       - Check if extra_damage_die on weapons is being applied correctly."
            )
        else:
            write_reco(
                "Physical and magical damage are reasonably balanced (" +
                format(phys_dmg_wins * 100 / total_dmg, '.0f') +
                "% vs " + format(magic_dmg_wins * 100 / total_dmg, '.0f') +
                "%). Monitor as new content is added."
            )

        if sorted_builds:
            top = sorted_builds[0]
            top_total = sum(overall_wins[c].get(top, 0) for c in CATEGORIES)
            top_pct2 = top_total * 100 / total_cross_cat_wins
            if top_pct2 > 50:
                write_reco(
                    top + " wins " + format(top_pct2, '.0f') +
                    "% of all BEST categories, indicating severe over-tuning.\n"
                    "       - Reduce " + top + "'s stat scaling or damage output.\n"
                    "       - Verify " + top + " is not receiving unintended bonuses from paths or gear.\n"
                    "       - Consider splitting its advantages across multiple builds."
                )
            elif top_pct2 > 35:
                write_reco(
                    top + " leads with " + format(top_pct2, '.0f') +
                    "% of BEST wins. Consider minor reductions to bring it in line."
                )

        for cat in CATEGORIES:
            sorted_cat = sorted(overall_wins[cat].items(), key=lambda x: x[1], reverse=True)
            if not sorted_cat:
                continue
            top_name, top_count = sorted_cat[0]
            top_pct3 = top_count * 100 / (total_levels_per_tier * len(all_tier_results))
            if top_pct3 > 80:
                if cat in ('Dmg/Turn', 'Dmg/10R'):
                    write_reco(
                        top_name + " has a monopoly on " + cat +
                        " (" + format(top_pct3, '.0f') + "%).\n" +
                        "       - Rebalance damage formulas so other builds can compete in this category.\n" +
                        "       - Check if " + top_name + " has unintended damage synergies."
                    )
                elif cat == 'Feats':
                    all_feat_same = len(set(overall_wins['Feats'].values())) <= 1
                    if not all_feat_same:
                        write_reco(
                            top_name + " dominates Feat accumulation (" + format(top_pct3, '.0f') +
                            "%).\n" +
                            "       - Ensure other builds have feat access through their path choices."
                        )

        late_levels = [l for l in all_levels if l > 30]
        if late_levels and magical_builds:
            late_magic_wins = 0
            late_phys_wins = 0
            for tier_name, all_results in all_tier_results:
                for lvl in late_levels:
                    best_dmg_bn = None
                    best_dmg_val = -1
                    for bn, results in all_results.items():
                        for res in results:
                            if res['level'] == lvl:
                                d = res['dmg_perturn']['per_turn']
                                if d > best_dmg_val:
                                    best_dmg_val = d
                                    best_dmg_bn = bn
                                break
                    if best_dmg_bn:
                        if best_dmg_bn.lower() in ('pyromancer', 'priest', 'necromancer'):
                            late_magic_wins += 1
                        elif best_dmg_bn.lower() in ('physical tank', 'marksman'):
                            late_phys_wins += 1
            if late_magic_wins < late_phys_wins * 0.5 and late_phys_wins > 0:
                write_reco(
                    "Magical builds fall behind physically in late-game damage (" +
                    str(late_magic_wins) + " vs " + str(late_phys_wins) + " late-game level wins).\n"
                    "       - Add late-game spell upgrades or scaling mechanics for magic.\n"
                    "       - Consider spell level-scaling (e.g., damage increases with character level)."
                )

        jack_wins = sum(overall_wins[c].get('Jack', 0) for c in CATEGORIES)
        if jack_wins == 0:
            write_reco(
                "Jack (hybrid build) wins no BEST categories.\n"
                "       - This may be acceptable if Jack's niche is flexibility, not specialization.\n"
                "       - If Jack should be viable, consider giving it unique hybrid bonuses or more skill/stat points."
            )
        elif jack_wins < total_cross_cat_wins * 0.05:
            write_reco(
                "Jack has very few BEST wins (" + str(jack_wins) +
                "), suggesting the hybrid trade-off may be too costly."
            )

        if reco_count == 0:
            f.write("  No specific issues detected. The builds appear well-balanced.\n")

        f.write("\n")
        f.write("=" * 60 + "\n")
        f.write("End of summary\n")


def main():
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    settings_path = os.path.join(script_dir, "settings.json")
    settings = load_json(settings_path)

    base_output_dir = os.path.join(script_dir, "output")
    os.makedirs(base_output_dir, exist_ok=True)

    levels = settings['generation']['levels']
    gear_tiers = settings.get('gear_tiers', [{"name": "bad_gear", "label": "Bad Gear (Iron/Base)"}])

    all_tier_results = []

    for tier in gear_tiers:
        tier_name = tier['name']
        tier_label = tier['label']
        tier_dir = os.path.join(base_output_dir, tier_name)
        os.makedirs(tier_dir, exist_ok=True)

        all_results = {}
        print("\n=== Gear Tier: " + tier_label + " ===")

        for build_name, build_config in settings['builds'].items():
            if not build_config.get('generate', True):
                continue

            print("  Generating: " + build_name + " (levels: " + str(levels) + ")")
            gear_override = resolve_gear(build_config, tier) if 'gear' in build_config else None
            results = generate_build(build_name, build_config, settings, levels, gear_override, tier_label)
            all_results[build_name] = results

            if settings['generation'].get('separate_files', True):
                path = write_build_file(build_name, results, tier_dir, tier_label)
                print("    -> " + path)

        if settings['generation'].get('generate_average', True):
            avg_path = os.path.join(tier_dir, "average.txt")
            write_average(all_results, settings, avg_path)
            print("    Average stats -> " + avg_path)

        all_tier_results.append((tier_name, all_results))

    # Root-level overall averages across all tiers
    overall_path = os.path.join(script_dir, "averages.txt")
    write_overall_averages(gear_tiers, all_tier_results, settings, overall_path)
    print("\nOverall averages across tiers -> " + overall_path)

    # Balance summary
    summary_path = os.path.join(script_dir, "summary.txt")
    write_summary(all_tier_results, settings, summary_path, settings['builds'])
    print("Balance summary -> " + summary_path)

    print("\nDone!")


if __name__ == "__main__":
    main()