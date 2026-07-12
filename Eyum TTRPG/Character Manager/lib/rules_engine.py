"""
Eyum TTRPG - Comprehensive Rules Engine
Implements all handbook rules for: injuries, conditions, resting, exhaustion,
combat modifiers (flanking/cover/high ground), damage types, resistance systems,
karma/alignment, weapon/armor proficiency, and proper crit/AoE damage modeling.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math


# ---- Damage Type Groupings (2.2 Damage Types) ----
DAMAGE_GROUPS = {
    "Physical": ["Slashing", "Bludgeoning", "Piercing"],
    "Mixed": ["Magical Slashing", "Magical Bludgeoning", "Magical Piercing"],
    "Elemental": [
        "Fire/Heat", "Earth", "Water", "Air", "Radiant", "Necrotic",
        "Lightning", "Steam", "Magma", "Ice/Cold", "Dust", "Mud",
        "Nova", "Solar", "Hallowed", "Starlight", "Cursed", "Ash",
        "Blight", "Poison", "Toxin", "Bloodfire", "Tremor", "Deluge",
        "Shatter", "Sorrow", "Chaos", "Infernal", "Metal", "Torrent",
        "Thunder", "Mirage", "Vacuum", "Warp", "Storm", "Frostfire",
        "Glacial", "Void", "Obsidian", "Quake", "Miasma", "Gel",
        "Corruption", "Atomic", "Quantum", "Eldritch"
    ],
    "Special": ["Psychic", "Force", "True"]
}

def damage_group(dmg_type: str) -> str:
    for group, types in DAMAGE_GROUPS.items():
        if dmg_type in types:
            return group
    return "Physical"

NOTATION_MAP = {
    "Fire/Heat": "Fire",
    "Fire": "Fire/Heat",
    "Ice/Cold": "Ice/Cold",
}


# ---- Resistance Multipliers (2.2 Damage Types) ----
RESISTANCE_MULTIPLIERS = {
    "Immunity": 0,
    "Greater Resistance": 1/3,
    "Resistance": 1/2,
    "Lesser Resistance": 3/4,
    "Normal": 1,
    "Lesser Weakness": 1.5,
    "Weakness": 2,
    "Greater Weakness": 3,
}


# ---- Injury Severity Thresholds (1.3 Player Stats) ----
INJURY_SEVERITY = [
    ("Minor", 0.10, 0.25),
    ("Moderate", 0.25, 0.50),
    ("Severe", 0.50, 1.00),
    ("Extreme", 0.75, float("inf")),
]

INJURY_DC = {
    "Minor": 10,
    "Moderate": 15,
    "Severe": 20,
    "Extreme": 25,
}

# Overkill scaling (1.3 Player Stats)
OVERKILL_EFFECTS = {
    1: {"disadvantage": True},
    2: {"dc_penalty": 5},
    3: {"dc_penalty": 15},
    4: {"dc_penalty": 25},
    5: {"auto_fail": True},
}

# Injury mapping by damage type (2.3 Injuries)
# Format: (severity) -> (condition, turns)
INJURY_MAP = {
    "Slashing":           {"Minor": ("Bleeding", 1), "Moderate": ("Bleeding", 2),
                           "Severe": ("Bleeding", 3), "Extreme": ("Bleeding", 4)},
    "Magical Slashing":   {"Minor": ("Bleeding", 2), "Moderate": ("Bleeding", 4),
                           "Severe": ("Bleeding", 6), "Extreme": ("Bleeding", 8)},
    "Bludgeoning":        {"Minor": ("Suffocating", 1), "Moderate": ("Suffocating", 2),
                           "Severe": ("Suffocating", 3), "Extreme": ("Suffocating", 4)},
    "Magical Bludgeoning":{"Minor": ("Suffocating", 2), "Moderate": ("Suffocating", 4),
                           "Severe": ("Suffocating", 6), "Extreme": ("Suffocating", 8)},
    "Piercing":           {"Minor": ("Bleeding", 1), "Moderate": ("Bleeding", 2),
                           "Severe": ("Bleeding", 3), "Extreme": ("Bleeding", 4)},
    "Magical Piercing":   {"Minor": ("Bleeding", 2), "Moderate": ("Bleeding", 4),
                           "Severe": ("Bleeding", 6), "Extreme": ("Bleeding", 8)},
    "Fire/Heat":          {"Minor": ("Burned", 1), "Moderate": ("Burned", 2),
                           "Severe": ("Burned", 3), "Extreme": ("Burned", 4)},
    "Earth":              {"Minor": ("Prone", 1), "Moderate": ("Prone,Stunned", 1),
                           "Severe": ("Prone,Stunned", 3), "Extreme": ("Prone,Stunned", 4)},
    "Water":              {"Minor": ("Suffocating", 1), "Moderate": ("Suffocating", 2),
                           "Severe": ("Suffocating", 3), "Extreme": ("Suffocating", 4)},
    "Air":                {"Minor": ("Suffocating", 1), "Moderate": ("Suffocating", 2),
                           "Severe": ("Suffocating", 3), "Extreme": ("Suffocating", 4)},
    "Radiant":            {"Minor": ("Blinded", 1), "Moderate": ("Blinded", 2),
                           "Severe": ("Blinded", 3), "Extreme": ("Blinded", 4)},
    "Necrotic":           {"Minor": ("Necrosis", 1), "Moderate": ("Necrosis", 2),
                           "Severe": ("Necrosis", 3), "Extreme": ("Necrosis", 4)},
    "Psychic":            {"Minor": ("Demoralized", 1), "Moderate": ("Demoralized", 2),
                           "Severe": ("Demoralized", 3), "Extreme": ("Demoralized", 4)},
    "Force":              {"Minor": ("Hurting", 3), "Moderate": ("Hurting", 3),
                           "Severe": ("Hurting", 4), "Extreme": ("Hurting", 5)},
    "True":               {"Minor": ("Suffocating,Deafened", 1), "Moderate": ("Suffocating,Deafened", 2),
                           "Severe": ("Unconscious,Suffocating", 1), "Extreme": ("Unconscious,Suffocating", 2)},
    "Lightning":          {"Minor": ("Shocked", 1), "Moderate": ("Shocked", 2),
                           "Severe": ("Shocked", 3), "Extreme": ("Shocked", 4)},
    "Infernal":           {"Minor": ("Burned", 5), "Moderate": ("Burned", 8),
                           "Severe": ("Burned", 10), "Extreme": ("Burned", 15)},
    "Ice/Cold":           {"Minor": ("Frozen", 1), "Moderate": ("Frozen", 2),
                           "Severe": ("Frozen,Frostbitten", 3), "Extreme": ("Frozen,Frostbitten", 4)},
    "Magma":              {"Minor": ("On Fire", 3), "Moderate": ("On Fire", 4),
                           "Severe": ("On Fire,Blinded", 5), "Extreme": ("On Fire,Blinded", 6)},
    "Steam":              {"Minor": ("Burned", 2), "Moderate": ("Burned", 3),
                           "Severe": ("Burned", 4), "Extreme": ("Burned", 5)},
    "Nova":               {"Minor": ("Blinded,Burned", 2), "Moderate": ("Blinded,Burned", 3),
                           "Severe": ("Blinded,Burned", 4), "Extreme": ("Blinded,Burned", 5)},
    "Solar":              {"Minor": ("Blinded,Burned", 2), "Moderate": ("Blinded,Burned", 3),
                           "Severe": ("Blinded,Burned", 4), "Extreme": ("Blinded,Burned", 5)},
    "Poison":             {"Minor": ("Poisoned", 1), "Moderate": ("Poisoned", 2),
                           "Severe": ("Poisoned", 3), "Extreme": ("Poisoned", 4)},
    "Toxin":              {"Minor": ("Poisoned", 1), "Moderate": ("Poisoned", 2),
                           "Severe": ("Poisoned", 3), "Extreme": ("Poisoned", 4)},
    "Thunder":            {"Minor": ("Stunned,Deafened", 1), "Moderate": ("Stunned,Deafened", 2),
                           "Severe": ("Stunned,Deafened", 3), "Extreme": ("Stunned,Deafened", 4)},
    "Obsidian":           {"Minor": ("Slow Death", 0), "Moderate": ("Slow Death", 0),
                           "Severe": ("Slow Death", 0), "Extreme": ("Slow Death", 0)},
    "Atomic":             {"Minor": ("Radiation", 1), "Moderate": ("Radiation", 2),
                           "Severe": ("Radiation", 3), "Extreme": ("Radiation", 4)},
    "Eldritch":           {"Minor": ("Eldritch Curse", 1), "Moderate": ("Eldritch Curse", 3),
                           "Severe": ("Eldritch Curse", 7), "Extreme": ("Eldritch Curse", 12)},
}


# ---- Conditions Database (2.4 Conditions) ----
@dataclass
class Condition:
    name: str
    category: str  # Environmental, Physical, Mental, Magical
    default_dc: int = 0
    default_duration: int = 0
    damage_per_turn: float = 0
    damage_type: str = ""
    stackable: bool = False
    affects_ac: int = 0
    affects_saves: int = 0
    affects_attacks: int = 0
    affects_speed_pct: float = 1.0
    description: str = ""

# Key conditions with mechanical effects
CONDITIONS = {
    "Bleeding": {
        "category": "Physical", "damage_per_turn": 2.5, "damage_type": "Slashing",
        "stackable": True, "default_dc": 10, "removal": "DC 10 medicine check or healing spell",
        "description": "Take 1d4 health damage per turn, each stack adds +1d4"
    },
    "Burned": {
        "category": "Physical", "damage_per_turn": 2.5, "damage_type": "Fire/Heat",
        "default_dc": 10, "removal": "DC 10 medicine check or healing spell",
        "description": "Take 1d4 fire damage per turn"
    },
    "Suffocating": {
        "category": "Environmental", "damage_per_turn": 3.5, "damage_type": "Vacuum",
        "affects_attacks": -1, "affects_saves": -1, "default_dc": 10,
        "removal": "DC 10 Constitution throw",
        "description": "1d6 Vacuum dmg/turn, disadvantage on attacks/saves/skills, Muted"
    },
    "Necrosis": {
        "category": "Physical", "damage_per_turn": 4.5, "damage_type": "Necrotic",
        "stackable": True, "default_dc": 13,
        "removal": "DC 13 medicine check (remove one stack per success)",
        "description": "1d8 Necrotic dmg/turn, disadvantage on saves, each stack +1d8"
    },
    "On Fire": {
        "category": "Environmental", "damage_per_turn": 3.5, "damage_type": "Fire/Heat",
        "default_duration": 3, "removal": "Take water damage or wait 3 turns",
        "description": "1d6 Fire dmg/turn, gain Burned when ends"
    },
    "Prone": {
        "category": "Environmental", "affects_attacks": -1, "affects_saves": -9999,
        "default_dc": 0, "removal": "Spend half movement to stand",
        "description": "Enemies have advantage, you have disadvantage on all rolls"
    },
    "Stunned": {
        "category": "Physical", "default_duration": 1, "affects_speed_pct": 0,
        "removal": "Wait duration",
        "description": "Cannot take actions"
    },
    "Blinded": {
        "category": "Physical", "default_duration": 3, "affects_attacks": -3,
        "removal": "Wait 3 turns",
        "description": "Triple disadvantage on attacks, auto-fail Search/Spot"
    },
    "Hurting": {
        "category": "Environmental", "damage_per_turn": 1, "damage_type": "Force",
        "stackable": True, "default_duration": 2,
        "removal": "Wait 2 turns",
        "description": "Take Force damage per turn, stacks"
    },
    "Shocked": {
        "category": "Physical", "damage_per_turn": 2.5, "damage_type": "Lightning",
        "default_duration": 2, "removal": "Wait 2 turns"
    },
    "Frozen": {
        "category": "Environmental", "damage_per_turn": 2.5, "damage_type": "Ice/Cold",
        "stackable": True, "affects_speed_pct": 0.5,
        "default_duration": 2, "removal": "Take fire damage or wait 2 turns",
        "description": "Speed and BAp halved, stacks deal 1d4 Ice/Cold damage"
    },
    "Frostbitten": {
        "category": "Physical", "damage_per_turn": 2.5, "damage_type": "Ice/Cold",
        "stackable": True, "affects_speed_pct": 0.5,
        "default_dc": 10, "removal": "DC 10 medicine check or healing spell"
    },
    "Frostburned": {
        "category": "Environmental", "damage_per_turn": 7.0, "damage_type": "Frostfire",
        "stackable": True, "affects_speed_pct": 0.5,
        "default_duration": 3, "removal": "Wait 3 turns",
        "description": "2d6 Frostfire dmg/turn, speed -10, BAp -1, no reactions"
    },
    "Poisoned": {
        "category": "Physical", "damage_per_turn": 7.0, "damage_type": "Poison",
        "default_duration": 3, "removal": "DC 15 Con save"
    },
    "Demoralized": {
        "category": "Mental", "affects_attacks": -1, "affects_saves": -1,
        "default_duration": 2, "removal": "Wait 2 turns"
    },
    "Despair": {
        "category": "Mental", "affects_attacks": -2, "affects_saves": -2,
        "default_duration": 2, "removal": "Wait 2 turns"
    },
    "Enraged": {
        "category": "Mental", "affects_attacks": -1, "default_duration": 2,
        "removal": "Wait 2 turns"
    },
    "Deafened": {
        "category": "Physical", "affects_attacks": -1, "default_duration": 3,
        "removal": "Wait 3 turns",
        "description": "Disadvantage on attacks, auto-fail sound-based checks"
    },
    "Unconscious": {
        "category": "Environmental", "affects_speed_pct": 0, "default_dc": 15,
        "removal": "DC 15 Wis save",
        "description": "Cannot act, all damage goes to HP"
    },
    "Paralyzed": {
        "category": "Physical", "affects_speed_pct": 0, "default_duration": 3,
        "removal": "Wait 3 turns",
        "description": "Movement 0, cannot take Actions"
    },
    "Petrified": {
        "category": "Physical", "affects_speed_pct": 0, "default_duration": 5,
        "removal": "Wait 5 turns",
        "description": "Cannot do anything, turn skipped"
    },
    "Slowed": {
        "category": "Magical", "affects_speed_pct": 0.5, "default_duration": 2,
        "removal": "Wait duration"
    },
    "Pierced": {
        "category": "Physical", "affects_ac": -3, "default_dc": 10,
        "removal": "DC 10 medicine check or healing spell",
        "description": "-3 AC"
    },
    "Withered": {
        "category": "Physical", "damage_per_turn": 7.5, "damage_type": "Blight",
        "default_duration": 2, "removal": "DC 20 medicine check"
    },
    "Hellfire": {
        "category": "Physical", "damage_per_turn": 4.5, "damage_type": "Infernal",
        "default_dc": 15, "removal": "DC 15 medicine check"
    },
    "Radiation": {
        "category": "Physical", "damage_per_turn": 3.5, "damage_type": "Atomic",
        "stackable": True, "default_duration": 3, "removal": "Wait 3 turns"
    },
    "Plagued": {
        "category": "Physical", "damage_per_turn": 6.0, "damage_type": "Miasma",
        "stackable": True, "default_dc": 50,
        "removal": "DC 50 medicine check (or Nat 20)",
        "description": "Disadvantage on skills/saves/attacks, half damage dealt, half speed, half Vit"
    },
    "Storm Shocked": {
        "category": "Environmental", "damage_per_turn": 2.5, "damage_type": "Lightning",
        "removal": "Ends when Soaked condition does"
    },
    "Eldritch Curse": {
        "category": "Magical", "damage_per_turn": 0, "damage_type": "Eldritch",
        "affects_attacks": -1, "affects_saves": -1, "stackable": True
    },
    "Cursed": {
        "category": "Magical", "default_dc": 15,
        "description": "Various negative effects"
    },
    "Purged": {
        "category": "Magical", "default_duration": 2
    },
    "Corrupt": {
        "category": "Physical", "damage_per_turn": 2.5, "damage_type": "Corruption",
        "default_dc": 20, "removal": "DC 20 medicine check"
    },
    "Diseased": {
        "category": "Physical", "damage_per_turn": 3.5, "damage_type": "Blight",
        "default_dc": 10, "removal": "DC 10 medicine check or healing spell"
    },
    "Soaked": {
        "category": "Environmental", "default_duration": 10,
        "removal": "Take fire damage or wait 10 turns",
        "description": "Double Lightning/Ice/Glacial damage, half Fire damage"
    },
    "Threatened": {
        "category": "Environmental",
        "description": "Ranged attacks and ranged spell attacks have disadvantage"
    },
    "Overcrowded": {
        "category": "Environmental", "stackable": True,
        "affects_attacks": -2, "affects_ac": -1, "affects_saves": -1,
        "description": "Stacks per enemy beyond 2 in melee range"
    },
    "Vibrating": {
        "category": "Physical", "damage_per_turn": 1.0, "damage_type": "Quantum",
        "stackable": True, "default_duration": 3, "removal": "Wait 3 turns"
    },
    "Gelled": {
        "category": "Physical", "stackable": True,
        "affects_speed_pct": 0.5, "removal": "Take fire or water damage",
        "description": "Movement/AP/BAp/Rp halved, double Fire damage"
    },
}

# Conditions that stack
STACKABLE_CONDITIONS = {
    "Bleeding": True,
    "Necrosis": True,
    "Frostbitten": True,
    "Frozen": True,
    "Frostburned": True,
    "Hurting": True,
    "Overcrowded": True,
    "Radiation": True,
    "Plagued": True,
    "Eldritch Curse": True,
    "Vibrating": True,
    "Gelled": True,
    "On Fire": False,
    "Burned": False,
    "Stunned": False,
}


# ---- Exhaustion Levels (1.3 Player Stats) ----
EXHAUSTION_EFFECTS = {
    1: {"ability_disadvantage": True},
    2: {"speed_halved": True},
    3: {"attack_disadvantage": True, "save_disadvantage": True},
    4: {"hp_vit_max_halved": True},
    5: {"speed_5ft": True},
    6: {"death": True},
}


# ---- Resting Rules (1.3 Player Stats) ----
REST_RULES = {
    "short_rest": {
        "duration": "30 minutes",
        "vit_restore": 1.0,       # full
        "mana_restore": 0.5,      # 50%
        "hp_restore": 0,          # none
        "with_injury_vit": 0.5,
        "with_injury_mana": 0.5,
        "class_features": True,
    },
    "long_rest": {
        "duration": "8 hours",
        "vit_restore": 1.0,
        "mana_restore": 1.0,
        "hp_restore": 1.0,
        "exhaustion_remove": 1,
        "with_injury_vit": 0.75,
        "with_injury_mana": 0.75,
        "with_injury_hp": 0.50,
    },
}


# ---- Cover Rules (1.6 Other Rules) ----
COVER_BONUSES = {
    "Half Cover": {"ac": 2, "dex_save_advantage": True},
    "Three-Quarters": {"ac": 5, "dex_save_advantage": True},
    "Total Cover": {"untargetable": True},
}


# ---- Vision Types (1.6 Other Rules) ----
VISION_RANGES = {
    "Normal Vision": 15000,
    "Low-Light Vision": 5000,
    "Darkvision": 60,
    "True Sight": 30,
    "Heat Sense": 30,
    "Mana Sense": 60,
    "Affinity Sense": 60,
}


# ---- Weapon Types (2.5 Weapons, Armors, and Tools) ----
WEAPON_TYPES = [
    "Unarmed", "Light", "Finesse", "Thrown", "Versatile",
    "Two-Handed", "Heavy", "Reach", "Martial", "Hooking",
    "Ranged", "Loading", "Magical", "Restraining", "Special",
]

# Armor proficiency ordering (must take in sequence)
ARMOR_PROFICIENCY_ORDER = ["Light", "Medium", "Heavy"]

# Armor type expertise bonus
ARMOR_EXPERTISE_BONUS = {"Light": 1, "Medium": 2, "Heavy": 4}

# Max Dex bonus per armor type (base / expert / dodge master)
ARMOR_MAX_DEX = {
    "No Armor": (4, 4, 7),
    "Light": (5, 7, 7),
    "Medium": (4, 6, 7),
    "Heavy": (3, 5, 7),
}


# ---- Karma / Alignment (3.2 Character Information) ----
ALIGNMENT_THRESHOLDS = {
    "Evil": (-500, -250),
    "Neutral": (-249, 249),
    "Good": (250, 500),
}

KARMA_CHANGES = {
    "kill_nonsentient": -1,
    "murder_good": -5,
    "murder_neutral": -2,
    "murder_evil": 5,
    "steal": -3,
    "lie": -1,
}


# ---- Combat Modifiers ----
def get_flanking_bonus():
    """+1 to attack rolls against flanked enemy, enemy has disadvantage on saves."""
    return {"attack_bonus": 1, "enemy_save_disadvantage": True}


def get_high_ground():
    """Advantage on attacks against lower creatures, lower have disadvantage."""
    return {"attack_advantage": True, "enemy_attack_disadvantage": True}


def get_overcrowded_bonus(stacks: int = 1):
    """-2 melee attack, -1 AC, -1 saves per 2 enemies beyond first 2."""
    return {
        "melee_attack_penalty": 2 + (stacks - 1),
        "ac_penalty": 1 + (stacks - 1),
        "save_penalty": 1 + (stacks - 1),
    }


# ---- Crit Rules (1.2 Dice and Skills) ----
def calculate_crit_damage(damage_dice: str, flat_bonus: float) -> float:
    """Crit: max possible damage from dice + flat bonus. Bypasses Vitality."""
    if not damage_dice:
        return flat_bonus
    from .die_avg import die_average
    # Get max value: num_dice * (die_sides) + flat
    parts = damage_dice.split('d')
    if len(parts) == 2:
        num = int(parts[0]) if parts[0] else 1
        sides = int(parts[1])
        return num * sides + flat_bonus
    return flat_bonus


# ---- AoE Damage (1.2 Dice and Skills) ----
def split_aoe_damage(total_damage: float) -> Tuple[float, float]:
    """Half bypasses Vitality and hits HP, other half goes to Vitality."""
    hp_damage = total_damage // 2
    vit_damage = total_damage - hp_damage
    return hp_damage, vit_damage


# ---- Falling Damage (1.6 Other Rules) ----
FALL_DAMAGE_TABLE = {
    (10, 50): 2,
    (55, 100): 4,
    (105, 150): 8,
    (155, 200): 16,
    (205, 250): 32,
}

def fall_damage(distance_feet: int) -> Tuple[float, int]:
    """Returns (total_damage, hurting_stacks)"""
    if distance_feet < 5:
        return 0, 0
    if distance_feet < 10:
        return 1, 0
    dist = (distance_feet // 5) * 5  # Round down to nearest 5
    dmg_per_5 = 2
    for (lo, hi), val in FALL_DAMAGE_TABLE.items():
        if lo <= dist <= hi:
            dmg_per_5 = val
            break
    if dist > 250:
        extra = (dist - 250) // 50
        dmg_per_5 = 32 * (2 ** extra)
    total = (dist / 5) * dmg_per_5
    hurting = max(0, (dist - 15) // 5)
    return total, hurting


# ---- Ranged Attack Distances (1.6 Other Rules) ----
def range_penalty(dist: float, base_range: float) -> str:
    """Returns 'normal', 'long', or 'extreme'"""
    if dist <= base_range:
        return "normal"
    elif dist <= base_range * 2:
        return "long"
    elif dist <= base_range * 3:
        return "extreme"
    return "impossible"


# ---- Size Categories (1.6 Other Rules) ----
SIZE_CATEGORIES = ["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"]

SIZE_EFFECTS = {
    "Tiny": {"space": 2.5, "squares": 1, "stealth_adv": True, "strength_disadv": True,
             "move_through_larger": True},
    "Small": {"space": 3.5, "squares": 1, "stealth_adv": True},
    "Medium": {"space": 7, "squares": 1, "no_modifiers": True},
    "Large": {"space": 12, "squares": 2, "reach": 5, "stealth_disadv": True},
    "Huge": {"space": 17, "squares": 3, "reach": 10, "stealth_double_disadv": True,
             "grapple_adv_vs_small": True},
    "Gargantuan": {"space": 20, "squares": 4, "reach": 15, "stealth_triple_disadv": True,
                   "grapple_adv_vs_medium": True},
}
