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
from lib.gear import resolve_gear, select_gear, get_equipment
from lib.races import select_best_race, build_racial_archetype, build_race_data
from lib.output import format_sheet, write_build_file, write_average, write_overall_averages, write_summary

DIE_AVERAGES_PRELOAD = {}


def score_effect_for_build(effect_key, effect_val, build_config, arch_name=''):
    score = 0
    stat_priority = build_config.get('stat_priority', [])
    stat_weights = [10, 4, 2, 1, 0.5, 0.25]
    is_physical = build_config.get('has_physical', False)
    is_magical = build_config.get('has_magical', False)
    primary_aff = build_config.get('primary_affinity')
    weapon = build_config.get('gear', {}).get('weapon', '')
    is_ranged = 'bow' in weapon.lower() or 'crossbow' in weapon.lower()

    if effect_key == 'stat':
        for stat, bonus in effect_val.items():
            if stat in ('str', 'dex', 'con', 'wis', 'int', 'cha'):
                for i, s in enumerate(stat_priority):
                    if s == stat and i < len(stat_weights):
                        score += bonus * stat_weights[i]
    elif effect_key == 'melee_damage':
        if is_physical and not is_ranged:
            score += effect_val * 15
    elif effect_key == 'ranged_damage':
        if is_physical and (is_ranged or not weapon):
            score += effect_val * 15
    elif effect_key == 'magic_damage':
        if is_magical:
            score += effect_val * 15
    elif effect_key == 'melee_accuracy':
        if is_physical and not is_ranged:
            score += effect_val * 10
    elif effect_key == 'ranged_accuracy':
        if is_physical and (is_ranged or not weapon):
            score += effect_val * 10
    elif effect_key == 'magic_accuracy':
        if is_magical:
            score += effect_val * 10
    elif effect_key == 'weapon_group_accuracy':
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
        for aff, val in effect_val.items():
            if is_magical:
                score += val * 3
            if aff == primary_aff:
                score += val * 20
    elif effect_key == 'skill_points':
        score += effect_val * 1
    elif effect_key == 'stat_points':
        score += effect_val * 6
    elif effect_key == 'extra_attack_bap':
        if is_physical:
            score += 20
    elif effect_key == 'initiative':
        score += effect_val * 3
    elif effect_key == 'speed':
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
    elif effect_key == 'hallowed_affinity':
        if is_magical:
            score += effect_val * 3
    elif effect_key == 'eldritch_affinity':
        if is_magical:
            score += effect_val * 3
    elif effect_key in ('fire_damage_bonus', 'earth_damage_bonus', 'water_damage_bonus',
                        'air_damage_bonus', 'radiant_damage_bonus', 'necrotic_damage_bonus',
                        'psychic_damage_bonus'):
        if is_magical:
            score += 6
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
    elif effect_key == 'spell_damage_mult':
        if is_magical:
            score += effect_val * 20
    elif effect_key == 'spell_mana_mult':
        if is_magical:
            score += effect_val * -8
    elif effect_key == 'vit_die_type':
        die_order = ['1d4','1d6','1d8','1d10','1d12','1d20']
        new_idx = die_order.index(effect_val) if effect_val in die_order else 3
        old_idx = 3
        score += (new_idx - old_idx) * 2
    elif effect_key == 'mana_die_type':
        die_order = ['1d4','1d6','1d8','1d10','1d12','1d20']
        new_idx = die_order.index(effect_val) if effect_val in die_order else 2
        old_idx = 2
        score += (new_idx - old_idx) * 2
    elif effect_key in ('true_sight_range', 'darkvision_range', 'fly_speed',
                        'initiative_advantage', 'first_round_damage', 'ap_first_round',
                        'first_round_advantage', 'magic_blast', 'ranged_expertise',
                        'pact_access_tier', 'tier_racial', 'karma', 'anti_deity_damage',
                        'antideity_damage', 'monster_damage', 'humanoid_damage'):
        score += 1

    return score


