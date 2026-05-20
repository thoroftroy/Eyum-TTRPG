from .effects import apply_feat_effects


def check_feat_prereq(char, prereq, settings):
    if not prereq:
        return True, None
    if 'level' in prereq and char.level < prereq['level']:
        return False, 'Requires Level ' + str(prereq['level'])
    if 'stat' in prereq:
        for stat_name, min_val in prereq['stat'].items():
            if getattr(char, stat_name, 0) < min_val:
                stat_upper = stat_name.upper()
                return False, 'Requires ' + stat_upper + ' ' + str(min_val)
    if 'path' in prereq:
        for arch_name, min_level in prereq['path'].items():
            found = False
            for (path, arch), lvl in char.archetype_levels.items():
                if arch == arch_name and lvl >= min_level:
                    found = True
                    break
            if not found:
                return False, 'Requires ' + arch_name + ' Lvl ' + str(min_level)
    if 'feat' in prereq:
        if prereq['feat'] not in char.feats_taken:
            return False, 'Requires feat: ' + prereq['feat']
    return True, None


def select_feats(char, target_level, settings):
    feats_data = settings.get('feats', {})
    feat_opportunities = target_level // 3
    feat_count = int(feat_opportunities * (1 + char.feat_per_feat))

    feat_count = min(feat_count, 500)

    taken_count = 0
    for milestone in range(3, min(target_level, 1000) + 1, 3):
        if taken_count >= feat_count:
            break

        feats_this_milestone = 1 + char.feat_per_feat
        for _ in range(feats_this_milestone):
            if taken_count >= feat_count:
                break

            old_level = char.level
            char.level = milestone

            eligible = []
            for feat_name, feat_data in feats_data.items():
                repeatable = feat_data.get('repeatable', False)
                if not repeatable and feat_name in char.feats_taken:
                    continue
                if isinstance(repeatable, int) and not isinstance(repeatable, bool):
                    times_taken = sum(1 for f in char.feats_taken if f == feat_name)
                    if times_taken >= repeatable:
                        continue
                ok, _ = check_feat_prereq(char, feat_data.get('prereq', {}), settings)
                if ok:
                    eligible.append((feat_name, feat_data))

            all_candidates = []
            for feat_name, feat_data in feats_data.items():
                repeatable = feat_data.get('repeatable', False)
                if not repeatable and feat_name in char.feats_taken:
                    continue
                if isinstance(repeatable, int) and not isinstance(repeatable, bool):
                    times_taken = sum(1 for f in char.feats_taken if f == feat_name)
                    if times_taken >= repeatable:
                        continue
                all_candidates.append((feat_name, feat_data))
            best_wanted = max(all_candidates, key=lambda x: x[1].get('value', 0)) if all_candidates else None

            if eligible:
                best = max(eligible, key=lambda x: x[1].get('value', 0))
                best_value = best[1].get('value', 0)
                if best_value >= 2:
                    char.feats_taken.append(best[0])
                    apply_feat_effects(char, best[1].get('effects', {}))
                    if best_wanted and best_wanted[0] != best[0] and best_wanted[1].get('value', 0) > best_value:
                        _, reason = check_feat_prereq(char, best_wanted[1].get('prereq', {}), settings)
                        note = "    (Wanted " + best_wanted[0] + " but did not meet prerequisite: " + reason + ")"
                        if note not in char.feat_fallback_notes:
                            char.feat_fallback_notes.append(note)
                else:
                    char.stat_points += 2
            else:
                char.stat_points += 2
                if best_wanted and best_wanted[1].get('value', 0) >= 2:
                    _, reason = check_feat_prereq(char, best_wanted[1].get('prereq', {}), settings)
                    if reason:
                        note = "    (No eligible feats worth taking. Best unavailable: " + best_wanted[0] + " - " + reason + ")"
                        if note not in char.feat_fallback_notes:
                            char.feat_fallback_notes.append(note)
            taken_count += 1
            char.level = old_level

    if char.vit_per_level_bonus:
        char.flat_vit += char.vit_per_level_bonus * target_level
    if char.hp_per_level_bonus:
        char.flat_hp += char.hp_per_level_bonus * target_level
    if char.mana_per_level_bonus:
        char.flat_mana += char.mana_per_level_bonus * target_level

    char.feats = feat_count
