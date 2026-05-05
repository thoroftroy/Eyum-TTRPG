#!/usr/bin/env python3
"""
Eyum TTRPG Character Sheet Generator
Reads settings.json for all rules and build configs.
Generates separate .txt files per build, plus average.txt.
Supports any levels specified in settings.json.
"""

import json
import os
import sys


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


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

    def mod(self, stat):
        return (getattr(self, stat) - 10) // 2

    def vit_max(self, r):
        return int(self.vit_n * r['die_averages'][self.vit_die]
                   + self.mod('con') * self.vit_n
                   + self.flat_vit)

    def hp_max(self, r):
        return int(self.hp_n * r['die_averages'][self.hp_die]
                   + self.flat_hp)

    def mana_max(self, r):
        return int(self.mana_n * r['die_averages'][self.mana_die]
                   + self.mod('wis') * self.mana_n)

    def ac(self, dex_table=None):
        base = 10
        dex_mod = self.mod('dex')
        if dex_table and dex_mod > 0:
            capped = min(dex_mod, 18)
            dex_bonus = dex_table.get(str(capped), min(dex_mod, 7))
        else:
            dex_bonus = dex_mod
        return base + dex_bonus + self.ac_bonus


def cost_for_stat(current_val, cost_table):
    items = sorted(cost_table.items(), key=lambda x: int(x[0].split('-')[0]))
    for range_str, cost in items:
        parts = range_str.split('-')
        low = int(parts[0])
        high = int(parts[1]) if len(parts) > 1 else low
        if low <= current_val <= high:
            return cost
    tier = (current_val - 1) // 10
    return tier + 1


def spend_stat_points(char, priority, points, cost_table):
    for stat in priority:
        while points > 0:
            current = getattr(char, stat)
            cost = cost_for_stat(current, cost_table)
            if cost > points:
                break
            setattr(char, stat, current + 1)
            points -= cost
            char.stat_points_spent += cost
    return points