def _get_affinity_arch_map(settings):
    """Derive affinity->archetype mapping from rules data, not hardcoded."""
    affinity_prereqs = settings.get('rules', {}).get('affinity_prerequisites', {})
    base_elements = {
        'Fire': 'Pyromancer', 'Earth': 'Geomancer', 'Water': 'Tidemaster', 'Air': 'Windwalker',
        'Radiant': 'Priest', 'Necrotic': 'Necromancer', 'Psychic': 'Psychic',
    }
    result = dict(base_elements)
    # Walk prerequisite tree: if Lightning needs Fire+Air, map Lightning to whichever base
    # element has the most archetype affinity overlap
    downstream = {}
    for aff, prereq in affinity_prereqs.items():
        if aff in result:
            continue
        needs_all = prereq.get('needs_all', [])
        needs = prereq.get('needs', {})
        all_affs = []
        if needs_all:
            for tier in needs_all:
                all_affs.extend(tier.get('affinities', []))
        else:
            all_affs = needs.get('all_of', []) or needs.get('any_of', [])
        # Find base elements among prerequisites
        for base_aff in all_affs:
            if base_aff in result:
                result[aff] = result[base_aff]
                break
        if aff not in result and all_affs:
            result[aff] = 'Magician'
    # Override specific known mappings
    overrides = {
        'Generic': 'Magician', 'Force': 'Magician', 'Eldritch': 'Magician',
    }
    result.update(overrides)
    return result


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

    primary_aff = build_config.get('primary_affinity')
    if primary_aff:
        arch_aff_map = _ARCH_AFF_MAP_CACHE
        mapped = arch_aff_map.get(arch_name)
        if mapped:
            if mapped == primary_aff:
                total += 30
            else:
                total -= 20

    return total


_ARCH_AFF_MAP_CACHE = {}


