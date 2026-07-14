#!/usr/bin/env python3
"""Targeted Build Regenerator — regenerates only builds affected by recent changes.

Reads changes.txt from update.py, determines which builds could be affected,
and re-runs the generator for just those builds so the GUI graph is accurate.
"""

import json, os, sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')
CHANGES_PATH = os.path.join(SCRIPT_DIR, 'changes.txt')
BUILDS_PATH = os.path.join(DATA_DIR, 'builds.json')
SPELLS_PATH = os.path.join(DATA_DIR, 'spells.json')
RACES_PATH = os.path.join(DATA_DIR, 'races.json')
PATHS_PATH = os.path.join(DATA_DIR, 'paths.json')
GEN_PATH = os.path.join(DATA_DIR, 'generation.json')
LOG_PATH = os.path.join(SCRIPT_DIR, 'output', 'build_regenerator_log.txt')


def load_json(path):
    with open(path) as f:
        return json.load(f)


def find_affected_builds(changed_items, builds, spells, races, paths):
    """Determine which builds could be affected by the changed items."""
    affected = set()

    changed_affinities = set()
    changed_spell_names = set()
    changed_race_families = set()
    changed_archetypes = set()

    for item in changed_items:
        parts = item.strip().split('|')
        category = parts[0].strip() if parts else ''
        name = parts[1].strip() if len(parts) > 1 else ''

        if category == 'SPELL':
            changed_spell_names.add(name)
        elif category == 'RACE':
            if '/' in name:
                fam = name.split('/')[0]
                changed_race_families.add(fam)
            else:
                changed_race_families.add(name)
        elif category == 'ARCHETYPE':
            changed_archetypes.add(name)
        elif category == 'AFFINITY':
            changed_affinities.add(name)
        elif category == 'FEAT':
            pass  # All builds use feats, regenerate everything

    # Match builds to changes
    for build_name, build_config in builds.items():
        if not build_config.get('generate', True):
            continue

        primary_aff = build_config.get('primary_affinity', '')
        race_pick = build_config.get('race', 'auto')
        paths_cfg = build_config.get('paths', {})

        # Affinity match
        if primary_aff and primary_aff in changed_affinities:
            affected.add(build_name)
            continue

        # Race match
        if race_pick != 'auto':
            for fam in changed_race_families:
                if race_pick == fam or build_name.endswith(f' {fam}'):
                    affected.add(build_name)
                    break
            if build_name in affected:
                continue

        # Archetype match
        for path_name, arch_list in paths_cfg.items():
            for arch in arch_list:
                if arch in changed_archetypes:
                    affected.add(build_name)
                    break
            if build_name in affected:
                break

        # Spell match — any magical build whose primary affinity has changed spells
        if primary_aff and changed_spell_names:
            for sn in changed_spell_names:
                # Check if this spell is in the build's primary affinity
                for aff_list in spells.values():
                    for s in aff_list:
                        if s['name'] == sn and aff_list == spells.get(primary_aff, []):
                            affected.add(build_name)
                            break
            if build_name in affected:
                continue

        # If the build's primary affinity is in changed affinities (prereqs changed)
        if primary_aff in changed_affinities:
            affected.add(build_name)

    return affected


