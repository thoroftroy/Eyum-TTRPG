import json
import os


def load_settings(settings_dir=None):
    if settings_dir is None:
        settings_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    settings = {}
    files = {
        'rules': 'rules.json',
        'weapons': 'weapons.json',
        'armor_types': 'armor_types.json',
        'paths': 'paths.json',
        'gear_tiers': 'gear_tiers.json',
        'races': 'races.json',
        'builds': 'builds.json',
        'spells': 'spells.json',
        'feats': 'feats.json',
        'generation': 'generation.json',
    }
    for key, filename in files.items():
        path = os.path.join(settings_dir, filename)
        with open(path, 'r') as f:
            settings[key] = json.load(f)
    return settings