def select_archetypes(build_config, settings, target_level):
    global _ARCH_AFF_MAP_CACHE
    if not _ARCH_AFF_MAP_CACHE:
        _ARCH_AFF_MAP_CACHE = _get_affinity_arch_map(settings)
    
    available_stp = target_level
    path_rules = settings['paths']
    preferred = build_config.get('preferred_paths', list(path_rules.keys()))
    affinity_prereqs = settings.get('rules', {}).get('affinity_prerequisites', {})
    primary_aff = build_config.get('primary_affinity')
    is_magical = build_config.get('has_magical', False)

    primary_arch = _ARCH_AFF_MAP_CACHE.get(primary_aff) if primary_aff else None

    needed_archs = set()
    if primary_arch:
        needed_archs.add(primary_arch)
    if is_magical:
        needed_archs.add('Magician')

    # Add prerequisite affinity archetypes for complex affinities
    if primary_aff and primary_aff in affinity_prereqs:
        def _collect_prereq_affs(aff, visited=None):
            if visited is None: visited = set()
            if aff in visited: return set()
            visited.add(aff)
            result = set()
            if aff not in affinity_prereqs:
                return result
            pr = affinity_prereqs[aff]
            needs_all = pr.get('needs_all', [])
            if needs_all:
                for tier in needs_all:
                    for a in tier.get('affinities', []):
                        result.add(a)
                        result |= _collect_prereq_affs(a, visited)
            else:
                needs = pr.get('needs', {})
                all_of = needs.get('all_of', [])
                any_of = needs.get('any_of', [])
                if all_of:
                    for a in all_of:
                        result.add(a)
                        result |= _collect_prereq_affs(a, visited)
                elif any_of:
                    result.add(any_of[0])
            return result

        all_prereqs = _collect_prereq_affs(primary_aff)
        for aff in all_prereqs:
            arch = _ARCH_AFF_MAP_CACHE.get(aff)
            if arch:
                needed_archs.add(arch)

    arch_scores = []
    for path_name in preferred:
        path_data = path_rules.get(path_name, {})
        archs = path_data.get('archetypes', {})
        for arch_name, arch_data in archs.items():
            score = score_archetype_for_build(arch_name, arch_data, build_config)
            base_tiers = sum(1 for k in arch_data if float(k) == int(float(k)) and not arch_data[k].get('repeatable', False))
            if arch_name in needed_archs:
                score += 2000
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
    family_name = None
    subrace_name = None
    if not is_worst and 'preferred_paths' in build_config and ('paths' not in build_config or not build_config.get('paths')):
        max_level = max(levels)
        dynamic_paths = select_archetypes(build_config, settings, max(levels))
        build_config['paths'] = dynamic_paths

    # Normalize paths: accept both [{"path":..., "archetype":...}] list and {path: [archs]} dict
    raw_paths = build_config.get('paths', {})
    if isinstance(raw_paths, dict):
        # Convert dict format to list format for internal use
        path_list = []
        for pname, archs in raw_paths.items():
            for aname in archs:
                path_list.append({"path": pname, "archetype": aname, "level": 999, "repeatables": {}})
        build_config['paths'] = path_list
    else:
        path_list = raw_paths

    race_pickup = build_config.get('race', None)
    if race_pickup and not is_worst:
        build_config['_build_name'] = build_name
        family_name, subrace_name = select_best_race(build_config, all_races)
        if family_name and subrace_name:
            race_data = all_races[family_name]['subraces'][subrace_name]
            arch_name = f"{family_name} {subrace_name}"
            has_racial_path = any(p.get('path') == 'Racial' for p in path_list)
            if not has_racial_path:
                build_config.setdefault('paths', []).append(
                    {"path": "Racial", "archetype": arch_name, "level": 10, "repeatables": {}}
                )
            if arch_name not in settings['paths'].get('Racial', {}).get('archetypes', {}):
                settings['paths']['Racial']['archetypes'][arch_name] = build_racial_archetype(race_data, family_name, subrace_name)

    prev_snapshot = None
    build_config['_prev_arch_levels'] = {}  # Reset per-build, not shared across builds
    for level in levels:
        stats = build_config['base_stats']
        char = Character(build_name, stats, settings)
        primary_aff = build_config.get('primary_affinity')
        if primary_aff:
            char.primary_affinity = primary_aff
        char.has_physical = build_config.get('has_physical', False)
        char.has_magical = build_config.get('has_magical', False)
        char.has_utility = any(p.get('path') == 'Utility' for p in path_list)
        char.affinities = build_config.get('starting_affinities', {"Generic": 1}).copy()
        char.gear = gear_override if gear_override is not None else build_config.get('gear', {})
        weapon_name = char.gear.get('weapon', '')
        if weapon_name and weapon_name not in ('none', None):
            weapon_info = settings.get('weapons', {}).get(weapon_name, {})
            char._weapon_magic_bonus = weapon_info.get('magic_bonus', 0)
        char.is_unarmed = build_config.get('unarmed_fighter', False) or char.gear.get('weapon', '') == 'none'
        char.tull_tier = 0

        if race_pickup and not is_worst and family_name and subrace_name:
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

        if not is_worst:
            apply_paths(char, level, build_config, settings)
        apply_level_progression(char, level, settings)

        if build_config.get('spend_stat_points') == 'all' and not build_config.get('worst', False):
            priority = list(build_config.get('stat_priority', ['str','dex','con','wis','int','cha']))
            total_pts = char.stat_points + settings['rules']['starting_points']['stat_points']

            cost_table = settings['rules']['stat_point_cost']

            # Determine character type from build config, not name
            char_type = build_config.get('char_type', 'balanced')
            if char_type == 'auto':
                pri = build_config.get('stat_priority', [])
                if build_config.get('has_magical') and not build_config.get('has_physical'):
                    char_type = 'caster'
                elif build_config.get('has_physical') and pri and pri[0] == 'con':
                    char_type = 'tank'
                elif build_config.get('has_physical') and pri and pri[0] == 'dex':
                    char_type = 'marksman'
                else:
                    char_type = 'balanced'

            # Check primary affinity spell prereqs for stat requirements
            primary_aff = build_config.get('primary_affinity')
            if primary_aff and primary_aff != 'Generic':
                spells_data = settings.get('spells', {})
                max_stat_needed = {'int': 0, 'con': 0, 'str': 0, 'dex': 0, 'wis': 0, 'cha': 0}
                for s in spells_data.get(primary_aff, []):
                    for stat in ['int', 'con', 'str', 'dex', 'wis', 'cha']:
                        key = f'{stat}_required'
                        val = s.get(key, 0)
                        if val and val > max_stat_needed[stat]:
                            max_stat_needed[stat] = val
                # Push high-requirement stats to front of priority
                stat_names = ['str', 'dex', 'con', 'wis', 'int', 'cha']
                stats_by_req = sorted(stat_names, key=lambda s: max_stat_needed[s], reverse=True)
                for s in reversed(stats_by_req):
                    if max_stat_needed[s] > 0:
                        if s in priority:
                            priority.remove(s)
                        priority.insert(0, s)

            spend_stat_points(char, priority, total_pts, cost_table, char_type, settings, primary_aff)
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

        select_feats(char, level, settings)

        if not build_config.get('worst', False):
            affinity_prereqs = settings.get('rules', {}).get('affinity_prerequisites', {})
            spend_affinity_points(char, build_config.get('primary_affinity'), affinity_prereqs)

        dmg_perturn = calculate_damage(char, settings)
        dmg_5round = calculate_5_round_damage(char, settings['rules'], dmg_perturn, settings)
        dmg_10round = calculate_10_round_damage(char, settings['rules'], dmg_perturn, settings)

        # Compute changes from previous level
        changes = _compute_changes(prev_snapshot, char, level)

        # Capture snapshot for next level comparison
        prev_snapshot = _capture_snapshot(char)

        sheet = format_sheet(char, level, settings, dmg_perturn, dmg_5round, dmg_10round, tier_label, changes)
        results.append({'level': level, 'char': char, 'sheet': sheet, 'dmg_perturn': dmg_perturn, 'dmg_5round': dmg_5round, 'dmg_10round': dmg_10round,
                        'race': f"{family_name} {subrace_name}" if race_pickup and family_name else 'none'})
    return results


