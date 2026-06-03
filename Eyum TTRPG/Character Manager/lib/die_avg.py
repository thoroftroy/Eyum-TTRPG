import re

_DIE_CACHE = {}

def die_average(die_str, default=0):
    """Compute average of a die expression like '1d6', '3d8', '20d20' at runtime."""
    if not die_str or die_str == '-':
        return default
    if die_str in _DIE_CACHE:
        return _DIE_CACHE[die_str]
    m = re.match(r'^(\d+)d(\d+)$', die_str)
    if m:
        count = int(m.group(1))
        sides = int(m.group(2))
        avg = count * (sides / 2.0 + 0.5)
    else:
        try:
            avg = float(die_str)
        except ValueError:
            avg = default
    _DIE_CACHE[die_str] = avg
    return avg
