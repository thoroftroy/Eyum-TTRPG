#!/usr/bin/env python3
"""
Eyum TTRPG Character Sheet Generator
Fixed to properly account for:
- Stat point cost scaling (higher stats cost more)
- All Level-up bonuses per handbook
- Individual breakdown of each stat/pool
- Damage calculations
"""

import os
import sys

from lib.config import load_settings
from lib.character import Character
from lib.effects import apply_effects
from lib.paths import apply_level_progression, apply_paths
from lib.feats import select_feats
from lib.stats import spend_stat_points, spend_affinity_points
from lib.combat import calculate_damage, calculate_5_round_damage, calculate_10_round_damage
from lib.gear import resolve_gear
from lib.races import select_best_race, build_racial_archetype, build_race_data
from lib.output import format_sheet, write_build_file, write_average, write_overall_averages, write_summary

DIE_AVERAGES_PRELOAD = {}


def score_effect_for_build(effect_key, effect_val, build_config, arch_name=''):
    score = 0
    stat_priority = build_config.get('stat_priority', [])
    stat_weights = [10, 4, 2, 1, 0.5, 0.25]
    is_physical = build_config.get('has_physical', False)
    is_magical = build_config.get('has_magical', False)

    if effect_key == 'stat':
        for stat, bonus in effect_val.items():
            if stat in ('str', 'dex', 'con', 'wis', 'int', 'cha'):
                for i, s in enumerate(stat_priority):
                    if s == stat and i < len(stat_weights):
                        score += bonus * stat_weights[i]
    elif effect_key == 'melee_damage':
        if is_physical:
            score += effect_val * 15
    elif effect_key == 'ranged_damage':
        if is_physical:
            score += effect_val * 15
    elif effect_key == 'magic_damage':
        if is_magical:
            score += effect_val * 15
    elif effect_key == 'melee_accuracy':
        if is_physical:
            score += effect_val * 10
    elif effect_key == 'ranged_accuracy':
        if is_physical:
            score += effect_val * 10
    elif effect_key == 'magic_accuracy':
        if is_magical:
            score += effect_val * 10
    elif effect_key == 'weapon_group_accuracy':
        if is_physical:
            score += effect_val * 10
    elif effect_key == 'ac_bonus':
        score += effect_val * 8
    elif effect_key == 'flat_vit':
        score += effect_val * 0.5
    elif effect_key == 'flat_hp':
        score += effect_val * 0.3
    elif effect_key == 'affinity_points':
        if is_magical:
            score += effect_val * 5
    elif effect_key == 'affinity':
        if is_magical:
            for aff, val in effect_val.items():
                score += val * 3
    elif effect_key == 'skill_points':
        score += effect_val * 1
    elif effect_key == 'stat_points':
        score += effect_val * 6
    elif effect_key == 'extra_attack_bap':
        if is_physical:
            score += 20
    elif effect_key == 'pack_tactics':
        if is_physical:
            score += 8
    elif effect_key == 'initiative':
        score += effect_val * 3
    elif effect_key == 'speed':
        score += effect_val * 2
    elif effect_key == 'fly_speed':
        score += effect_val * 2
    elif effect_key == 'skill_points_per_level':
        score += 8
    elif effect_key == 'proficiency_per_level':
        score += 8
    elif effect_key == 'expertise_per_level':
        score += 8
    elif effect_key == 'affinity_per_level':
        if is_magical:
            score += 10
    elif effect_key == 'feat_per_feat':
        score += 15
    elif effect_key == 'damage_reduction':
        score += effect_val * 3
    elif effect_key == 'spell':
        if is_magical:
            score += effect_val * 5
    elif effect_key == 'mana_dice_count':
        if is_magical:
            score += effect_val * 5
    elif effect_key == 'mana_per_level':
        if is_magical:
            score += effect_val * 3
    elif effect_key == 'hp_per_level':
        score += effect_val * 3
    elif effect_key == 'vit_per_level':
        score += effect_val * 3
    elif effect_key == 'brawler_stacks':
        if is_physical:
            score += effect_val * 8
    elif effect_key == 'antideity_damage' or effect_key == 'anti_deity_damage':
        score += 10
    elif effect_key == 'hallowed_affinity':
        if is_magical:
            score += effect_val * 3
    elif effect_key == 'eldritch_affinity':
        if is_magical:
            score += effect_val * 3
    elif effect_key == 'karma':
        score += 0
    elif effect_key == 'pact_access_tier':
        score += 2
    elif effect_key == 'tier_racial':
        score += 3
    elif effect_key == 'initiative_advantage':
        score += 5
    elif effect_key == 'first_round_damage':
        score += 3
    elif effect_key == 'ap_first_round':
        score += 3
    elif effect_key == 'first_round_advantage':
        score += 5
    elif effect_key == 'true_sight_range':
        score += effect_val * 0.5
    elif effect_key == 'darkvision_range':
        score += effect_val * 0.3
    elif effect_key == 'magic_blast':
        if is_magical:
            score += 3
    elif effect_key == 'generic_affinity':
        if is_magical:
            score += effect_val * 3
    elif effect_key == 'bap':
        score += effect_val * 8
    elif effect_key == 'rp':
        score += effect_val * 5
    elif effect_key == 'ap':
        score += effect_val * 6
    elif effect_key == 'ranged_adv_damage':
        if is_physical:
            score += effect_val * 4
    elif effect_key == 'ranged_expertise':
        if is_physical:
            score += 5
    elif effect_key == 'spell_damage_mult':
        if is_magical:
            score += effect_val * 20
    elif effect_key == 'spell_mana_mult':
        if is_magical:
            score += effect_val * -8

    return score


