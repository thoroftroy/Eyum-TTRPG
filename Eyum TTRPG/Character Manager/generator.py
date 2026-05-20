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
from lib.combat import calculate_damage, calculate_10_round_damage
from lib.gear import resolve_gear
from lib.races import select_best_race, build_racial_archetype, build_race_data
from lib.output import format_sheet, write_build_file, write_average, write_overall_averages, write_summary


def generate_build(build_name, build_config, settings, levels, gear_override=None, tier_label=None):
    results = []

    all_races = build_race_data(settings)

    race_pickup = build_config.get('race', None)
    if race_pickup:
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
            char.speed = race_data.get('speed', 30)

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
            if arch == 'Jack':
                if lvl >= 3:
                    char.affinity_points += max(0, level - 1)

        if char.is_unarmed:
            tull_tier = char.tull_tier
            if tull_tier >= 9:
                char.melee_damage += 16
                char.melee_extra_info = "1d20 Slashing + 1d12 Bludgeoning (Tull Claws)"
            elif tull_tier >= 5:
                char.melee_damage += 10
                char.melee_extra_info = "1d10 Slashing + 1d8 Bludgeoning (Tull Claws)"
            elif tull_tier >= 1:
                char.melee_damage += 5
                char.melee_extra_info = "1d6 Slashing + 1d4 Bludgeoning (Tull Claws)"
            else:
                char.melee_damage += 2
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


def main():
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    settings = load_settings(os.path.join(script_dir, "data"))

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

    overall_path = os.path.join(script_dir, "averages.txt")
    write_overall_averages(gear_tiers, all_tier_results, settings, overall_path)
    print("\nOverall averages across tiers -> " + overall_path)

    summary_path = os.path.join(script_dir, "summary.txt")
    write_summary(all_tier_results, settings, summary_path, settings['builds'])
    print("Balance summary -> " + summary_path)

    print("\nDone!")


if __name__ == "__main__":
    main()
