import math
from .die_avg import die_average


# ---- Affinity Bonus Tables (from 2.1 Affinities, exact handbook values) ----

_ATTACK_STANDARD = [
    (-10, -10), (-6, -8), (-3, -5), (0, -3), (2, 0),
    (4, 1), (7, 2), (12, 3), (18, 4), (25, 5), (33, 6), (42, 7), (52, 8),
    (64, 9), (76, 10), (90, 11), (104, 12), (120, 13), (137, 14), (155, 15),
]
_ATTACK_GENERIC = [
    (0, 0), (3, 1), (4, 2), (6, 3), (8, 4),
    (12, 5), (16, 6), (20, 7), (24, 8), (30, 9), (36, 10),
    (42, 11), (48, 12), (56, 13), (64, 14), (72, 15),
]
_DC_STANDARD = [
    (-10, -8), (-5, -5), (-1, -3), (2, -1), (3, 0),
    (6, 1), (10, 2), (15, 3), (21, 4), (28, 5), (36, 6), (44, 7), (54, 8),
    (64, 9), (75, 10), (87, 11), (100, 12), (114, 13), (129, 14),
]
_DC_GENERIC = [
    (0, 0), (3, 1), (4, 2), (5, 3), (7, 4),
    (10, 5), (13, 6), (17, 7), (20, 8), (25, 9), (30, 10),
    (35, 11), (40, 12), (46, 13), (52, 14), (59, 15),
]
_DAMAGE_STANDARD = [
    (-10, -5), (-5, -3), (0, -1), (2, 0), (3, 1),
    (5, 2), (9, 3), (13, 4), (17, 5), (23, 6), (29, 7), (35, 8),
    (43, 9), (51, 10), (60, 11), (69, 12), (80, 13), (91, 14), (102, 15),
]
_DAMAGE_GENERIC = [
    (0, 0), (3, 1), (4, 2), (5, 3), (6, 4),
    (8, 5), (11, 6), (14, 7), (17, 8), (21, 9), (24, 10),
    (29, 11), (33, 12), (38, 13), (44, 14), (49, 15),
]
_ATTACK_OVERFLOW = (155, 20, 15)     # (max, step, max_bonus)
_ATTACK_GEN_OVERFLOW = (72, 10, 15)  # (max, step, max_bonus)
_DC_OVERFLOW = (129, 15, 14)         # (max, step, max_bonus)
_DC_GEN_OVERFLOW = (59, 5, 15)       # (max, step, max_bonus)
_DAMAGE_OVERFLOW = (102, 10, 15)     # (max, step, max_bonus)
_DAMAGE_GEN_OVERFLOW = (49, 5, 15)   # (max, step, max_bonus)


def _lookup(val, table, overflow):
    """Look up a bonus from a threshold table. val is the affinity value."""
    for limit, bonus in table:
        if val <= limit:
            return bonus
    max_limit, step, max_bonus = overflow
    extra = (val - max_limit) // step
    return max_bonus + max(0, extra)


def attack_bonus_standard(affinity):
    return _lookup(affinity, _ATTACK_STANDARD, _ATTACK_OVERFLOW)


def attack_bonus_generic(affinity):
    return _lookup(affinity, _ATTACK_GENERIC, _ATTACK_GEN_OVERFLOW)


def dc_bonus_standard(affinity):
    return _lookup(affinity, _DC_STANDARD, _DC_OVERFLOW)


def dc_bonus_generic(affinity):
    return _lookup(affinity, _DC_GENERIC, _DC_GEN_OVERFLOW)


def damage_bonus_standard(affinity):
    return _lookup(affinity, _DAMAGE_STANDARD, _DAMAGE_OVERFLOW)


def damage_bonus_generic(affinity):
    return _lookup(affinity, _DAMAGE_GENERIC, _DAMAGE_GEN_OVERFLOW)


def affinity_mod(affinity):
    """Backwards-compatible alias: uses the damage bonus table (Standard column)."""
    return damage_bonus_standard(affinity)


