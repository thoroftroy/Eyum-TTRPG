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


def spend_stat_points(char, priority, points, cost_table, char_type='balanced',
                      settings=None, primary_aff=None):
    """Spend stat points to raise stats with realistic spread.
    char_type can be: 'tank', 'marksman', 'caster', 'jack', 'balanced'"""

    points_remaining = points

    # Check spell prereqs for required stats — cap INT at WIS target so
    # mages don't burn all points on INT after meeting reasonable requirements.
    spell_stat_reqs = {'int': 0, 'con': 0, 'str': 0, 'dex': 0, 'wis': 0, 'cha': 0}
    if settings and primary_aff and primary_aff != 'Generic':
        for s in settings.get('spells', {}).get(primary_aff, []):
            for stat in ['int', 'con', 'str', 'dex', 'wis', 'cha']:
                key = f'{stat}_required'
                val = s.get(key, 0)
                if val and val > spell_stat_reqs[stat]:
                    spell_stat_reqs[stat] = val

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
        for i, stat in enumerate(priority):
            if i == 0:
                stat_targets[stat] = 20
            elif i == 1:
                stat_targets[stat] = 14
            elif i == 2:
                stat_targets[stat] = 10
            else:
                stat_targets[stat] = 8

    # Override targets based on spell prereqs — stop once the character
    # meets the highest relevant stat requirement for their primary affinity.
    if char_type == 'caster' or char_type == 'balanced':
        for stat in ['int', 'con', 'str', 'dex', 'wis', 'cha']:
            needed = spell_stat_reqs[stat]
            if needed and needed > stat_targets.get(stat, 8):
                stat_targets[stat] = needed

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


def _affinity_prereqs_met(aff_name, char, affinity_prereqs):
    if not affinity_prereqs or aff_name not in affinity_prereqs:
        return True
    prereq = affinity_prereqs[aff_name]
    needs_all = prereq.get('needs_all', [])
    if needs_all:
        for tier in needs_all:
            for aff in tier.get('affinities', []):
                if char.affinities.get(aff, 0) < tier.get('min_each', 0):
                    return False
        return True
    needs = prereq.get('needs', {})
    min_each = prereq.get('min_each', 0)
    all_of = needs.get('all_of', [])
    any_of = needs.get('any_of', [])
    if all_of:
        for aff in all_of:
            if char.affinities.get(aff, 0) < min_each:
                return False
        return True
    if any_of:
        return any(char.affinities.get(aff, 0) >= min_each for aff in any_of)
    return True


def spend_affinity_points(char, primary_affinity=None, affinity_prereqs=None):
    affp = char.affinity_points
    if affp <= 0:
        return

    if primary_affinity:
        if primary_affinity == 'Generic':
            if getattr(char, 'generic_affinity_spendable', False):
                gained = affp // 3
                if gained > 0:
                    char.affinities['Generic'] = char.affinities.get('Generic', 0) + gained
                    affp -= gained * 3
            char.affinity_points = affp
            return

        def _spend_on(aff_name, points):
            nonlocal affp
            if affp <= 0:
                return
            if aff_name == 'Generic':
                if not getattr(char, 'generic_affinity_spendable', False):
                    return
                take = min(affp // 3, points)
                if take > 0:
                    char.affinities[aff_name] = char.affinities.get(aff_name, 0) + take
                    affp -= take * 3
                return
            if aff_name in affinity_prereqs and not _affinity_prereqs_met(aff_name, char, affinity_prereqs):
                prereq = affinity_prereqs[aff_name]
                needs_all = prereq.get('needs_all', [])
                if needs_all:
                    for tier in needs_all:
                        for a in tier.get('affinities', []):
                            needed = tier.get('min_each', 0) - char.affinities.get(a, 0)
                            if needed > 0 and a != 'Generic':
                                _spend_on(a, needed)
                else:
                    needs = prereq['needs']
                    min_each = prereq.get('min_each', 0)
                    for a in (needs.get('all_of', []) or needs.get('any_of', [])):
                        needed = min_each - char.affinities.get(a, 0)
                        if needed > 0 and a != 'Generic':
                            _spend_on(a, needed)
                if not _affinity_prereqs_met(aff_name, char, affinity_prereqs):
                    return

            take = min(affp, points)
            char.affinities[aff_name] = char.affinities.get(aff_name, 0) + take
            affp -= take

        _spend_on(primary_affinity, affp)
    else:
        pref_order = ['Fire', 'Earth', 'Water', 'Air', 'Radiant', 'Necrotic', 'Psychic']
        while affp > 0:
            spent = False
            for aff in pref_order:
                if affp <= 0:
                    break
                if aff == 'Generic':
                    if getattr(char, 'generic_affinity_spendable', False) and affp >= 3:
                        char.affinities[aff] = char.affinities.get(aff, 0) + 1
                        affp -= 3
                        spent = True
                    continue
                if affinity_prereqs and aff in affinity_prereqs and not _affinity_prereqs_met(aff, char, affinity_prereqs):
                    continue
                char.affinities[aff] = char.affinities.get(aff, 0) + 1
                affp -= 1
                spent = True
            if not spent:
                break

    char.affinity_points = 0
