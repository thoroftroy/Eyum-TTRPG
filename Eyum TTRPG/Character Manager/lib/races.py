def select_best_race(build_config, races_data):
    pickup = build_config.get('race', 'auto')
    if pickup != 'auto':
        build_name = build_config.get('_build_name', '')
        # Priority 1: build name has explicit family+subrace (e.g., "Race: Bugfolk Twigwrought")
        if build_name and build_name.startswith('Race: '):
            parts = build_name[6:].split(' ', 1)
            if len(parts) == 2:
                fam, sub = parts
                if fam in races_data and sub in races_data[fam].get('subraces', {}):
                    return fam, sub
        # Priority 2: exact subrace name or family+subrace
        for family_name, family in races_data.items():
            for subrace_name, data in family.get('subraces', {}).items():
                if subrace_name == pickup or f"{family_name} {subrace_name}" == pickup:
                    return family_name, subrace_name
        # Priority 3: family name only — pick first subrace
        for family_name, family in races_data.items():
            if family_name == pickup and family.get('subraces'):
                first_sub = list(family['subraces'].keys())[0]
                return family_name, first_sub
        return None, None

    stat_priority = build_config.get('stat_priority', ['str', 'dex', 'con', 'wis', 'int', 'cha'])
    base_affinities = build_config.get('starting_affinities', {})
    is_magical = build_config.get('has_magical', False)
    primary_affinity = build_config.get('primary_affinity')
    if not primary_affinity and is_magical and base_affinities:
        sorted_affs = sorted(base_affinities.items(), key=lambda x: x[1], reverse=True)
        for aff, val in sorted_affs:
            if aff != 'Generic':
                primary_affinity = aff
                break

    prereq_affinities = set()
    if primary_affinity:
        try:
            import json, os
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            rules_path = os.path.join(script_dir, 'data', 'rules.json')
            with open(rules_path) as f:
                rules = json.load(f)
            prereqs = rules.get('affinity_prerequisites', {}).get(primary_affinity)
            if prereqs:
                needs_all = prereqs.get('needs_all', [])
                if needs_all:
                    for tier in needs_all:
                        prereq_affinities.update(tier.get('affinities', []))
                else:
                    needs = prereqs.get('needs', {})
                    prereq_affinities.update(needs.get('all_of', []) or needs.get('any_of', []))
        except Exception:
            pass

    worst = build_config.get('worst', False)
    stat_weights = [3, 2, 1.5, 1, 0.5, 0.25]

    def classify_race(data):
        affs = data.get('affinity_bonuses', {})
        # Tier -1: race unlocks the primary affinity for free at base (no prereqs needed)
        unlocks = data.get('unlocks_affinities', [])
        if is_magical and primary_affinity and primary_affinity in unlocks:
            return -1
        # Check prereq affinities for unlock too
        if is_magical and prereq_affinities:
            for pa in prereq_affinities:
                if pa in unlocks:
                    return -1
        # Tier 0: race has positive primary affinity
        if is_magical and primary_affinity:
            if affs.get(primary_affinity, 0) > 0:
                return 0
            if affs.get(primary_affinity, 0) < 0:
                return 99
        if is_magical and prereq_affinities:
            has_pos = any(affs.get(a, 0) > 0 for a in prereq_affinities)
            has_neg = any(affs.get(a, 0) < 0 for a in prereq_affinities)
            if has_pos and not has_neg:
                return 1
            if has_pos:
                return 2
        if is_magical and primary_affinity and affs.get(primary_affinity, 0) == 0:
            return 3
        return 4

    def stat_score(data):
        s = 0
        bonuses = data.get('stat_bonuses', {})
        for i, stat in enumerate(stat_priority):
            if i >= len(stat_weights):
                break
            s += bonuses.get(stat, 0) * stat_weights[i]
        return s

    candidates = []
    for family_name, family in races_data.items():
        for subrace_name, data in family.get('subraces', {}).items():
            if data.get('evolution_only'):
                continue
            if is_magical:
                tier = classify_race(data)
            else:
                tier = 0
            s = stat_score(data)
            candidates.append((tier, -s if worst else s, family_name, subrace_name))

    candidates.sort()
    if not candidates:
        return None, None

    best_tier = candidates[0][0]
    same_tier = [c for c in candidates if c[0] == best_tier]
    best = max(same_tier, key=lambda x: x[1]) if not worst else min(same_tier, key=lambda x: x[1])
    return best[2], best[3]


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
