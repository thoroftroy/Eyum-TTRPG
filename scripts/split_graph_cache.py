#!/usr/bin/env python3
"""Split the massive graph_cache.json into per-tier files for the web app."""
import json, os, sys

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'dist/graph_cache.json'
    out_dir = sys.argv[2] if len(sys.argv) > 2 else 'dist/graph_data'

    with open(src) as f:
        data = json.load(f)

    os.makedirs(out_dir, exist_ok=True)

    tiers_meta = {}
    for tier_name, builds in data.items():
        # Compact: remove redundant stat keys by storing only the 14 displayed stats per level
        keep_stats = {
            'Vitality','Health','Mana','AC','Feats','Spells','To Hit',
            'Dmg/Turn','Dmg/5R','Dmg/10R',
            'STR','DEX','CON','WIS','INT','CHA',
            'ManaCost','SpellName','AP','BAp','Race'
        }
        compact = {}
        avg = builds.pop('__average__', None) if isinstance(builds, dict) else None

        for bname, bdata in builds.items():
            cdata = {}
            for lvl_str, ldata in bdata.items():
                cdata[lvl_str] = {k: v for k, v in ldata.items() if k in keep_stats}
            compact[bname] = cdata

        if avg:
            cavg = {}
            for lvl_str, ldata in avg.items():
                cavg[lvl_str] = {k: v for k, v in ldata.items() if k in keep_stats}
            compact['__average__'] = cavg

        out_path = os.path.join(out_dir, f'{tier_name}.json')
        with open(out_path, 'w') as f:
            json.dump(compact, f, separators=(',', ':'))

        sz = os.path.getsize(out_path)
        tiers_meta[tier_name] = {
            'file': f'{tier_name}.json',
            'builds': sorted([k for k in compact if k != '__average__']),
            'has_average': '__average__' in compact,
            'size_kb': round(sz / 1024, 1),
        }

    meta_path = os.path.join(out_dir, '_tiers.json')
    with open(meta_path, 'w') as f:
        json.dump(tiers_meta, f, indent=2)
    print(f'Split into {len(tiers_meta)} tier files in {out_dir}/ (tiers.json + {len(tiers_meta)} data files)')

    # Print sizes
    total = sum(os.path.getsize(os.path.join(out_dir, f)) for f in os.listdir(out_dir))
    print(f'Total size: {total / 1024 / 1024:.1f} MB (vs original {os.path.getsize(src) / 1024 / 1024:.1f} MB)')

if __name__ == '__main__':
    main()
