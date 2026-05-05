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
        self.ac_bonus = 0

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
        self.spells_from_levels = 0
        self.starting_spells = 0

        self.has_physical = False
        self.has_magical = False
        self.affinities = {"Generic": 1}
        self.archetype_levels = {}

        self.stat_points_spent = 0

        self.melee_damage = 0
        self.melee_accuracy = 0
        self.ranged_damage = 0
        self.ranged_accuracy = 0
        self.magic_accuracy = 0
        self.magic_damage = 0

        self.level = 1

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
        return int(dice_avg + wis_mod * self.mana_n)

    def ac(self, dex_table=None):
        base = 10
        dex_mod = self.mod('dex')
        if dex_table and dex_mod > 0:
            capped = min(dex_mod, 18)
            dex_bonus = dex_table.get(str(capped), min(dex_mod, 7))
        else:
            dex_bonus = dex_mod
        return base + dex_bonus + self.ac_bonus


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
                char.affinities['Generic'] = char.affinities.get('Generic', 0) + 1

        if lvl % 3 == 0:
            char.stat_points += e3['stat_points']
            char.affinity_points += e3['affinity_points']
            char.feats += 1
            if char.has_magical and e3.get('if_magical_spell', False):
                char.spells_from_levels += 1

        if lvl % 8 == 0 and 'bap' in e8:
            char.bap += e8['bap']

        if lvl % 10 == 0 and 'ap' in e10:
            char.ap += e10['ap']

        char.prof = prof['base'] + ((lvl - 1) // 3)


def apply_paths(char, target_level, build_config, settings):
    r = settings['rules']
    paths_rules = settings['paths']

    path_list = build_config.get('paths', [])
    if not path_list:
        return

    for pconf in path_list:
        path_name = pconf['path']
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

        share = points_per + (1 if i < remainder else 0)
        points_to_spend = min(share, desired_points)

        arch_rule = paths_rules.get(path_name, {}).get('archetypes', {}).get(arch_name, {})

        achievements = 0
        sorted_keys = sorted(arch_rule.keys(), key=lambda k: float(k))

        for key in sorted_keys:
            if achievements >= points_to_spend:
                break
            apply_effects(char, arch_rule[key])
            achievements += 1

        char.archetype_levels[(path_name, arch_name)] = achievements


def apply_effects(char, effects):
    if not effects:
        return
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


def spend_stat_points(char, priority, points, cost_table, char_type='balanced'):
    """Spend stat points to raise stats with realistic spread.
    char_type can be: 'tank', 'marksman', 'caster', 'jack', 'balanced'"""
    import random
    
    points_remaining = points
    cost_table_list = sorted(cost_table.items(), key=lambda x: int(x[0].split('-')[0]))
    
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
    
    for stat in priority:
        target = stat_targets.get(stat, 8)
        current = getattr(char, stat)
        
        while points_remaining > 0 and current < target:
            cost = cost_for_stat(current, cost_table)
            if cost > points_remaining:
                if points_remaining >= 2 and current >= 18:
                    setattr(char, stat, current + 1)
                    points_remaining -= cost
                    char.stat_points_spent += cost
                    current += 1
                elif points_remaining >= 1 and current >= 12 and priority.index(stat) <= 1:
                    setattr(char, stat, current + 1)
                    points_remaining -= cost
                    char.stat_points_spent += cost
                    current += 1
                break
            setattr(char, stat, current + 1)
            points_remaining -= cost
            char.stat_points_spent += cost
            current += 1
    
    return points_remaining


def spend_affinity_points(char, settings):
    affp = char.affinity_points
    if affp <= 0:
        return
    
    pref_order = ['Fire', 'Earth', 'Water', 'Air', 'Radiant', 'Necrotic', 'Psychic']
    
    for aff in pref_order:
        while affp > 0:
            char.affinities[aff] = char.affinities.get(aff, 0) + 1
            affp -= 1
    
    while affp > 0:
        char.affinities['Generic'] = char.affinities.get('Generic', 0) + 1
        affp -= 1
    
    char.affinity_points = 0


def calculate_damage(char):
    result = {'melee': 0, 'ranged': 0, 'magic': 0, 'mana_cost': 0, 'magic_dmg': 0}
    
    hit_chance_base = 0.75
    
    if char.has_physical:
        if char.melee_damage > 0:
            dmg = 4 + char.melee_damage + char.mod('str')
            result['melee'] = int(dmg * hit_chance_base)
        
        if char.ranged_damage > 0:
            dmg = 4 + char.ranged_damage + char.mod('dex')
            result['ranged'] = int(dmg * hit_chance_base)
    
    if char.has_magical:
        gen_aff = char.affinities.get('Generic', 0)
        best_aff = 0
        for k, v in char.affinities.items():
            if k != 'Generic' and v >= 3 and v > best_aff:
                best_aff = v
        
        if best_aff >= 3:
            dmg = 1 + best_aff + gen_aff + char.magic_damage
            result['magic'] = int((1 + best_aff) * hit_chance_base)
            result['magic_dmg'] = int((1 + best_aff) * hit_chance_base)
            result['mana_cost'] = 2
    
    return result


def calculate_10_round_damage(char, r, dmg_per_turn):
    total = dmg_per_turn['melee'] + dmg_per_turn['ranged']
    
    if char.has_magical and dmg_per_turn['mana_cost'] > 0:
        mana = char.mana_max(r)
        mana_left = mana
        for _ in range(10):
            if mana_left >= dmg_per_turn['mana_cost']:
                total += dmg_per_turn['magic']
                mana_left -= dmg_per_turn['mana_cost']
            else:
                break
    
    return total


def format_sheet(char, level, settings, dmg_perturn, dmg_10round):
    r = settings['rules']
    lines = []
    sep = "=" * 60
    lines.append(sep)
    lines.append("  " + char.name + " - Level " + str(level))
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

    lines.append("  COMBAT:")
    lines.append("    AC: " + str(char.ac(r['ac']['dex_bonus_table'])))
    lines.append("    Initiative: " + format_mod(char.mod('dex')))
    lines.append("    Speed: 30 ft")
    lines.append("    AP: " + str(char.ap) + "  BAP: " + str(char.bap) + "  RP: " + str(char.rp))
    lines.append("    Proficiency: +" + str(char.prof))
    lines.append("")

    lines.append("  HEALTH POOLS:")
    lines.append("    Vitality: " + str(char.vit_max(r)) + " = " + vd + " (" + str(int(die_avg[char.vit_die])) + " x " + str(char.vit_n) + ") + " + str(char.flat_vit) + "(flat) + " + str(con_mod) + " x " + str(char.vit_n) + "(Con)")
    lines.append("    Health:  " + str(char.hp_max(r)) + " = " + hd + " (" + str(int(die_avg[char.hp_die])) + " x " + str(char.hp_n) + ") + " + str(char.flat_hp) + "(flat)")
    lines.append("    Mana:   " + str(char.mana_max(r)) + " = " + md + " (" + str(int(die_avg[char.mana_die])) + " x " + str(char.mana_n) + ") + " + str(wis_mod) + " x " + str(char.mana_n) + "(Wis)")
    lines.append("")

    lines.append("  DAMAGE:")
    lines.append("    Melee Dmg/Turn: " + str(dmg_perturn['melee']))
    lines.append("    Ranged Dmg/Turn: " + str(dmg_perturn['ranged']))
    lines.append("    Magic Dmg/Turn: " + str(dmg_perturn['magic']) + " (x" + str(dmg_perturn['mana_cost']) + " mana)")
    lines.append("    Total Dmg/10R: " + str(dmg_10round))
    lines.append("")

    lines.append("  RESOURCES:")
    lines.append("    Skill Points:  " + str(char.skill_points))
    lines.append("    Stat Points:   " + str(char.stat_points))
    lines.append("    Affinity Pts:  " + str(char.affinity_points))
    lines.append("    Stat Spent:    " + str(char.stat_points_spent))
    lines.append("")

    total_spells = char.starting_spells + char.spells_from_levels
    lines.append("  FEATS & SPELLS:")
    lines.append("    Feats:  " + str(char.feats))
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

    return "\n".join(lines)


def generate_build(build_name, build_config, settings, levels):
    results = []
    for level in levels:
        stats = build_config['base_stats']
        char = Character(build_name, stats, settings)
        char.has_physical = build_config.get('has_physical', False)
        char.has_magical = build_config.get('has_magical', False)
        char.affinities = build_config.get('starting_affinities', {"Generic": 1}).copy()

        apply_level_progression(char, level, settings)

        if build_config.get('spend_stat_points') == 'all':
            priority = build_config.get('stat_priority', ['str','dex','con','wis','int','cha'])
            total_pts = char.stat_points + settings['rules']['starting_points']['stat_points']
            cost_table = settings['rules']['stat_point_cost']
            
            char_type = 'balanced'
            lower_name = build_name.lower()
            if 'tank' in lower_name:
                char_type = 'tank'
            elif 'marksman' in lower_name:
                char_type = 'marksman'
            elif 'pyromancer' in lower_name or 'priest' in lower_name or 'necromancer' in lower_name:
                char_type = 'caster'
            elif 'jack' in lower_name:
                char_type = 'jack'
            
            spend_stat_points(char, priority, total_pts, cost_table, char_type)
            char.stat_points = 0

        apply_paths(char, level, build_config, settings)

        spend_affinity_points(char, settings)

        dmg_perturn = calculate_damage(char)
        dmg_10round = calculate_10_round_damage(char, settings['rules'], dmg_perturn)

        sheet = format_sheet(char, level, settings, dmg_perturn, dmg_10round)
        results.append({'level': level, 'char': char, 'sheet': sheet, 'dmg_perturn': dmg_perturn, 'dmg_10round': dmg_10round})
    return results


def write_build_file(build_name, results, output_dir):
    safe = build_name.replace(' ', '_').replace('/', '_')
    path = os.path.join(output_dir, safe + ".txt")
    with open(path, 'w') as f:
        f.write("EYUM TTRPG - " + build_name.upper() + "\n")
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

            for build_name, results in all_results.items():
                for res in results:
                    if res['level'] == level:
                        c = res['char']
                        d = res['dmg_perturn']
                        vitals.append(c.vit_max(r))
                        healths.append(c.hp_max(r))
                        manas.append(c.mana_max(r))
                        acs.append(c.ac(r['ac']['dex_bonus_table']))
                        feats.append(c.feats)
                        spells.append(c.starting_spells + c.spells_from_levels)
                        dmg_per.append(d['melee'] + d['ranged'] + d['magic'])
                        dmg_10r.append(res['dmg_10round'])
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
            f.write("\n")


def main():
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    settings_path = os.path.join(script_dir, "settings.json")
    settings = load_json(settings_path)

    output_dir = os.path.join(script_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    avg_path = os.path.join(script_dir, "average.txt")

    levels = settings['generation']['levels']
    all_results = {}

    for build_name, build_config in settings['builds'].items():
        if not build_config.get('generate', True):
            continue;

        print("Generating: " + build_name + " (levels: " + str(levels) + ")")
        results = generate_build(build_name, build_config, settings, levels)
        all_results[build_name] = results;

        if settings['generation'].get('separate_files', True):
            path = write_build_file(build_name, results, output_dir)
            print("  -> " + path)

    if settings['generation'].get('generate_average', True):
        write_average(all_results, settings, avg_path)
        print("Average stats -> " + avg_path)

    print("\nDone!")


if __name__ == "__main__":
    main()