def score_archetype_for_build(arch_name, arch_data, build_config):
    total = 0
    for tier_key, effects in arch_data.items():
        tier_num = float(tier_key)
        repeatable = effects.get('repeatable', False)
        multiplier = 1.0
        if tier_num != int(tier_num) and not repeatable:
            multiplier = 0.6
        elif repeatable:
            multiplier = 0.3
        for ek, ev in effects.items():
            if ek == 'repeatable':
                continue
            total += score_effect_for_build(ek, ev, build_config, arch_name) * multiplier

    if arch_name == 'Indomitable':
        total -= 20
    if arch_name == 'Magician':
        total -= 20

    primary_aff = build_config.get('primary_affinity')
    if primary_aff:
        arch_aff_map = {
            'Pyromancer': 'Fire', 'Geomancer': 'Earth',
            'Tidemaster': 'Water', 'Windwalker': 'Air',
            'Priest': 'Radiant', 'Necromancer': 'Necrotic'
        }
        mapped = arch_aff_map.get(arch_name)
        if mapped:
            if mapped == primary_aff:
                total += 30
            else:
                total -= 20

    return total


def select_archetypes(build_config, settings, target_level):
    available_stp = 1 + (target_level // 2)
    path_rules = settings['paths']
    preferred = build_config.get('preferred_paths', list(path_rules.keys()))

    arch_scores = []
    for path_name in preferred:
        path_data = path_rules.get(path_name, {})
        archs = path_data.get('archetypes', {})
        for arch_name, arch_data in archs.items():
            score = score_archetype_for_build(arch_name, arch_data, build_config)
            base_tiers = sum(1 for k in arch_data if float(k) == int(float(k)) and not arch_data[k].get('repeatable', False))
            arch_scores.append((score, path_name, arch_name, base_tiers))

    reverse_sort = not build_config.get('worst', False)
    arch_scores.sort(key=lambda x: x[0], reverse=reverse_sort)

    result = []
    stp_remaining = available_stp
    paths_unlocked = set()

    for score, path_name, arch_name, base_tiers in arch_scores:
        if stp_remaining <= 0:
            break

        path_cost = 1 if path_name not in paths_unlocked else 0
        if path_cost == 1:
            if stp_remaining < 1:
                continue
            stp_remaining -= 1
            paths_unlocked.add(path_name)

        levels = min(stp_remaining, base_tiers)
        if levels > 0:
            result.append({"path": path_name, "archetype": arch_name, "level": levels, "repeatables": {}})
            stp_remaining -= levels

    return result


def generate_build(build_name, build_config, settings, levels, gear_override=None, tier_label=None):
    results = []

    all_races = build_race_data(settings)

    is_worst = build_config.get('worst', False)
    is_casual = build_name.lower().startswith('casual ')
    family_name = None
    subrace_name = None
    if not is_worst and not is_casual and 'preferred_paths' in build_config and ('paths' not in build_config or not build_config.get('paths')):
        max_level = max(levels)
        dynamic_paths = select_archetypes(build_config, settings, max(levels))
        build_config['paths'] = dynamic_paths

    race_pickup = build_config.get('race', None)
    if race_pickup and not is_worst and not is_casual:
        family_name, subrace_name = select_best_race(build_config, all_races)
        if family_name and subrace_name:
            race_data = all_races[family_name]['subraces'][subrace_name]
            arch_name = f"{family_name} {subrace_name}"
            has_racial_path = any(p.get('path') == 'Racial' for p in build_config.get('paths', []))
            if not has_racial_path:
                build_config.setdefault('paths', []).append(
                    {"path": "Racial", "archetype": arch_name, "level": 10, "repeatables": {}}
                )
            if arch_name not in settings['paths'].get('Racial', {}).get('archetypes', {}):
                settings['paths']['Racial']['archetypes'][arch_name] = build_racial_archetype(race_data, family_name, subrace_name)

    for level in levels:
        stats = build_config['base_stats']
        char = Character(build_name, stats, settings)
        primary_aff = build_config.get('primary_affinity')
        if primary_aff:
            char.primary_affinity = primary_aff
        char.has_physical = build_config.get('has_physical', False)
        char.has_magical = build_config.get('has_magical', False)
        char.affinities = build_config.get('starting_affinities', {"Generic": 1}).copy()
        char.gear = gear_override if gear_override is not None else build_config.get('gear', {})
        char.is_unarmed = build_config.get('unarmed_fighter', False) or char.gear.get('weapon', '') == 'none'
        char.tull_tier = 0

        if race_pickup and not is_worst and not is_casual and family_name and subrace_name:
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
            char.speed = race_data.get('speed', 30)

        apply_level_progression(char, level, settings)
        if not is_worst and not is_casual:
            apply_paths(char, level, build_config, settings)

        if build_config.get('spend_stat_points') == 'all' and not build_config.get('worst', False):
            priority = build_config.get('stat_priority', ['str','dex','con','wis','int','cha'])
            total_pts = char.stat_points + settings['rules']['starting_points']['stat_points']

            is_casual = build_name.lower().startswith('casual ')
            if is_casual:
                total_pts = total_pts * 2 // 5

            cost_table = settings['rules']['stat_point_cost']

            lower_name = build_name.lower()
            char_type = 'balanced'
            if 'worst' in lower_name:
                char_type = 'balanced'
            elif 'tank' in lower_name:
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

        if char.is_unarmed:
            tull_tier = char.tull_tier
            if char.tull_claw_die:
                if tull_tier >= 9:
                    char.melee_extra_info = "1d10 Slashing + 8 Bludgeoning (Tull Claws)"
                elif tull_tier >= 5:
                    char.melee_extra_info = "1d8 Slashing + 4 Bludgeoning (Tull Claws)"
                else:
                    char.melee_extra_info = "1d6 Slashing + 2 Bludgeoning (Tull Claws)"
            else:
                char.melee_damage += 2
                char.melee_extra_info = "1d4 Bludgeoning (Fist)"

        if not is_casual:
            select_feats(char, level, settings)

        if not is_casual and not build_config.get('worst', False):
            affinity_prereqs = settings.get('rules', {}).get('affinity_prerequisites', {})
            spend_affinity_points(char, build_config.get('primary_affinity'), affinity_prereqs)

        dmg_perturn = calculate_damage(char, settings)
        dmg_5round = calculate_5_round_damage(char, settings['rules'], dmg_perturn, settings)
        dmg_10round = calculate_10_round_damage(char, settings['rules'], dmg_perturn, settings)

        sheet = format_sheet(char, level, settings, dmg_perturn, dmg_5round, dmg_10round, tier_label)
        results.append({'level': level, 'char': char, 'sheet': sheet, 'dmg_perturn': dmg_perturn, 'dmg_5round': dmg_5round, 'dmg_10round': dmg_10round,
                        'race': f"{family_name} {subrace_name}" if race_pickup and family_name else 'none'})
    return results


def main():
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    settings = load_settings(os.path.join(script_dir, "data"))

    base_output_dir = os.path.join(script_dir, "output")
    os.makedirs(base_output_dir, exist_ok=True)

    gen = settings['generation']
    if 'max_level' in gen:
        levels = list(range(1, gen['max_level'] + 1))
    else:
        levels = gen['levels']
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

    overall_path = os.path.join(script_dir, "averages.txt")
    write_overall_averages(gear_tiers, all_tier_results, settings, overall_path)
    print("\nOverall averages across tiers -> " + overall_path)

    summary_path = os.path.join(script_dir, "summary.txt")
    write_summary(all_tier_results, settings, summary_path, settings['builds'])
    print("Balance summary -> " + summary_path)

    print("\nDone!")


if __name__ == "__main__":
    main()