def skill_tree_at_level(level):
    return 1 + (level // 2)


def apply_level_progression(char, target_level, settings):
    r = settings['rules']
    per = r['per_level']
    e2 = r['every_2_levels']
    e3 = r['every_3_levels']
    e8 = r.get('every_8_levels', {})
    e10 = r.get('every_10_levels', {})
    prof = r['proficiency']

    for lvl in range(2, target_level + 1):
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
            char.feats += 1
            if char.has_magical and e3.get('if_magical_spell', False):
                char.spells_from_levels += 1

        if lvl % 8 == 0 and 'bap' in e8:
            char.bap += e8['bap']

        if lvl % 10 == 0 and 'ap' in e10:
            char.ap += e10['ap']

        char.prof = prof['base'] + (lvl // 3)


def apply_paths(char, target_level, build_config, settings):
    r = settings['rules']
    paths_rules = settings['paths']
    available_stp = skill_tree_at_level(target_level)

    path_list = build_config.get('paths', [])
    if not path_list:
        return

    # Apply initial effects for all selected paths first
    for pconf in path_list:
        path_name = pconf['path']
        path_rule = paths_rules.get(path_name, {})
        if 'initial' in path_rule:
            apply_effects(char, path_rule['initial'])
            if path_name == 'Magical':
                char.starting_spells = r['magical_start']['spells_at_level_1']

    # Distribute skill tree points evenly
    total_paths = len(path_list)
    points_per = available_stp // total_paths
    remainder = available_stp % total_paths
    stp_spent = 0

    for i, pconf in enumerate(path_list):
        path_name = pconf['path']
        arch_name = pconf['archetype']
        desired_points = int(pconf['level'])

        # Give this path its share, with remainder going to earlier paths
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
            stp_spent += 1

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


def format_sheet(char, level, settings):
    r = settings['rules']
    lines = []
    sep = "=" * 60
    lines.append(sep)
    lines.append("  " + char.name + " - Level " + str(level))
    lines.append(sep)
    lines.append("")

    lines.append("  STATS:")
    lines.append("    STR: " + str(char.str).rjust(2) + " (" + format_mod(char.mod('str')) + ")")
    lines.append("    DEX: " + str(char.dex).rjust(2) + " (" + format_mod(char.mod('dex')) + ")")
    lines.append("    CON: " + str(char.con).rjust(2) + " (" + format_mod(char.mod('con')) + ")")
    lines.append("    WIS: " + str(char.wis).rjust(2) + " (" + format_mod(char.mod('wis')) + ")")
    lines.append("    INT: " + str(char.int).rjust(2) + " (" + format_mod(char.mod('int')) + ")")
    lines.append("    CHA: " + str(char.cha).rjust(2) + " (" + format_mod(char.mod('cha')) + ")")
    lines.append("")

    lines.append("  COMBAT:")
    lines.append("    AC: " + str(char.ac(r['ac']['dex_bonus_table'])))
    lines.append("    Initiative: " + format_mod(char.mod('dex')))
    lines.append("    Speed: 30 ft")
    lines.append("    AP: " + str(char.ap) + "  BAP: " + str(char.bap) + "  RP: " + str(char.rp))
    lines.append("    Proficiency: +" + str(char.prof))
    lines.append("")

    vd = str(char.vit_n) + "d" + char.vit_die.split('d')[1]
    hd = str(char.hp_n) + "d" + char.hp_die.split('d')[1]
    md = str(char.mana_n) + "d" + char.mana_die.split('d')[1]

    lines.append("  HEALTH POOLS:")
    lines.append("    Vitality:  ~" + str(char.vit_max(r)).rjust(3) + "  (" + vd + ")")
    lines.append("    Health:    ~" + str(char.hp_max(r)).rjust(3) + "  (" + hd + ")")
    lines.append("    Mana:      ~" + str(char.mana_max(r)).rjust(3) + "  (" + md + ")")
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


def format_mod(m):
    if m >= 0:
        return "+" + str(m)
    return str(m)


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
            # char.stat_points already includes level-up gains; add starting points
            total_pts = char.stat_points + settings['rules']['starting_points']['stat_points']
            cost_table = settings['rules']['stat_point_cost']
            spend_stat_points(char, priority, total_pts, cost_table)
            char.stat_points = 0  # All points spent

        apply_paths(char, level, build_config, settings)

        sheet = format_sheet(char, level, settings)
        results.append({'level': level, 'char': char, 'sheet': sheet})
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

            for build_name, results in all_results.items():
                for res in results:
                    if res['level'] == level:
                        c = res['char']
                        vitals.append(c.vit_max(r))
                        healths.append(c.hp_max(r))
                        manas.append(c.mana_max(r))
                        acs.append(c.ac(r['ac']['dex_bonus_table']))
                        feats.append(c.feats)
                        spells.append(c.starting_spells + c.spells_from_levels)
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
            f.write("\n")


def main():
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    settings_path = os.path.join(script_dir, "settings.json")
    settings = load_json(settings_path)

    gen = settings['generation']
    output_dir = gen['output_dir']
    os.makedirs(output_dir, exist_ok=True)

    levels = gen['levels']
    all_results = {}

    for build_name, build_config in settings['builds'].items():
        if not build_config.get('generate', True):
            continue;

        print("Generating: " + build_name + " (levels: " + str(levels) + ")")
        results = generate_build(build_name, build_config, settings, levels)
        all_results[build_name] = results;

        if gen.get('separate_files', True):
            path = write_build_file(build_name, results, output_dir)
            print("  -> " + path)

    if gen.get('generate_average', True):
        avg_path = gen.get('average_file',
                         os.path.join(script_dir, "average.txt"))
        write_average(all_results, settings, avg_path)
        print("Average stats -> " + avg_path)

    print("\nDone! Edit settings.json and re-run to regenerate.")


if __name__ == "__main__":
    main()