def _capture_snapshot(char):
    """Capture key character state for level-to-level diffing."""
    return {
        'level': char.level,
        'str': char.str, 'dex': char.dex, 'con': char.con,
        'wis': char.wis, 'int': char.int, 'cha': char.cha,
        'ap': char.ap, 'bap': char.bap, 'rp': char.rp,
        'prof': char.prof,
        'speed': char.speed,
        'vit_n': char.vit_n, 'hp_n': char.hp_n, 'mana_n': char.mana_n,
        'vit_die': char.vit_die, 'hp_die': char.hp_die, 'mana_die': char.mana_die,
        'feat_count': char.feats,
        'feats_taken': list(char.feats_taken),
        'spells': char.starting_spells + char.spells_from_levels,
        'melee_dmg': char.melee_damage, 'ranged_dmg': char.ranged_damage,
        'melee_acc': char.melee_accuracy, 'ranged_acc': char.ranged_accuracy,
        'magic_acc': char.magic_accuracy, 'magic_dmg': char.magic_damage,
        'affinities': dict(char.affinities),
        'archetype_levels': dict(char.archetype_levels),
        'stat_points_spent': char.stat_points_spent,
        'spell_dmg_mult': char.spell_damage_mult,
        'ac_bonus': char.ac_bonus,
        'flat_vit': char.flat_vit, 'flat_hp': char.flat_hp, 'flat_mana': char.flat_mana,
        'archetype_whole_levels': dict(char.archetype_whole_levels),
    }


STAT_LABELS = {'str': 'STR', 'dex': 'DEX', 'con': 'CON', 'wis': 'WIS', 'int': 'INT', 'cha': 'CHA'}


