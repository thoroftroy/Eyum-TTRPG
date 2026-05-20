from .spells import select_spell


def attacks_per_round(char):
    n = 1
    if char.bap >= 2:
        n += char.bap // 2
    return n


def calculate_damage(char, settings):
    result = {'melee': 0, 'ranged': 0, 'magic': 0, 'mana_cost': 0, 'magic_dmg': 0,
              'melee_per_hit': 0, 'ranged_per_hit': 0, 'attacks_per_turn': 1}

    hit_chance_base = 1.0
    die_avg = settings['rules']['die_averages']
    weapons = settings.get('weapons', {})
    weapon_name = char.gear.get('weapon', '')
    weapon_info = weapons.get(weapon_name, {})
    weapon_type = weapon_info.get('type', '')
    weapon_die = weapon_info.get('die')

    is_unarmed = char.is_unarmed or weapon_name == 'none' or weapon_name is None

    if is_unarmed:
        die_order = ['1d4', '1d6', '1d8', '1d10', '1d12']
        brawler_die = die_order[min(char.brawler_stacks, len(die_order) - 1)]
        base_weapon = die_avg.get(brawler_die, 2.5)
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
    hit_chance = min(1.0, hit_chance_base + accuracy_bonus * 0.05)
    hit_chance_adv = 1 - (1 - hit_chance) ** 2
    result['hit_chance'] = hit_chance
    result['hit_chance_advantage'] = hit_chance_adv

    atk_per_round = attacks_per_round(char)

    if char.has_physical:
        melee_total_die = base_weapon + damage_bonus + extra_damage + char.melee_damage
        melee_per_hit = melee_total_die + char.mod('str')
        melee_per_hit_raw = melee_per_hit * hit_chance
        result['melee_per_hit'] = int(melee_per_hit_raw)
        result['melee_per_hit_raw'] = melee_per_hit_raw
        result['melee'] = result['melee_per_hit'] * atk_per_round

        ranged_total_die = base_weapon + damage_bonus + extra_damage + char.ranged_damage
        ranged_per_hit = ranged_total_die + char.mod('dex')
        ranged_per_hit_raw = ranged_per_hit * hit_chance
        result['ranged_per_hit'] = int(ranged_per_hit_raw)
        result['ranged_per_hit_raw'] = ranged_per_hit_raw
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
    hit_chance = dmg_per_turn.get('hit_chance', 0.75)
    hit_chance_adv = dmg_per_turn.get('hit_chance_advantage', 1 - (1 - hit_chance) ** 2)

    phys_per_hit = max(dmg_per_turn.get('melee_per_hit_raw', 0), dmg_per_turn.get('ranged_per_hit_raw', 0))
    if phys_per_hit <= 0 and best_phys_dmg > 0:
        phys_per_hit = best_phys_dmg / max(atk_per_round, 1)

    fr_die_avg = r['die_averages'].get(char.first_round_damage, 0) if char.first_round_damage else 0
    bonus_attacks = 1 if getattr(char, 'ap_first_round', 0) else 0
    r1_adv = getattr(char, 'first_round_advantage', False)
    perm_adv = getattr(char, 'ranged_expertise', False)
    use_adv_r1 = r1_adv or perm_adv
    r1_hc = hit_chance_adv if use_adv_r1 else hit_chance
    perm_hc = hit_chance_adv if perm_adv else hit_chance

    r1_phys = phys_per_hit * (r1_hc / hit_chance) if use_adv_r1 and hit_chance > 0 else phys_per_hit
    r1_fr = fr_die_avg * r1_hc
    r1_adv_dmg = char.ranged_adv_damage_stacks * 3.5 * r1_hc if use_adv_r1 else 0

    if not (magic_dmg > best_phys_dmg and mana_cost > 0):
        round_1_dmg = (atk_per_round + bonus_attacks) * (r1_phys + r1_fr + r1_adv_dmg)
        rest_phys = phys_per_hit * (perm_hc / hit_chance) if perm_adv and hit_chance > 0 else phys_per_hit
        rest_adv_dmg = char.ranged_adv_damage_stacks * 3.5 * perm_hc if perm_adv else 0
        rest_dmg = 9 * atk_per_round * (rest_phys + rest_adv_dmg)
        return {'total': int(round_1_dmg + rest_dmg),
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
            round_atk = atk_per_round + (bonus_attacks if round_idx == 0 else 0)
            r_casts = min(round_atk, remaining_mana // cost) if cost > 0 else round_atk
            fr_this = r1_fr if round_idx == 0 else 0
            round_dmg = r_casts * (spell_dmg + fr_this)
            remaining_mana -= r_casts * cost
            if r_casts > 0:
                rounds_casting += 1
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
