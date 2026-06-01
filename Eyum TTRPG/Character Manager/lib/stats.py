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


def spend_affinity_points(char, primary_affinity=None, affinity_prereqs=None):
    affp = char.affinity_points
    if affp <= 0:
        return

    if primary_affinity and affinity_prereqs and primary_affinity in affinity_prereqs:
        prereq = affinity_prereqs[primary_affinity]
        needs_all = prereq.get('needs_all', [])
        if needs_all:
            all_satisfied = True
            for tier in needs_all:
                tier_affs = tier.get('affinities', [])
                tier_min = tier.get('min_each', 0)
                for aff in tier_affs:
                    current = char.affinities.get(aff, 0)
                    if current < tier_min:
                        needed = tier_min - current
                        if affp >= needed:
                            char.affinities[aff] = char.affinities.get(aff, 0) + needed
                            affp -= needed
                        else:
                            char.affinities[aff] = char.affinities.get(aff, 0) + affp
                            affp = 0
            for tier in needs_all:
                tier_affs = tier.get('affinities', [])
                tier_min = tier.get('min_each', 0)
                for aff in tier_affs:
                    if char.affinities.get(aff, 0) < tier_min:
                        all_satisfied = False
            if not all_satisfied:
                char.affinity_points = affp
                return
        else:
            needs = prereq.get('needs', {})
            min_each = prereq.get('min_each', 0)
            affinities_needed = needs.get('all_of', []) or needs.get('any_of', [])
            all_satisfied = True
            for aff in affinities_needed:
                current = char.affinities.get(aff, 0)
                if current < min_each:
                    needed = min_each - current
                    if affp >= needed:
                        char.affinities[aff] = char.affinities.get(aff, 0) + needed
                        affp -= needed
                    else:
                        char.affinities[aff] = char.affinities.get(aff, 0) + affp
                        affp = 0
            for aff in affinities_needed:
                if char.affinities.get(aff, 0) < min_each:
                    all_satisfied = False
            if not all_satisfied:
                char.affinity_points = affp
                return
    if primary_affinity:
        char.affinities[primary_affinity] = char.affinities.get(primary_affinity, 0) + affp
    else:
        pref_order = ['Fire', 'Earth', 'Water', 'Air', 'Radiant', 'Necrotic', 'Psychic']
        while affp > 0:
            for aff in pref_order:
                if affp <= 0:
                    break
                char.affinities[aff] = char.affinities.get(aff, 0) + 1
                affp -= 1

    char.affinity_points = 0