def _compute_changes(prev, char, level):
    """Build a human-readable summary of what changed since the previous level."""
    if prev is None:
        return None
    parts = []

    # Level-up basics
    parts.append(f"Level {prev['level']}→{level}")

    # Stats that changed
    stat_changes = []
    for s in ['str', 'dex', 'con', 'wis', 'int', 'cha']:
        old = prev[s]
        new = getattr(char, s)
        if old != new:
            stat_changes.append(f"{STAT_LABELS[s]} {old}→{new}")
    if stat_changes:
        parts.append("Stats: " + ", ".join(stat_changes))

    # Combat points
    ap_changed = prev['ap'] != char.ap
    bap_changed = prev['bap'] != char.bap
    rp_changed = prev['rp'] != char.rp
    prof_changed = prev['prof'] != char.prof
    combat_changes = []
    if ap_changed: combat_changes.append(f"AP {prev['ap']}→{char.ap}")
    if bap_changed: combat_changes.append(f"BAp {prev['bap']}→{char.bap}")
    if rp_changed: combat_changes.append(f"Rp {prev['rp']}→{char.rp}")
    if prof_changed: combat_changes.append(f"Prof +{prev['prof']}→+{char.prof}")
    if combat_changes:
        parts.append("Combat: " + ", ".join(combat_changes))

    # HP/Vit/Mana dice
    pool_changes = []
    if prev['vit_n'] != char.vit_n: pool_changes.append(f"+1 Vit die (now {char.vit_n}d{char.vit_die[-1]})")
    if prev['hp_n'] != char.hp_n: pool_changes.append(f"+1 HP die (now {char.hp_n}d{char.hp_die[-1]})")
    if prev['mana_n'] != char.mana_n: pool_changes.append(f"+1 Mana die (now {char.mana_n}d{char.mana_die[-1]})")
    if prev['vit_die'] != char.vit_die: pool_changes.append(f"Vit die {prev['vit_die']}→{char.vit_die}")
    if prev['hp_die'] != char.hp_die: pool_changes.append(f"HP die {prev['hp_die']}→{char.hp_die}")
    if prev['mana_die'] != char.mana_die: pool_changes.append(f"Mana die {prev['mana_die']}→{char.mana_die}")
    if pool_changes:
        parts.append("Pools: " + "; ".join(pool_changes))

    # New feats
    new_feats = [f for f in char.feats_taken if f not in prev['feats_taken']]
    if new_feats:
        parts.append("Feats: gained " + ", ".join(new_feats))

    # Affinity changes
    aff_changes = []
    for aff in set(list(prev['affinities'].keys()) + list(char.affinities.keys())):
        old = prev['affinities'].get(aff, 0)
        new = char.affinities.get(aff, 0)
        if old != new:
            aff_changes.append(f"{aff} {old}→{new}")
    if aff_changes and len(aff_changes) <= 6:
        parts.append("Affinities: " + ", ".join(aff_changes))
    elif aff_changes:
        parts.append(f"Affinities: {len(aff_changes)} changed")

    # Archetype level changes
    arch_changes = []
    for (pn, an), lv in char.archetype_levels.items():
        old_lv = prev['archetype_levels'].get((pn, an), 0)
        if lv != old_lv:
            arch_changes.append(f"+{lv - old_lv} STP in {pn}→{an} (now Lvl {lv})")
    if arch_changes:
        parts.append("Skill Tree: " + "; ".join(arch_changes))

    # Damage/accuracy changes
    dmg_changes = []
    if prev['melee_dmg'] != char.melee_damage: dmg_changes.append(f"Melee Dmg {prev['melee_dmg']}→{char.melee_damage}")
    if prev['ranged_dmg'] != char.ranged_damage: dmg_changes.append(f"Ranged Dmg {prev['ranged_dmg']}→{char.ranged_damage}")
    if prev['magic_dmg'] != char.magic_damage: dmg_changes.append(f"Magic Dmg {prev['magic_dmg']}→{char.magic_damage}")
    if prev['melee_acc'] != char.melee_accuracy: dmg_changes.append(f"Melee Acc {prev['melee_acc']}→{char.melee_accuracy}")
    if prev['ranged_acc'] != char.ranged_accuracy: dmg_changes.append(f"Ranged Acc {prev['ranged_acc']}→{char.ranged_accuracy}")
    if prev['magic_acc'] != char.magic_accuracy: dmg_changes.append(f"Magic Acc {prev['magic_acc']}→{char.magic_accuracy}")
    if dmg_changes and len(dmg_changes) <= 4:
        parts.append("Damage: " + ", ".join(dmg_changes))

    # Spell damage multiplier change
    if prev.get('spell_dmg_mult', 1) != char.spell_damage_mult:
        parts.append(f"Spell multiplier {prev.get('spell_dmg_mult',1)}x→{char.spell_damage_mult}x")

    return " | ".join(parts) if parts else None


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
    gear_tiers = settings.get('gear_tiers', [{"name": "bad_gear", "label": "Bad Gear", "gold_per_level": 1}])

    # --- Test mode filtering ---
    test_mode = gen.get('test_mode', {})
    if test_mode.get('enabled', False):
        build_filter = test_mode.get('build_filter', [])
        level_range = test_mode.get('level_range', None)
        if build_filter:
            print(f"[TEST MODE] Build filter: {build_filter}")
        if level_range:
            levels = [l for l in levels if level_range[0] <= l <= level_range[1]]
            print(f"[TEST MODE] Level range: {level_range} -> {len(levels)} levels")
        print(f"[TEST MODE] Active — only running filtered builds/levels")
    # --- End test mode ---

    # Load equipment data for dynamic gear selection
    eq_data = get_equipment()
    if eq_data:
        print(f"Equipment data loaded: {len(eq_data.get('weapons',[]))} weapons available")

    all_tier_results = []

    for tier in gear_tiers:
        tier_name = tier['name']
        tier_label = tier['label']
        tier_dir = os.path.join(base_output_dir, tier_name)
        os.makedirs(tier_dir, exist_ok=True)

        all_results = {}
        max_level = max(levels)
        print(f"\n=== Gear Tier: {tier_label} ===")

        for build_name, build_config in settings['builds'].items():
            if not build_config.get('generate', True):
                continue
            # Test mode: skip builds not in the filter (if filter is non-empty)
            if test_mode.get('enabled', False) and build_filter and build_name not in build_filter:
                continue

            print(f"  Generating: {build_name} (levels: {min(levels)}-{max_level})")
            # Select best gear the character can afford at max level
            gear_override = select_gear(build_config, tier_name, max_level) if tier_name != 'no_gear' else {'weapon': None, 'armor': 'none'}
            if gear_override:
                print(f"    Gear: {gear_override.get('weapon','none')} | {gear_override.get('armor','none')}")
            sys.stdout.flush()
            results = generate_build(build_name, build_config, settings, levels, gear_override, tier_label)
            all_results[build_name] = results

            if settings['generation'].get('separate_files', True):
                path = write_build_file(build_name, results, tier_dir, tier_label)
                print(f"    -> {path}")

        if settings['generation'].get('generate_average', True):
            avg_path = os.path.join(tier_dir, "average.txt")
            write_average(all_results, settings, avg_path)
            print(f"    Average stats -> {avg_path}")

        all_tier_results.append((tier_name, all_results))

    overall_path = os.path.join(script_dir, "averages.txt")
    write_overall_averages(gear_tiers, all_tier_results, settings, overall_path)
    print(f"\nOverall averages across tiers -> {overall_path}")

    summary_path = os.path.join(script_dir, "summary.txt")
    write_summary(all_tier_results, settings, summary_path, settings['builds'])
    print(f"Balance summary -> {summary_path}")

    # Append weapon balance analysis
    if eq_data:
        _append_weapon_balance(eq_data, summary_path)

    print("\nDone!")


