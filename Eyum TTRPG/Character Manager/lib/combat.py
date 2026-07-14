from .spells import select_spell
from .die_avg import die_average


def attacks_per_round(char):
    n = 1
    if char.bap >= 2:
        n += char.bap // 2
    if getattr(char, 'extra_attack_bap', False):
        n += 1
    return n


def calculate_damage(char, settings):
    result = {'melee': 0, 'ranged': 0, 'magic': 0, 'mana_cost': 0, 'magic_dmg': 0,
              'melee_per_hit': 0, 'ranged_per_hit': 0, 'attacks_per_turn': 1,
              'cond_dmg': 0, 'cond_names': [], 'spell_extra_effect': ''}

    hit_chance_base = 1.0
    weapons = settings.get('weapons', {})
    weapon_name = char.gear.get('weapon', '')
    weapon_info = weapons.get(weapon_name, {})
    weapon_type = weapon_info.get('type', '')
    weapon_die = weapon_info.get('die')

    is_unarmed = char.is_unarmed or weapon_name == 'none' or weapon_name is None

    if is_unarmed:
        die_order = ['1d4', '1d6', '1d8', '1d10', '1d12']
        if char.tull_claw_die:
            claw_idx = die_order.index(char.tull_claw_die)
            effective_idx = min(claw_idx + char.brawler_stacks, len(die_order) - 1)
            base_weapon = die_average(die_order[effective_idx], 2.5) + char.tull_claw_flat
        else:
            brawler_die = die_order[min(char.brawler_stacks, len(die_order) - 1)]
            base_weapon = die_average(brawler_die, 2.5)
        damage_bonus = 0
        extra_damage = 0
        weapon_type = 'melee'
    else:
        base_weapon = die_average(weapon_die, 0) if weapon_die else 0
        damage_bonus = weapon_info.get('damage_bonus', 0)
        extra_damage_die = weapon_info.get('extra_damage_die')
        extra_damage = die_average(extra_damage_die, 0) if extra_damage_die else 0

    weapon_accuracy = weapon_info.get('accuracy_bonus', 0) if not is_unarmed else 0
    accuracy_bonus = char.weapon_group_accuracy + char.steady_aim_accuracy + weapon_accuracy
    if weapon_type == 'melee' and char.dual_wield_accuracy > 0 and not is_unarmed:
        accuracy_bonus += char.dual_wield_accuracy
    hit_chance = min(1.0, hit_chance_base + accuracy_bonus * 0.05)
    hit_chance_adv = 1 - (1 - hit_chance) ** 2
    if char.point_blank:
        hit_chance = hit_chance_adv
    result['hit_chance'] = hit_chance
    result['hit_chance_advantage'] = hit_chance_adv

    atk_per_round = attacks_per_round(char)
    spell_atks = 1

    crit_bonus_avg = 0
    if char.crit_bonus_die:
        crit_bonus_avg = die_average(char.crit_bonus_die, 0) * 0.05

    cleave_bonus_avg = char.cleave_damage * 0.75 if char.cleave_damage else 0

    charge_bonus_avg = 0
    if char.charge_die:
        charge_bonus_avg = die_average(char.charge_die, 0)

    per_hit_feat_bonus = crit_bonus_avg + cleave_bonus_avg + (charge_bonus_avg / max(atk_per_round, 1))
    # Skirmisher movement damage: (speed / 5) * per_5ft_bonus, applies once per round then resets.
    # Model as average bonus spread across all attacks.
    skirmish_bonus = 0
    if hasattr(char, 'skirmish_per_5ft') and char.skirmish_per_5ft > 0:
        skirmish_bonus = (char.speed / 10.0) * char.skirmish_per_5ft
    per_hit_feat_bonus += skirmish_bonus / max(atk_per_round, 1)

    if char.has_physical:
        melee_total_die = base_weapon + damage_bonus + extra_damage + char.melee_damage
        melee_per_hit = melee_total_die + char.mod('str') + per_hit_feat_bonus
        melee_per_hit_raw = melee_per_hit * hit_chance
        result['melee_per_hit'] = int(melee_per_hit_raw)
        result['melee_per_hit_raw'] = melee_per_hit_raw
        result['melee'] = result['melee_per_hit'] * atk_per_round

        ranged_total_die = base_weapon + damage_bonus + extra_damage + char.ranged_damage
        ranged_per_hit = ranged_total_die + char.mod('dex') + per_hit_feat_bonus
        ranged_per_hit_raw = ranged_per_hit * hit_chance
        result['ranged_per_hit'] = int(ranged_per_hit_raw)
        result['ranged_per_hit_raw'] = ranged_per_hit_raw
        result['ranged'] = result['ranged_per_hit'] * atk_per_round

    if char.has_magical:
        spell_info, spell_dmg = select_spell(char, settings, max_mana=char.mana_max(settings['rules']))
        if spell_info:
            mana_mult = getattr(char, 'spell_mana_mult', 1)
            if not spell_info.get('use_multiplier', True):
                mana_mult = 1
            cost = spell_info['spell']['mana'] * mana_mult
            is_conc = spell_info['spell'].get('concentration')
            has_bap = spell_info['spell'].get('bap_attack')
            retal = spell_info['spell'].get('retaliation', {})

            # Retaliation damage (triggered by being attacked — assume 1 hit/round)
            retal_dmg = 0
            if retal:
                retal_dice = die_average(retal.get('dice', ''))
                retal_flat = retal.get('flat', 0)
                retal_dmg = int(retal_dice + retal_flat)

            if is_conc and has_bap:
                ap_actions = max(0, char.ap - 1)
                bap_actions = char.bap
                total_actions = ap_actions + bap_actions
                cond_dmg_val = spell_info.get('cond_dmg', 0)
                # BAp attacks cost 1/3 of the spell's base mana per bolt per the handbook
                bolt_mana = max(1, spell_info['spell']['mana'] // 3)
                total_mana = cost + total_actions * bolt_mana
                mana_pool = char.mana_max(settings['rules'])
                max_by_mana = max(0, (mana_pool - cost) // max(1, bolt_mana))
                effective_actions = min(total_actions, max_by_mana)
                ap_eff = min(ap_actions, effective_actions)
                bap_eff = effective_actions - ap_eff
                # BAp bolts don't get base magic damage per the handbook
                bolt_base = max(0, spell_dmg - cond_dmg_val - getattr(char, 'magic_damage', 0) * getattr(char, 'spell_damage_mult', 1))
                magic = int((ap_eff * bolt_base * 2.0) + (bap_eff * bolt_base)
                            + (effective_actions * cond_dmg_val) + retal_dmg)
                result['magic'] = magic
                result['magic_dmg'] = spell_dmg
                result['mana_cost'] = cost
                result['bap_attack'] = True
                spell_atks = total_actions
            elif is_conc:
                # Passive concentration: 1 AP on concentration, remaining on next-best non-conc spell
                si2, sd2 = select_spell(char, settings, max_mana=char.mana_max(settings['rules']),
                                        exclude_concentration=True)
                same = si2 and si2.get('spell', {}).get('name') == spell_info['spell'].get('name')
                if si2 and sd2 > 0 and not same:
                    mn2 = getattr(char, 'spell_mana_mult', 1)
                    if not si2.get('use_multiplier', True):
                        mn2 = 1
                    cost2 = si2['spell']['mana'] * mn2
                    secondary_actions = max(0, char.ap - 1) + char.bap // 2  # BAp converts to Ap at 2:1
                    # Mana pool AFTER paying for the concentration spell
                    mana_pool_for_secondary = char.mana_max(settings['rules']) - cost
                    max_cast2 = mana_pool_for_secondary // max(1, cost2) if cost2 > 0 else secondary_actions
                    if max_cast2 <= 0:
                        result['magic'] = int(spell_dmg + retal_dmg)
                        result['magic_dmg'] = spell_dmg
                    else:
                        casts2 = min(secondary_actions, max_cast2)
                        best_total = int(spell_dmg + sd2 * casts2 + retal_dmg)
                        best_secondary = (si2, sd2, casts2)
                        
                        # Try other non-concentration spells — a cheaper spell cast more times
                        # might out-damage the highest per-cast spell with fewer casts.
                        # Restrict to primary affinity only (same as select_spell).
                        spells_data = settings.get('spells', {})
                        from .spells import check_spell_prereqs, spell_avg_damage, spell_save_dc
                        affinity_prereqs = settings.get('rules', {}).get('affinity_prerequisites', {})
                        primary = getattr(char, 'primary_affinity', None)
                        target_save = __import__('lib.spells', fromlist=['avg_save_mod']).avg_save_mod(char.prof)
                        search_elements = [primary] if primary else list(spells_data.keys())
                        for elem in search_elements:
                            if elem not in spells_data:
                                continue
                            for s in spells_data[elem]:
                                if s.get('concentration'): continue
                                if s['name'] == spell_info['spell'].get('name'): continue
                                if s['name'] == si2['spell']['name']: continue
                                elem_val = char.affinities.get(elem, 0)
                                if not check_spell_prereqs(char, s, elem, elem_val, affinity_prereqs):
                                    continue
                                sd = spell_avg_damage(s, elem, elem_val, 0.75, char)
                                # Apply save multiplier for save spells (matching select_spell logic)
                                if s.get('save'):
                                    dc = spell_save_dc(char, elem) if elem else 0
                                    if s.get('save_half', False):
                                        fail_chance = min(0.95, max(0.05, (dc - 1 - target_save) / 20.0))
                                        save_mul = fail_chance + (1 - fail_chance) * 0.5
                                    else:
                                        fail_chance = min(0.95, max(0.05, (dc - 1 - target_save) / 20.0))
                                        save_mul = fail_chance
                                    sd *= save_mul
                                if sd <= 0: continue
                                c2 = s['mana'] * mn2
                                if c2 <= 0: continue
                                mc2 = mana_pool_for_secondary // max(1, c2)
                                if mc2 <= 0: continue
                                cs2 = min(secondary_actions, mc2)
                                total = int(spell_dmg + sd * cs2 + retal_dmg)
                                if total > best_total:
                                    best_total = total
                                    best_secondary = ({'spell': s, 'element': elem, 'damage_per_cast': sd,
                                                       'use_multiplier': True, 'cond_dmg': 0, 'cond_names': [],
                                                       'extra_effect': s.get('extra_effect', '')}, sd, cs2)
                        
                        magic = best_total
                        si2, sd2, casts2 = best_secondary
                        result['magic'] = magic
                        result['magic_dmg'] = spell_dmg + sd2
                        result['secondary_spell'] = si2.get('spell', {}).get('name', '')
                        result['secondary_dmg'] = sd2
                        result['secondary_casts'] = casts2
                        result['secondary_mana'] = si2.get('spell', {}).get('mana', 0)
                else:
                    result['magic'] = int(spell_dmg + retal_dmg)
                    result['magic_dmg'] = spell_dmg
                result['mana_cost'] = cost
                spell_atks = 1
            else:
                spell_atks = atk_per_round
                if spell_info['spell'].get('costs_bonus_action'):
                    spell_atks = min(char.ap, char.bap)
                max_casts_by_mana = char.mana_max(settings['rules']) // max(1, cost)
                casts = min(spell_atks, max_casts_by_mana)
                result['magic'] = int(spell_dmg * casts + retal_dmg)
                result['magic_dmg'] = spell_dmg
                result['mana_cost'] = cost
                result['spell_atks_raw'] = spell_atks
                result['spell_atks_mana_capped'] = casts
                # If multiplier is active but base version would give more damage, use base
                if mana_mult > 1 and spell_info.get('use_multiplier', True):
                    base_cost = spell_info['spell']['mana']
                    base_casts = min(spell_atks, char.mana_max(settings['rules']) // max(1, base_cost))
                    base_dmg = spell_dmg / char.spell_damage_mult if char.spell_damage_mult > 1 else spell_dmg
                    base_total = int(base_dmg * base_casts + retal_dmg)
                    if base_total > result['magic']:
                        result['magic'] = base_total
                        result['mana_cost'] = base_cost
                        result['spell_atks_mana_capped'] = base_casts
            result['cond_dmg'] = spell_info.get('cond_dmg', 0)
            result['cond_names'] = spell_info.get('cond_names', []) if spell_info.get('cond_dmg', 0) > 0 else []
            result['spell_extra_effect'] = spell_info.get('extra_effect', '')
            result['spell_name'] = spell_info['spell'].get('name', '')
            result['spell_element'] = spell_info.get('element', '')
            result['concentration'] = spell_info['spell'].get('concentration', False)
            result['retal_dmg'] = retal_dmg
            result['skip_info'] = spell_info.get('skip_info', {})

    result['per_turn'] = max(result['melee'], result['ranged'], result['magic'])
    result['attacks_per_turn'] = atk_per_round
    result['spell_attacks_per_turn'] = spell_atks

    return result


def _x_round_damage(char, r, dmg_per_turn, settings, num_rounds):
    atk_per_round = dmg_per_turn.get('attacks_per_turn', attacks_per_round(char))
    spell_atks = dmg_per_turn.get('spell_attacks_per_turn', atk_per_round)
    best_phys_dmg = max(dmg_per_turn['melee'], dmg_per_turn['ranged'])
    magic_dmg = dmg_per_turn['magic']
    mana_cost = dmg_per_turn['mana_cost']
    hit_chance = dmg_per_turn.get('hit_chance', 0.75)
    hit_chance_adv = dmg_per_turn.get('hit_chance_advantage', 1 - (1 - hit_chance) ** 2)

    phys_per_hit = max(dmg_per_turn.get('melee_per_hit_raw', 0), dmg_per_turn.get('ranged_per_hit_raw', 0))
    if phys_per_hit <= 0 and best_phys_dmg > 0:
        phys_per_hit = best_phys_dmg / max(atk_per_round, 1)

    fr_die_avg = die_average(char.first_round_damage) if char.first_round_damage else 0
    bonus_attacks = 1 if getattr(char, 'ap_first_round', 0) else 0
    r1_adv = getattr(char, 'first_round_advantage', False)
    perm_adv = getattr(char, 'ranged_expertise', False)
    use_adv_r1 = r1_adv or perm_adv
    r1_hc = hit_chance_adv if use_adv_r1 else hit_chance
    perm_hc = hit_chance_adv if perm_adv else hit_chance

    r1_phys = phys_per_hit * (r1_hc / hit_chance) if use_adv_r1 and hit_chance > 0 else phys_per_hit
    r1_fr = fr_die_avg * r1_hc
    r1_adv_dmg = char.ranged_adv_damage_stacks * 3.5 * r1_hc if use_adv_r1 else 0

    magic_dmg_per_cast = dmg_per_turn.get('magic_dmg', 0)
    if magic_dmg_per_cast <= 0 and magic_dmg > 0:
        magic_dmg_per_cast = magic_dmg

    if not (magic_dmg > best_phys_dmg and magic_dmg_per_cast > 0):
        round_1_dmg = (atk_per_round + bonus_attacks) * (r1_phys + r1_fr + r1_adv_dmg)
        rest_phys = phys_per_hit * (perm_hc / hit_chance) if perm_adv and hit_chance > 0 else phys_per_hit
        rest_adv_dmg = char.ranged_adv_damage_stacks * 3.5 * perm_hc if perm_adv else 0
        rest_dmg = (num_rounds - 1) * atk_per_round * (rest_phys + rest_adv_dmg)
        return {'total': int(round_1_dmg + rest_dmg),
                'mana_start': 0, 'mana_end': 0,
                'rounds_casting': 0,
                'mana_per_round': 0}

    if mana_cost <= 0:
        total_dmg = int(spell_atks * magic_dmg_per_cast * num_rounds)
        return {'total': total_dmg,
                'mana_start': 0, 'mana_end': 0,
                'rounds_casting': num_rounds,
                'mana_per_round': 0}

    max_mana = char.mana_max(r)
    total = 0
    remaining_mana = max_mana
    rounds_casting = 0

    mana_mult = getattr(char, 'spell_mana_mult', 1)
    retal = dmg_per_turn.get('retal_dmg', 0)

    # Storm/bap_attack style: bolts every round
    if dmg_per_turn.get('bap_attack'):
        bolt_base = magic_dmg_per_cast
        cond_val = dmg_per_turn.get('cond_dmg', 0)
        # BAp bolts don't get base magic damage per the handbook
        magic_dmg_portion = getattr(char, 'magic_damage', 0) * getattr(char, 'spell_damage_mult', 1)
        base = max(0, bolt_base - cond_val - magic_dmg_portion)
        first_round = (max(0, char.ap - 1) * base * 2.0 + char.bap * base
                       + (max(0, char.ap - 1) + char.bap) * cond_val)
        later_round = (char.ap * base * 2.0 + char.bap * base
                       + (char.ap + char.bap) * cond_val)
        total_dmg = int(first_round + later_round * (num_rounds - 1))
        return {'total': total_dmg,
                'mana_start': int(max_mana),
                'mana_end': int(max_mana - mana_cost),
                'rounds_casting': num_rounds,
                'mana_per_round': int(mana_cost)}

    # Use calculate_damage's results — don't re-select spells.
    is_conc_spell = dmg_per_turn.get('concentration', False)
    if is_conc_spell:
        mana_cost = dmg_per_turn.get('mana_cost', mana_cost)

    if is_conc_spell:
        conc_drain = mana_cost // 5
        sec_name = dmg_per_turn.get('secondary_spell', '')
        sec_dmg = dmg_per_turn.get('secondary_dmg', 0)
        sec_casts = dmg_per_turn.get('secondary_casts', 0)
        sec_mana = dmg_per_turn.get('secondary_mana', 0)

        if sec_name and sec_dmg > 0 and sec_casts > 0:
            round_full_dmg = int(magic_dmg_per_cast + sec_dmg * sec_casts + retal)
            round_conc_only = int(magic_dmg_per_cast + retal)
            round1_mana = mana_cost + sec_mana * sec_casts
            later_full_mana = conc_drain + sec_mana * sec_casts

            # How many full-secondary rounds can we afford?
            mana_after_r1 = max(0, max_mana - round1_mana)
            full_rounds_after_r1 = max(0, mana_after_r1 // max(1, later_full_mana)) if later_full_mana > 0 else (num_rounds - 1)
            full_rounds = 1 + full_rounds_after_r1  # round 1 + extra full rounds

            # Remaining rounds: concentration only (just conc_drain per turn)
            conc_only_rounds = 0
            if full_rounds < num_rounds:
                remaining_mana = max(0, max_mana - round1_mana - full_rounds_after_r1 * later_full_mana)
                conc_only_rounds = min(num_rounds - full_rounds, remaining_mana // max(1, conc_drain))

            total_dmg = int(round_full_dmg * full_rounds + round_conc_only * conc_only_rounds)
            return {'total': total_dmg,
                    'mana_start': int(max_mana),
                    'mana_end': int(max(0, max_mana - round1_mana - full_rounds_after_r1 * later_full_mana - conc_only_rounds * conc_drain)),
                    'rounds_casting': full_rounds + conc_only_rounds,
                    'mana_per_round': int(mana_cost + conc_drain + sec_mana * sec_casts)}
        else:
            # No secondary — concentration damage every turn, limited by mana for conc_drain
            round_dmg = int(magic_dmg_per_cast + retal)
            affordable = min(num_rounds, 1 + (max_mana - mana_cost) // max(1, conc_drain))
            total_dmg = int(round_dmg * affordable)
            total_mana = mana_cost + conc_drain * (affordable - 1)
            return {'total': total_dmg,
                    'mana_start': int(max_mana),
                    'mana_end': int(max(0, max_mana - total_mana)),
                    'rounds_casting': affordable,
                    'mana_per_round': int(mana_cost + conc_drain)}

    # Default: proceed with normal multi-round calculation
    conc_active_cost = 0  # mana cost of currently active concentration spell
    for round_idx in range(num_rounds):
        # Deduct concentration drain from active concentration spell
        if conc_active_cost > 0:
            conc_drain = conc_active_cost // 5
            if remaining_mana >= conc_drain:
                remaining_mana -= conc_drain
            else:
                conc_active_cost = 0  # can't pay, spell ends
        remaining_mana = max(0, remaining_mana)

        spell_info, spell_dmg = select_spell(char, settings, max_mana=remaining_mana)
        if spell_info and spell_dmg > phys_per_hit:
            mana_mult = getattr(char, 'spell_mana_mult', 1)
            if not spell_info.get('use_multiplier', True):
                mana_mult = 1
            cost = spell_info['spell']['mana'] * mana_mult
            round_atk = spell_atks + (bonus_attacks if round_idx == 0 else 0)
            r_casts = min(round_atk, remaining_mana // cost) if cost > 0 else round_atk
            fr_this = r1_fr if round_idx == 0 else 0
            round_dmg = r_casts * (spell_dmg + fr_this)
            remaining_mana -= r_casts * cost
            if r_casts > 0:
                rounds_casting += 1
            # Track concentration: if this spell has concentration, it becomes the active one
            if spell_info['spell'].get('concentration') and r_casts > 0:
                conc_active_cost = spell_info['spell']['mana']  # base mana for drain calc
        else:
            if round_idx == 0:
                round_dmg = (atk_per_round + bonus_attacks) * (r1_phys + r1_fr + r1_adv_dmg)
            else:
                rest_p = phys_per_hit * (perm_hc / hit_chance) if perm_adv and hit_chance > 0 else phys_per_hit
                rest_a = char.ranged_adv_damage_stacks * 3.5 * perm_hc if perm_adv else 0
                round_dmg = atk_per_round * (rest_p + rest_a)
        total += round_dmg

    return {'total': int(total),
            'mana_start': int(max_mana),
            'mana_end': int(max(0, remaining_mana)),
            'rounds_casting': rounds_casting,
            'mana_per_round': int(mana_cost)}


def calculate_5_round_damage(char, r, dmg_per_turn, settings):
    return _x_round_damage(char, r, dmg_per_turn, settings, 5)


def calculate_10_round_damage(char, r, dmg_per_turn, settings):
    return _x_round_damage(char, r, dmg_per_turn, settings, 10)
