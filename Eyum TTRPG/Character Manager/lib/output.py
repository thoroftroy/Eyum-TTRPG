import os


CATEGORIES = ['Vitality', 'Health', 'Mana', 'AC', 'Feats', 'Spells', 'To Hit', 'Dmg/Turn', 'Dmg/5R', 'Dmg/10R']


def format_mod(m):
    if m >= 0:
        return "+" + str(m)
    return str(m)


def format_sheet(char, level, settings, dmg_perturn, dmg_5round, dmg_10round, tier_label=None):
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
    lines.append("    Initiative: " + format_mod(char.mod('dex') + char.initiative))
    lines.append("    Speed: " + str(char.speed) + " ft")
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
        magic_cast = dmg_perturn.get('magic_dmg', dmg_perturn['magic'] / max(atk, 1))
        if atk > 1:
            lines.append("    Magic Dmg/Cast: " + str(int(magic_cast)) + " | Dmg/Turn: " + str(dmg_perturn['magic']) + " (x" + str(mana_cost) + " mana)")
        else:
            lines.append("    Magic Dmg/Cast: " + str(dmg_perturn['magic']) + " (x" + str(mana_cost) + " mana)")
    lines.append("    Total Dmg/5R:  " + str(int(dmg_5round['total'])))
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
        shield_name = char.gear.get('shield', '')
        if shield_name:
            shield_info = armor_types.get(shield_name, {})
            shield_label = shield_info.get('label', shield_name)
            shield_ac = shield_info.get('ac_bonus', 0)
            shield_line = "    Shield: " + shield_label + " (+" + str(shield_ac) + " AC)"
            if char.shield_master:
                shield_line += " [Shield Master: +" + str(shield_ac * 2) + " AC]"
            lines.append(shield_line)
        lines.append("")

    return "\n".join(lines)


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

        all_affinity_names = set(settings['rules'].get('affinity_prerequisites', {}).keys())
        all_affinity_names.add('Generic')
        for results in all_results.values():
            for res in results:
                all_affinity_names.update(res['char'].affinities.keys())
        all_affinity_names = sorted(all_affinity_names)

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
            dmg_5r = []
            dmg_10r = []
            to_hits = []
            strs = []
            dexs = []
            cons = []
            wiss = []
            ints = []
            chas = []

            affinity_values = {aff: [] for aff in all_affinity_names}

            build_vitals = {}
            build_healths = {}
            build_manas = {}
            build_acs = {}
            build_feats = {}
            build_spells = {}
            build_dmg_per = {}
            build_dmg_5r = {}
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
                        dmg_5 = res['dmg_5round']['total'] if isinstance(res['dmg_5round'], dict) else res['dmg_5round']
                        dmg_10 = res['dmg_10round']['total'] if isinstance(res['dmg_10round'], dict) else res['dmg_10round']
                        best_hit = max(c.to_hit_melee(), c.to_hit_ranged(), c.to_hit_magic())

                        vitals.append(vit)
                        healths.append(hp)
                        manas.append(mana)
                        acs.append(ac_val)
                        feats.append(feat)
                        spells.append(spell)
                        dmg_per.append(dmg_t)
                        dmg_5r.append(dmg_5)
                        dmg_10r.append(dmg_10)
                        to_hits.append(best_hit)
                        strs.append(c.str)
                        dexs.append(c.dex)
                        cons.append(c.con)
                        wiss.append(c.wis)
                        ints.append(c.int)
                        chas.append(c.cha)

                        for aff in all_affinity_names:
                            affinity_values[aff].append(c.affinities.get(aff, 0))

                        build_vitals[build_name] = vit
                        build_healths[build_name] = hp
                        build_manas[build_name] = mana
                        build_acs[build_name] = ac_val
                        build_feats[build_name] = feat
                        build_spells[build_name] = spell
                        build_dmg_per[build_name] = dmg_t
                        build_dmg_5r[build_name] = dmg_5
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
                if dmg_5r:
                    f.write("  Dmg/5R:    avg=" + str(sum(dmg_5r)//len(dmg_5r)) +
                              "  min=" + str(min(dmg_5r)) + "  max=" + str(max(dmg_5r)) + "\n")
                f.write("  Dmg/10R:   avg=" + str(sum(dmg_10r)//len(dmg_10r)) +
                          "  min=" + str(min(dmg_10r)) + "  max=" + str(max(dmg_10r)) + "\n")
                f.write("  To Hit:    avg=" + format_mod(sum(to_hits)//len(to_hits)) +
                          "  min=" + format_mod(min(to_hits)) + "  max=" + format_mod(max(to_hits)) + "\n")
                f.write("  STR:       avg=" + str(sum(strs)//len(strs)) +
                          "  min=" + str(min(strs)) + "  max=" + str(max(strs)) + "\n")
                f.write("  DEX:       avg=" + str(sum(dexs)//len(dexs)) +
                          "  min=" + str(min(dexs)) + "  max=" + str(max(dexs)) + "\n")
                f.write("  CON:       avg=" + str(sum(cons)//len(cons)) +
                          "  min=" + str(min(cons)) + "  max=" + str(max(cons)) + "\n")
                f.write("  WIS:       avg=" + str(sum(wiss)//len(wiss)) +
                          "  min=" + str(min(wiss)) + "  max=" + str(max(wiss)) + "\n")
                f.write("  INT:       avg=" + str(sum(ints)//len(ints)) +
                          "  min=" + str(min(ints)) + "  max=" + str(max(ints)) + "\n")
                f.write("  CHA:       avg=" + str(sum(chas)//len(chas)) +
                          "  min=" + str(min(chas)) + "  max=" + str(max(chas)) + "\n")

                f.write("\n  AFFINITIES:\n")
                active_affs = [(aff, affinity_values[aff]) for aff in all_affinity_names if affinity_values[aff] and max(affinity_values[aff]) > 0]
                for i in range(0, len(active_affs), 6):
                    chunk = active_affs[i:i+6]
                    parts = []
                    for aff, vals in chunk:
                        avg_val = sum(vals) // len(vals)
                        parts.append(aff + ": " + str(avg_val) + " (" + str(min(vals)) + "-" + str(max(vals)) + ")")
                    f.write("    " + "  ".join(parts) + "\n")

                best_vit = max(build_vitals, key=build_vitals.get)
                best_hp = max(build_healths, key=build_healths.get)
                best_mana = max(build_manas, key=build_manas.get)
                best_ac = max(build_acs, key=build_acs.get)
                best_feat = max(build_feats, key=build_feats.get)
                best_spell = max(build_spells, key=build_spells.get)
                best_dmg = max(build_dmg_per, key=build_dmg_per.get)
                best_dmg5 = max(build_dmg_5r, key=build_dmg_5r.get)
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
                f.write("    Dmg/5R:   " + best_dmg5 + " (" + str(build_dmg_5r[best_dmg5]) + ")\n")
                f.write("    Dmg/10R:  " + best_dmg10 + " (" + str(build_dmg_10r[best_dmg10]) + ")\n")
                f.write("    To Hit:   " + best_hit_name + " (" + format_mod(build_to_hits[best_hit_name]) + ")\n")
            f.write("\n")


def write_overall_averages(tier_data, all_tier_results, settings, output_path):
    with open(output_path, 'w') as f:
        f.write("EYUM TTRPG - OVERALL AVERAGES ACROSS ALL GEAR TIERS\n")
        f.write("=" * 60 + "\n\n")

        all_levels = set()
        all_affinity_names = set(settings['rules'].get('affinity_prerequisites', {}).keys())
        all_affinity_names.add('Generic')
        for tier_name, all_results in all_tier_results:
            for results in all_results.values():
                for res in results:
                    all_levels.add(res['level'])
                    all_affinity_names.update(res['char'].affinities.keys())
        all_levels = sorted(all_levels)
        all_affinity_names = sorted(all_affinity_names)

        for level in all_levels:
            f.write("LEVEL " + str(level) + "\n")
            f.write("-" * 40 + "\n")

            first_tier = True
            for tier_name, all_results in all_tier_results:
                strs = []
                dexs = []
                cons = []
                wiss = []
                ints = []
                chas = []
                vitals = []
                healths = []
                manas = []
                affinity_values = {aff: [] for aff in all_affinity_names}
                for build_name, results in all_results.items():
                    for res in results:
                        if res['level'] == level:
                            c = res['char']
                            strs.append(c.str)
                            dexs.append(c.dex)
                            cons.append(c.con)
                            wiss.append(c.wis)
                            ints.append(c.int)
                            chas.append(c.cha)
                            vitals.append(c.vit_max(settings['rules']))
                            healths.append(c.hp_max(settings['rules']))
                            manas.append(c.mana_max(settings['rules']))
                            for aff in all_affinity_names:
                                affinity_values[aff].append(c.affinities.get(aff, 0))
                            break
                if first_tier:
                    f.write("  Stats: Str=" + str(sum(strs)//len(strs)) + " (" + str(min(strs)) + "-" + str(max(strs)) + ")" +
                            "  Dex=" + str(sum(dexs)//len(dexs)) + " (" + str(min(dexs)) + "-" + str(max(dexs)) + ")" +
                            "  Con=" + str(sum(cons)//len(cons)) + " (" + str(min(cons)) + "-" + str(max(cons)) + ")" +
                            "  Wis=" + str(sum(wiss)//len(wiss)) + " (" + str(min(wiss)) + "-" + str(max(wiss)) + ")" +
                            "  Int=" + str(sum(ints)//len(ints)) + " (" + str(min(ints)) + "-" + str(max(ints)) + ")" +
                            "  Cha=" + str(sum(chas)//len(chas)) + " (" + str(min(chas)) + "-" + str(max(chas)) + ")\n")
                    f.write("  Pools: Vit=" + str(sum(vitals)//len(vitals)) + " (" + str(min(vitals)) + "-" + str(max(vitals)) + ")" +
                            "  HP=" + str(sum(healths)//len(healths)) + " (" + str(min(healths)) + "-" + str(max(healths)) + ")" +
                            "  Mana=" + str(sum(manas)//len(manas)) + " (" + str(min(manas)) + "-" + str(max(manas)) + ")\n")
                    f.write("  Affinities:\n")
                    active_affs = [(aff, affinity_values[aff]) for aff in all_affinity_names if affinity_values[aff] and max(affinity_values[aff]) > 0]
                    for i in range(0, len(active_affs), 6):
                        chunk = active_affs[i:i+6]
                        parts = []
                        for aff, vals in chunk:
                            avg_val = sum(vals) // len(vals)
                            parts.append(aff + ": " + str(avg_val) + " (" + str(min(vals)) + "-" + str(max(vals)) + ")")
                        f.write("    " + "  ".join(parts) + "\n")
                    first_tier = False

            f.write("\n")
            for tier_name, all_results in all_tier_results:
                acs_vals = []
                dmg_t = []
                dmg_5 = []
                dmg_10 = []
                to_hits = []
                for build_name, results in all_results.items():
                    for res in results:
                        if res['level'] == level:
                            c = res['char']
                            acs_vals.append(c.ac(c.gear.get('armor', 'none'), settings.get('armor_types', {}), settings['rules']['ac']['dex_bonus_table']))
                            dmg_t.append(res['dmg_perturn']['per_turn'])
                            dmg_5.append(res['dmg_5round']['total'] if isinstance(res['dmg_5round'], dict) else res['dmg_5round'])
                            dmg_10.append(res['dmg_10round']['total'] if isinstance(res['dmg_10round'], dict) else res['dmg_10round'])
                            to_hits.append(max(c.to_hit_melee(), c.to_hit_ranged(), c.to_hit_magic()))
                            break

                avg_hit = sum(to_hits) // len(to_hits)
                label_padded = tier_name.replace('_', ' ').title().ljust(15)
                f.write("  " + label_padded + ": AC=" + str(sum(acs_vals)//len(acs_vals)).rjust(2) +
                        " (" + str(min(acs_vals)) + "-" + str(max(acs_vals)) + ")" +
                        "   Hit=" + format_mod(avg_hit).rjust(4) +
                        " (" + format_mod(min(to_hits)) + "-" + format_mod(max(to_hits)) + ")" +
                        "  Dmg=" + str(sum(dmg_t)//len(dmg_t)).rjust(4) +
                        " (" + str(min(dmg_t)) + "-" + str(max(dmg_t)) + ")" +
                        "  Dmg/5R=" + str(sum(dmg_5)//len(dmg_5)).rjust(6) +
                        " (" + str(min(dmg_5)) + "-" + str(max(dmg_5)) + ")" +
                        "  Dmg/10R=" + str(sum(dmg_10)//len(dmg_10)).rjust(6) +
                        " (" + str(min(dmg_10)) + "-" + str(max(dmg_10)) + ")\n")
            f.write("\n")


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
                'Dmg/5R': res['dmg_5round']['total'] if isinstance(res['dmg_5round'], dict) else res['dmg_5round'],
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

    RANGE_BONUS = 15
    weapons_data = settings.get('weapons', {})
    ranged_bonus = {}
    for bn in all_build_names:
        bc = build_configs.get(bn, {})
        if bc.get('has_magical', False):
            ranged_bonus[bn] = RANGE_BONUS
        else:
            wpn = bc.get('gear', {}).get('weapon', '')
            wpn_type = weapons_data.get(wpn, {}).get('type', '')
            ranged_bonus[bn] = RANGE_BONUS if wpn_type == 'ranged' else 0

    total_levels_per_tier = len(all_levels)
    total_wins_possible = total_levels_per_tier * len(CATEGORIES)

    with open(output_path, 'w') as f:
        f.write("EYUM TTRPG - BALANCE SUMMARY & RECOMMENDATIONS\n")
        f.write("=" * 60 + "\n\n")
        f.write("Generated from analysis of " + str(len(all_levels)) + " levels")
        f.write(" across " + str(len(all_tier_results)) + " gear tiers")
        f.write(" and " + str(len(all_build_names)) + " builds.\n\n")

        f.write("OVERALL BUILD DOMINANCE\n")
        f.write("-" * 40 + "\n")
        sorted_builds = sorted(all_build_names,
                               key=lambda b: sum(overall_wins[c].get(b, 0) for c in CATEGORIES) + ranged_bonus.get(b, 0),
                               reverse=True)
        total_cross_cat_wins = sum(sum(overall_wins[c].values()) for c in CATEGORIES) + sum(ranged_bonus.values()) or 1
        for bn in sorted_builds:
            total = sum(overall_wins[c].get(bn, 0) for c in CATEGORIES) + ranged_bonus.get(bn, 0)
            pct = total * 100 / total_cross_cat_wins
            f.write("  " + bn.ljust(18) + ": " + str(total).rjust(3) + " category-level wins (" + format(pct, '.1f') + "%)\n")
        f.write("\n")

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
                   sum(overall_wins['Dmg/5R'].get(b, 0) for b in builds) + \
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
                elif cat in ('Dmg/Turn', 'Dmg/5R', 'Dmg/10R'):
                    f.write("    >>> IMBALANCE: Damage output is concentrated in one build.\n")
                    f.write("    Consider: rebalancing damage scaling so other builds can compete.\n")
            elif top_pct < 40:
                f.write("    (Well-distributed across multiple builds)\n")
            else:
                f.write("    (Moderate concentration)\n")
        f.write("\n")

        f.write("STAT ANALYSIS\n")
        f.write("-" * 40 + "\n")
        all_stat_values = {s: [] for s in ['str', 'dex', 'con', 'wis', 'int', 'cha']}
        all_stat_max = {s: {} for s in ['str', 'dex', 'con', 'wis', 'int', 'cha']}
        for tier_name, all_results in all_tier_results:
            for build_name, results in all_results.items():
                for res in results:
                    c = res['char']
                    for s in ['str', 'dex', 'con', 'wis', 'int', 'cha']:
                        val = getattr(c, s)
                        all_stat_values[s].append(val)
                        prev = all_stat_max[s].get(build_name, 0)
                        all_stat_max[s][build_name] = max(prev, val)
                    break

        for s in ['str', 'dex', 'con', 'wis', 'int', 'cha']:
            avg = sum(all_stat_values[s]) // len(all_stat_values[s])
            max_build = max(all_stat_max[s], key=all_stat_max[s].get)
            max_val = all_stat_max[s][max_build]
            min_build = min(all_stat_max[s], key=all_stat_max[s].get)
            min_val = all_stat_max[s][min_build]
            f.write("  " + s.upper().ljust(6) + ": avg=" + str(avg).rjust(2) +
                    "  max=" + max_build.ljust(18) + " (" + str(max_val).rjust(2) + ")" +
                    "  min=" + min_build.ljust(18) + " (" + str(min_val).rjust(2) + ")\n")
        f.write("\n")

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
                if cat in ('Dmg/Turn', 'Dmg/5R', 'Dmg/10R'):
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
        f.write("RACE POPULARITY ANALYSIS\n")
        f.write("-" * 40 + "\n")
        race_counts = {}
        total_non_casual = 0
        seen_builds = set()
        for tier_name, all_results in all_tier_results:
            for build_name, results in all_results.items():
                if build_name in seen_builds:
                    continue
                seen_builds.add(build_name)
                bc = build_configs.get(build_name, {})
                if bc.get('worst', False):
                    continue
                if build_name.lower().startswith('casual '):
                    continue
                total_non_casual += 1
                if results and results[0].get('race', 'none') != 'none':
                    race = results[0]['race']
                    if race not in race_counts:
                        race_counts[race] = {'count': 0, 'builds': []}
                    race_counts[race]['count'] += 1
                    race_counts[race]['builds'].append(build_name)

        sorted_races = sorted(race_counts.items(), key=lambda x: x[1]['count'], reverse=True)
        if not sorted_races:
            f.write("  No races selected for any build.\n")
        else:
            for race, info in sorted_races:
                pct = info['count'] * 100 / total_non_casual
                flag = ""
                if pct > 50:
                    flag = "  <<< OVER-TUNED: chosen by over half of all builds"
                elif pct > 33:
                    flag = "  <<< STRONG: chosen by over a third of all builds"
                elif pct >= 20:
                    flag = "  <<< POPULAR: may indicate above-average strength"
                f.write("  " + race.ljust(24) + ": " + str(info['count']).rjust(2) + "/" +
                        str(total_non_casual) + " (" + format(pct, '.0f') + "%)" + flag + "\n")
            if race_counts:
                top_race = sorted_races[0][0]
                top_pct = sorted_races[0][1]['count'] * 100 / total_non_casual
                if top_pct > 50:
                    f.write("\n  >>> " + top_race + " is overwhelmingly popular. Consider reducing its stat bonuses,\n")
                    f.write("      racial path benefits, or affinity bonuses so other races are competitive.\n")
                elif top_pct > 33:
                    f.write("\n  >>> " + top_race + " is very popular (>" + str(int(top_pct)) +
                            "% pick rate). Review if its power budget is too high.\n")
        f.write("\n")
        f.write("SPELL ANALYSIS & RANKINGS\n")
        f.write("-" * 40 + "\n")
        try:
            die_avg = r.get('die_averages', {})
            spells_data = settings.get('spells', {})
            spell_stats = []
            for aff_name, spells in spells_data.items():
                if aff_name in ('Healing', 'Eldritch'):
                    continue
                for spell in spells:
                    mana = spell.get('mana', 0)
                    dmg = 0
                    if spell.get('damage_dice'):
                        dmg += die_avg.get(spell['damage_dice'], 0)
                    if spell.get('damage_flat'):
                        dmg += spell['damage_flat']
                    if spell.get('damage_formula'):
                        dmg += 10
                    if dmg <= 0 and mana <= 0:
                        continue
                    eff = dmg / max(mana, 1)
                    spell_stats.append((dmg, mana, eff, aff_name, spell.get('name', '?')))
            if spell_stats:
                spell_stats.sort(key=lambda x: x[0], reverse=True)
                f.write("\nTop 5 by base damage:\n")
                for dmg, mana, eff, aff, name in spell_stats[:5]:
                    f.write(f"  {aff}:{name} — {dmg:.1f} dmg, {mana} mana\n")
                spell_stats.sort(key=lambda x: x[2], reverse=True)
                f.write("\nTop 5 by mana efficiency:\n")
                for dmg, mana, eff, aff, name in spell_stats[:5]:
                    f.write(f"  {aff}:{name} — {eff:.2f} dmg/mana, {dmg:.1f} dmg, {mana} mana\n")
                spell_stats.sort(key=lambda x: x[1])
                zero_mana = [s for s in spell_stats if s[1] == 0]
                if zero_mana:
                    f.write("\nFree spells (0 mana):\n")
                    for dmg, mana, eff, aff, name in zero_mana[:5]:
                        f.write(f"  {aff}:{name} — {dmg:.1f} dmg\n")
                high_cost = sorted([s for s in spell_stats if s[1] > 50], key=lambda x: x[0], reverse=True)
                if high_cost:
                    f.write("\nHighest-cost spells (50+ mana):\n")
                    for dmg, mana, eff, aff, name in high_cost[:5]:
                        f.write(f"  {aff}:{name} — {dmg:.1f} dmg, {mana} mana, {eff:.2f} dmg/mana\n")
        except Exception:
            pass
        f.write("\n")
        f.write("ARCHETYPE DRIFT DETECTION\n")
        f.write("-" * 40 + "\n")
        f.write("Checks whether Archetype-specialist builds actually focus on their\n")
        f.write("namesake archetype, or drift toward a different one that scores higher.\n")
        f.write("Drift = a non-Racial archetype has more levels than the namesake.\n\n")

        seen_drifts = set()
        drift_found = 0
        for build_name, bc in build_configs.items():
            if not build_name.startswith('Archetype:'):
                continue
            target_arch = build_name.split(':', 1)[1].strip()
            paths = bc.get('paths', {})
            if not paths:
                continue
            primary_path = None
            primary_arch = None
            if isinstance(paths, dict):
                for pname, archs in paths.items():
                    if archs:
                        primary_path = pname
                        primary_arch = archs[0]
                        break
            elif isinstance(paths, list):
                for p in paths:
                    primary_path = p.get('path')
                    primary_arch = p.get('archetype')
                    if primary_arch:
                        break
            if not primary_arch:
                continue

            # Check only first tier result (deduplicate across gear tiers)
            first_tier = all_tier_results[0][1] if all_tier_results else {}
            results = first_tier.get(build_name, [])
            if not results:
                continue
            max_res = max(results, key=lambda r: r['level'])
            c = max_res['char']
            arch_levels = getattr(c, 'archetype_levels', {})
            if not arch_levels:
                continue

            # Find the archetype with most levels, EXCLUDING Racial path
            best_arch = None
            best_levels = 0
            for (p, a), lv in arch_levels.items():
                if p == 'Racial':
                    continue
                if lv > best_levels:
                    best_levels = lv
                    best_arch = a

            if best_arch and best_arch != primary_arch:
                key = (build_name, best_arch)
                if key in seen_drifts:
                    continue
                seen_drifts.add(key)
                drift_found += 1
                f.write(f"  DRIFT: {build_name}\n")
                f.write(f"    Namesake: {primary_arch} (in {primary_path})\n")
                f.write(f"    Drifted to: {best_arch} ({best_levels} levels)\n")
                sorted_archs = sorted([(a, lv) for (p, a), lv in arch_levels.items() if p != 'Racial'], key=lambda x: x[1], reverse=True)
                arch_summary = ', '.join(f'{a}({lv})' for a, lv in sorted_archs[:5])
                f.write(f"    Non-Racial archetypes: {arch_summary}\n\n")

        if drift_found == 0:
            f.write("  No drift detected — all Archetype builds focus on their namesake.\n")
        else:
            f.write(f"  {drift_found} builds drifted away from their named archetype.\n")
            f.write("  This means another archetype scored higher than the specialized one.\n")
            f.write("  The named archetype may need buffing or the driftee may need nerfing.\n")
        f.write("\n")
