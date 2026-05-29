def select_best_race(build_config, races_data):
    pickup = build_config.get('race', 'auto')
    if pickup != 'auto':
        for family_name, family in races_data.items():
            for subrace_name, data in family.get('subraces', {}).items():
                if subrace_name == pickup or family_name == pickup:
                    return family_name, subrace_name
        return None, None

    stat_priority = build_config.get('stat_priority', ['str', 'dex', 'con', 'wis', 'int', 'cha'])
    base_affinities = build_config.get('starting_affinities', {})
    is_magical = build_config.get('has_magical', False)
    primary_affinity = None
    if is_magical and base_affinities:
        sorted_affs = sorted(base_affinities.items(), key=lambda x: x[1], reverse=True)
        for aff, val in sorted_affs:
            if aff != 'Generic':
                primary_affinity = aff
                break

    best_score = -9999
    best_family = None
    best_subrace = None

    stat_weights = [10, 4, 2, 1, 0.5, 0.25]

    for family_name, family in races_data.items():
        for subrace_name, data in family.get('subraces', {}).items():
            if data.get('evolution_only'):
                continue

            score = 0
            bonuses = data.get('stat_bonuses', {})
            for i, stat in enumerate(stat_priority):
                if i >= len(stat_weights):
                    break
                bonus = bonuses.get(stat, 0)
                score += bonus * stat_weights[i]

            affinity_bonuses = data.get('affinity_bonuses', {})
            for aff, val in affinity_bonuses.items():
                if val > 0:
                    if aff == 'Generic':
                        score += 1
                    elif is_magical and aff == primary_affinity:
                        score += 10
                    elif aff in base_affinities:
                        score += 5
                    else:
                        score += 1
                elif val < 0:
                    if is_magical and aff == primary_affinity:
                        score -= 15
                    elif aff in base_affinities:
                        score -= 5
                    else:
                        score -= 1

            if score > best_score:
                best_score = score
                best_family = family_name
                best_subrace = subrace_name

    return best_family, best_subrace


def build_racial_archetype(race_data, race_family, subrace_name=''):
    try:
        from data.bloodline_data import BLOODLINE_DATA
        family_data = BLOODLINE_DATA.get(race_family, {})
        subrace_data = family_data.get(subrace_name, {})
        if subrace_data:
            return dict(subrace_data)
    except (ImportError, KeyError):
        pass

    # Fallback: simplified generic formula for subraces without handbook data
    archetype = {}
    for tier_num in range(1, 11):
        effects = {}
        effects['stat_points'] = tier_num // 2 + 1
        effects['affinity_points'] = tier_num
        if tier_num == 1:
            effects['tier1_racial'] = True
            effects['skill_points'] = 2
        elif tier_num == 3:
            effects['skill_points'] = 2
        elif tier_num == 5:
            effects['ac_bonus'] = 1
        elif tier_num == 7:
            effects['speed'] = 5
        elif tier_num == 10:
            effects['ac_bonus'] = 1
            effects['stat_points'] = 5
            effects['flat_vit'] = 20
            effects['flat_hp'] = 10
        archetype[str(tier_num)] = effects
    return archetype


def build_race_data(settings):
    races = settings.get('races', {})
    paths_rules = settings.get('paths', {})
    racial_path = paths_rules.get('Racial', {})
    if 'archetypes' not in racial_path:
        racial_path['archetypes'] = {}
    for family_name, family in races.items():
        for subrace_name, data in family.get('subraces', {}).items():
            arch_name = f"{family_name} {subrace_name}"
            if arch_name not in racial_path['archetypes']:
                racial_path['archetypes'][arch_name] = build_racial_archetype(data, family_name, subrace_name)
    return races