class Character:
    def __init__(self, name, stats, settings):
        self.name = name
        r = settings['rules']
        base = r['base_stat_value']

        self.str = stats.get('str', base)
        self.dex = stats.get('dex', base)
        self.con = stats.get('con', base)
        self.wis = stats.get('wis', base)
        self.int = stats.get('int', base)
        self.cha = stats.get('cha', base)

        self.starting_str = self.str
        self.starting_dex = self.dex
        self.starting_con = self.con
        self.starting_wis = self.wis
        self.starting_int = self.int
        self.starting_cha = self.cha

        sd = r['starting_dice']
        l1 = r['level_1_bonuses']

        self.vit_n = 1 + l1['vit_dice_count']
        self.hp_n = 1 + l1['hp_dice_count']
        self.mana_n = 1 + l1['mana_dice_count']

        self.vit_die = sd['vit_die']
        self.hp_die = sd['hp_die']
        self.mana_die = sd['mana_die']

        self.flat_vit = 0
        self.flat_hp = 0
        self.flat_mana = 0
        self.ac_bonus = 0
        self.armor_training_ac_heavy = 0
        self.armor_training_ac_medium = 0
        self._weapon_magic_bonus = 0
        self.fire_damage_bonus = None
        self.earth_damage_bonus = None
        self.water_damage_bonus = None
        self.air_damage_bonus = None
        self.radiant_damage_bonus = None
        self.necrotic_damage_bonus = None
        self.psychic_damage_bonus = None

        sp = r['starting_points']
        sc = r['starting_combat']

        self.skill_points = sp['skill_points'] + l1['skill_points']
        self.stat_points = 0
        self.affinity_points = sp['affinity_points']

        self.ap = sc['ap']
        self.bap = sc['bap']
        self.rp = sc['rp']
        self.prof = r['proficiency']['base']

        self.feats = 0
        self.feat_per_feat = 0
        self.spells_from_levels = 0
        self.starting_spells = 0

        self.has_physical = False
        self.has_magical = False
        self.has_utility = False
        self.affinities = {"Generic": 1}
        self.archetype_levels = {}
        self.archetype_whole_levels = {}

        self.stat_points_spent = 0

        self.melee_damage = 0
        self.melee_accuracy = 0
        self.ranged_damage = 0
        self.ranged_accuracy = 0
        self.magic_accuracy = 0
        self.magic_damage = 0

        self.gear = {}

        self.level = 1

        self.feats_taken = []
        self.feat_fallback_notes = []
        self.vit_per_level_bonus = 0
        self.hp_per_level_bonus = 0
        self.mana_per_level_bonus = 0
        self.crit_bonus_die = None
        self.save_half_magic = False
        self.dual_wield_accuracy = 0
        self.brawler_stacks = 0
        self.max_dex_ac_extra = 0
        self.hunker_ac = 0
        self.mana_well_die = None
        self.eternal_mana_threshold = 0
        self.eternal_mana_amount = 0
        self.charge_die = None
        self.cleave_damage = 0
        self.prone_die = None
        self.execute_threshold = 0
        self.weapon_group_accuracy = 0
        self.point_blank = False
        self.steady_aim_accuracy = 0
        self.first_round_damage = None
        self.ap_first_round = 0
        self.first_round_advantage = False
        self.ranged_adv_damage_stacks = 0
        self.ranged_expertise = False
        self.defensive_duelist_ac = False
        self.overdrive_bonus = 0
        self.quick_spells = False
        self.twin_cast = False
        self.is_unarmed = False
        self.tull_tier = 0
        self.tull_claw_die = None
        self.tull_claw_flat = 0
        self.shield_master = False
        self.melee_extra_info = None
        self.pack_tactics = False
        self.extra_attack_bap = False
        self.speed = 30
        self.initiative = 0
        self.bonus_action_sprint = False
        self.melee_kill_bonus = False
        self.ranged_ignore_half_cover = False
        self.stat_points_banked = {}
        self.skill_points_per_level = 0
        self.proficiency_per_level = 0
        self.expertise_per_level = 0
        self.affinity_per_level = 0
        self.magic_blast = False
        self.magic_accuracy_non_water = 0
        self.magic_accuracy_non_air = 0
        self.magic_accuracy_non_fire = 0
        self.magic_accuracy_non_earth = 0
        self.magic_accuracy_non_necrotic = 0
        self.magic_accuracy_non_radiant = 0
        self.hallowed_affinity = 0
        self.eldritch_affinity = 0
        self.eldritch_blast_damage = 1
        self.eldritch_blast_range = 0
        self.true_sight_range = 0
        self.fly_speed = 0
        self.karma = 0
        self.initiative_advantage = False
        self.darkvision_range = 0
        self.immunity_threatened = False
        self.immunity_surprised = False
        self.pact_access_tier = 1
        self.generic_affinity_spendable = False
        self.anti_deity_damage = False
        self.healing_maximize = False
        self.cleansing = 0
        self.concentration_two_spells = False
        self.free_heal = False
        self.reaction_save_ally = False
        self.damage_reduction = 0
        self.crit_block = False
        self.second_chance = False
        self.skill_tree_level_bonus = False
        self.spell_damage_mult = 1
        self.spell_mana_mult = 1

    def mod(self, stat):
        val = getattr(self, stat)
        return (val - 10) // 2

    def vit_max(self, r):
        con_mod = self.mod('con')
        dice_avg = self.vit_n * die_average(self.vit_die)
        con_bonus = con_mod * self.vit_n
        return self.flat_vit + int(dice_avg + con_bonus)

    def hp_max(self, r):
        dice_avg = self.hp_n * die_average(self.hp_die)
        return self.flat_hp + int(dice_avg)

    def mana_max(self, r):
        wis_mod = self.mod('wis')
        dice_avg = self.mana_n * die_average(self.mana_die)
        return self.flat_mana + int(dice_avg + wis_mod * self.mana_n)

    def ac(self, armor_type, armor_types, dex_table=None):
        base = 10
        dex_mod = self.mod('dex')
        armor_info = armor_types.get(armor_type, armor_types.get('none', {'ac_bonus': 0, 'max_dex': 4}))
        armor_bonus = armor_info['ac_bonus']
        max_dex = armor_info['max_dex']

        if armor_type in ('heavy', 'nerite_heavy', 'dragon_heavy'):
            armor_bonus += getattr(self, 'armor_training_ac_heavy', 0)
        if armor_type in ('medium', 'nerite_medium', 'dragon_medium'):
            armor_bonus += getattr(self, 'armor_training_ac_medium', 0)

        max_dex += getattr(self, 'max_dex_ac_extra', 0)

        if armor_type == 'none':
            effective = min(dex_mod, max_dex)
        else:
            effective = max(0, min(dex_mod, max_dex))

        if dex_table and effective > 0:
            dex_bonus = dex_table.get(str(min(effective, 18)), min(effective, 7))
        elif effective <= 0:
            dex_bonus = effective if armor_type == 'none' else 0
        else:
            dex_bonus = effective

        shield_bonus = 0
        shield_name = self.gear.get('shield')
        if shield_name:
            shield_info = armor_types.get(shield_name)
            if shield_info:
                shield_bonus = shield_info['ac_bonus']
                if self.shield_master:
                    shield_bonus *= 2

        return base + armor_bonus + dex_bonus + self.ac_bonus + shield_bonus

    def to_hit_melee(self):
        acc = self.prof + self.melee_accuracy + self.weapon_group_accuracy + self.steady_aim_accuracy
        if self.dual_wield_accuracy > 0:
            acc += self.dual_wield_accuracy
        return acc + self.mod('str')

    def to_hit_ranged(self):
        acc = self.prof + self.ranged_accuracy + self.weapon_group_accuracy + self.steady_aim_accuracy
        return acc + self.mod('dex')

    def to_hit_magic(self):
        generic = self.affinities.get('Generic', 0)
        best_specific = 0
        for k, v in self.affinities.items():
            if k != 'Generic' and v > best_specific:
                best_specific = v
        weapon_name = self.gear.get('weapon', '')
        weapon_magic_bonus = 0
        if weapon_name and weapon_name not in ('none', None):
            weapon_magic_bonus = getattr(self, '_weapon_magic_bonus', 0)
        return (attack_bonus_generic(generic)
                + attack_bonus_standard(best_specific)
                + self.magic_accuracy + weapon_magic_bonus)