def run_regenerator(win=None):
    """Worker function for GUI or standalone."""
    import sys as _sys
    _sys.path.insert(0, SCRIPT_DIR)
    sink = _LogSink(win)
    quiet = '--quiet' in _sys.argv

    # Redirect print
    try:
        _builtin_print = __builtins__.print
    except:
        _builtin_print = print
    def _print(*args, **kwargs):
        msg = ' '.join(str(a) for a in args)
        tag = 'red' if ('ERROR' in msg or 'error' in msg) else ('green' if ('Done' in msg or 'OK' in msg) else 'normal')
        # Always show key status lines even in quiet mode
        is_status = any(kw in msg for kw in ('Regenerating', 'affected', 'changed', 'No builds', 'Found'))
        if quiet and tag == 'normal' and not is_status:
            return
        sink.log(msg, tag)
    import builtins
    builtins.print = _print

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if not os.path.exists(CHANGES_PATH):
        print("No changes.txt found — nothing to regenerate.")
        sink.flush(LOG_PATH)
        try:
            import builtins; builtins.print = _builtin_print
        except: pass
        return

    with open(CHANGES_PATH) as f:
        changed_items = [l.strip() for l in f if l.strip() and not l.startswith('#')]

    if not changed_items:
        print("changes.txt is empty — nothing to regenerate.")
        os.remove(CHANGES_PATH)
        sink.flush(LOG_PATH)
        try:
            import builtins; builtins.print = _builtin_print
        except: pass
        return

    print(f"Found {len(changed_items)} changed items. Determining affected builds...")

    builds = load_json(BUILDS_PATH)
    spells = load_json(SPELLS_PATH)
    races = load_json(RACES_PATH)
    paths_rules = load_json(PATHS_PATH)

    affected = find_affected_builds(changed_items, builds, spells, races, paths_rules)

    if not affected:
        print("No builds affected by these changes.")
        os.remove(CHANGES_PATH)
        sink.flush(LOG_PATH)
        try:
            import builtins; builtins.print = _builtin_print
        except: pass
        return

    print(f"Regenerating {len(affected)} affected builds: {', '.join(sorted(affected))}")

    from lib.config import load_settings
    from generator import generate_build, select_gear
    from lib.output import write_build_file, write_average, write_overall_averages, write_summary

    settings = load_settings(os.path.join(SCRIPT_DIR, 'data'))
    gen = settings.get('generation', {})

    if 'max_level' in gen:
        levels = list(range(1, gen['max_level'] + 1))
    else:
        levels = gen.get('levels', list(range(1, 201)))

    gear_tiers = settings.get('gear_tiers', [{"name": "bad_gear", "label": "Bad Gear", "gold_per_level": 1}])
    output_dir = gen.get('output_dir', os.path.join(SCRIPT_DIR, 'output'))
    max_level = max(levels)

    regenerated = []
    errors = []
    all_tier_results = []

    for tier in gear_tiers:
        tier_name = tier['name']
        tier_label = tier['label']
        tier_dir = os.path.join(output_dir, tier_name)
        os.makedirs(tier_dir, exist_ok=True)

        all_results = {}

        for build_name in sorted(affected):
            build_config = builds.get(build_name)
            if not build_config:
                continue

            try:
                if tier_name != 'no_gear':
                    gear_override = select_gear(build_config, tier_name, max_level)
                else:
                    gear_override = {'weapon': None, 'armor': 'none'}

                print(f"  {build_name} ({tier_label})...")
                results = generate_build(build_name, build_config, settings, levels,
                                        gear_override, tier_label)
                all_results[build_name] = results

                if gen.get('separate_files', True):
                    write_build_file(build_name, results, tier_dir, tier_label)

                regenerated.append(f"{build_name} ({tier_label})")
            except Exception as e:
                errors.append(f"{build_name} ({tier_label}): {e}")
                print(f"    ERROR: {e}")

        if gen.get('generate_average', True) and all_results:
            avg_path = os.path.join(tier_dir, "average.txt")
            write_average(all_results, settings, avg_path)

        all_tier_results.append((tier_name, all_results))

    # Regenerate cross-tier averages and summary
    if all_tier_results:
        overall_path = os.path.join(SCRIPT_DIR, "averages.txt")
        write_overall_averages(gear_tiers, all_tier_results, settings, overall_path)
        print(f"Updated averages.txt")

        summary_path = os.path.join(SCRIPT_DIR, "summary.txt")
        write_summary(all_tier_results, settings, summary_path, settings['builds'])
        print(f"Updated summary.txt")

    # Write changes.txt summary
    with open(CHANGES_PATH, 'w') as f:
        f.write(f"# Regenerated {ts}\n")
        f.write(f"# {len(regenerated)} build/tier combinations\n")
        for r in sorted(set(r.split(' (')[0] for r in regenerated)):
            f.write(f"REGENERATED|{r}\n")
        if errors:
            for e in errors:
                f.write(f"ERROR|{e}\n")

    print(f"\nDone. {len(regenerated)} build/tier combinations regenerated.")
    if errors:
        print(f"{len(errors)} errors (see {LOG_PATH})")

    sink.flush(LOG_PATH)

    try:
        import builtins; builtins.print = _builtin_print
    except: pass


class _LogSink:
    def __init__(self, gui=None):
        self.gui = gui
        self.lines = []
    def log(self, s='', tag='normal'):
        self.lines.append(s)
        if self.gui:
            self.gui.log(s, tag)
    def flush(self, path):
        with open(path, 'w') as f:
            f.write('\n'.join(self.lines) + '\n')


def main():
    if '--no-gui' in sys.argv:
        run_regenerator(None)
    else:
        try:
            from console_gui import run_with_gui
            run_with_gui("Eyum Build Regenerator", run_regenerator, auto_close=True, close_delay=1)
        except ImportError:
            run_regenerator(None)


if __name__ == '__main__':
    main()