def _append_weapon_balance(eq_data, summary_path):
    """Append weapon balance statistics to the summary file."""
    weapons = eq_data.get('weapons', [])
    if not weapons: return

    lines = ["\n" + "="*70, "WEAPON BALANCE ANALYSIS (from Equipment Analyzer)", "="*70]

    dprs = [w.get('dpr_vs_ac16', 0) for w in weapons if w.get('dpr_vs_ac16', 0) > 0]
    if dprs:
        dprs.sort()
        lines.append(f"\nDPR Distribution (vs AC 16, {len(dprs)} weapons):")
        lines.append(f"  Min: {dprs[0]:.1f}  Q1: {dprs[len(dprs)//4]:.1f}  Median: {dprs[len(dprs)//2]:.1f}  Q3: {dprs[3*len(dprs)//4]:.1f}  Max: {dprs[-1]:.1f}")

    by_dpr = sorted(weapons, key=lambda x: x.get('dpr_vs_ac16', 0), reverse=True)
    lines.append("\nTop 10 Weapons by DPR (vs AC 16):")
    for i, w in enumerate(by_dpr[:10]):
        lines.append(f"  {i+1}. {w['name']:<50} DPR:{w.get('dpr_vs_ac16',0):.1f}  DMG:{w['total_dmg']}  Acc:{w['total_acc']}  {w.get('dpr_tier','?')}")

    mat_dpr = {}
    for w in weapons:
        mat_dpr[w['material']] = mat_dpr.get(w['material'], 0) + w.get('dpr_vs_ac16', 0)
    mat_rank = sorted(mat_dpr.items(), key=lambda x: x[1], reverse=True)
    lines.append("\nMaterial Performance (sum DPR vs AC 16):")
    for i, (mat, dpr) in enumerate(mat_rank[:10]):
        lines.append(f"  {i+1}. {mat:<25} Sum DPR: {dpr:.0f}")

    cat_dpr = {}
    for w in weapons:
        for c in w.get('category', []):
            cat_dpr[c] = cat_dpr.get(c, 0) + w.get('dpr_vs_ac16', 0)
    lines.append("\nCategory Performance (sum DPR vs AC 16):")
    for c, dpr in sorted(cat_dpr.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  {c:<20} Sum DPR: {dpr:.0f}")

    tier_counts = {}
    for w in weapons:
        t = w.get('dpr_tier', 'unknown')
        tier_counts[t] = tier_counts.get(t, 0) + 1
    lines.append(f"\nDPR Tier Distribution: {tier_counts}")

    with open(summary_path, 'a') as f:
        f.write('\n'.join(lines) + '\n')
    print("Weapon balance appended to summary")


if __name__ == "__main__":
    main()
