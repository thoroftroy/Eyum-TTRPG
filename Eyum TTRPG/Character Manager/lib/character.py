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

        self._magician_damage_mult_2x = 2
        self._magician_mana_mult_2x = 4
        self._magician_damage_mult_3x = 3
        self._magician_mana_mult_3x = 6
        self._magician_has_2x = False
        self._magician_has_3x = False

        # ---- NEW: Full rules engine systems ----
        self.conditions = {}          # {condition_name: [stacks, duration, source_dc]}
        self.injuries = []            # [(condition_name, stacks, duration)]
        self.overkill_level = 0
        self.exhaustion = 0
        self.current_vit = None       # set after max calcs
        self.current_hp = None
        self.current_mana = None
        self.karma = 0
        self.alignment = "Neutral"
        self.size_category = "Medium"
        self.vision_types = ["Normal Vision"]
        self.weapon_proficiency = []  # list of weapon types proficient in
        self.weapon_expertise = []    # list of specific weapons with expertise
        self.armor_proficiency = []   # ["Light"] or ["Light", "Medium"] etc
        self.armor_expertise = []     # armor types with expertise
        self.shield_proficiency = False
        self.shield_expertise = False
        self.tool_proficiency = []
        self.tool_expertise = []
        self.resistances = {}     # {damage_type_or_group: multiplier}
        self.weaknesses = {}      # {damage_type_or_group: multiplier}
        self.immunities = []      # [damage_type_or_group]
        self.languages = ["Common"]
        self.racial_language = ""
        self.spells_known = []
        self._magician_tier_choice = None  # None, "2x", or "3x"

    def set_magician_tier(self, choice):
        """Set Magician spell multiplier: '2x' or '3x' (handbook: choose either)."""
        self._magician_tier_choice = choice
        if choice == "2x":
            self.spell_damage_mult = self._magician_damage_mult_2x
            self.spell_mana_mult = self._magician_mana_mult_2x
        elif choice == "3x":
            self.spell_damage_mult = self._magician_damage_mult_3x
            self.spell_mana_mult = self._magician_mana_mult_3x
        else:
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

    # ==== NEW RULES ENGINE METHODS ====

    # ---- Injury System (1.3 Player Stats + 2.3 Injuries) ----
    def check_injury(self, hp_damage_taken, max_hp, damage_type, is_crit=False):
        """Process an injury check. Returns dict with results."""
        from .rules_engine import (INJURY_SEVERITY, INJURY_DC, INJURY_MAP,
                                   OVERKILL_EFFECTS)
        if hp_damage_taken <= 0 or max_hp <= 0:
            return None
        pct = hp_damage_taken / max_hp

        severity = None
        for sev, lo, hi in INJURY_SEVERITY:
            if pct >= lo:
                severity = sev
        if not severity:
            return None

        if is_crit:
            sev_order = ["Minor", "Moderate", "Severe", "Extreme"]
            idx = sev_order.index(severity)
            severity = sev_order[min(idx + 1, 3)]

        massive_damage = pct >= 0.5
        dc = INJURY_DC[severity]

        if self.overkill_level >= 1:
            dc += OVERKILL_EFFECTS.get(self.overkill_level, {}).get("dc_penalty", 0)
        if OVERKILL_EFFECTS.get(self.overkill_level, {}).get("auto_fail"):
            dc = 9999

        con_save = self.mod('con')

        injury_info = {
            "severity": severity,
            "dc": dc,
            "massive_damage": massive_damage,
            "damage_type": damage_type,
        }

        if damage_type in INJURY_MAP:
            mapping = INJURY_MAP[damage_type]
            if severity in mapping:
                cond, turns = mapping[severity]
                injury_info["condition"] = cond
                injury_info["turns"] = turns

        return injury_info

    def apply_injury_result(self, result, con_roll):
        """Apply injury check result. con_roll is the d20 result (+ Con mod handled externally)."""
        if not result:
            return
        if con_roll >= result["dc"]:
            self.overkill_level = min(5, self.overkill_level + 1)
        else:
            self.overkill_level = 0
            if "condition" in result:
                self.injuries.append({
                    "condition": result["condition"],
                    "turns": result["turns"],
                    "severity": result["severity"],
                })
            if result.get("massive_damage"):
                return "unconscious_check"

    def has_injury(self):
        return len(self.injuries) > 0

    # ---- Condition System (2.4 Conditions) ----
    def add_condition(self, name, stacks=1, duration=None, dc=None):
        from .rules_engine import CONDITIONS
        info = CONDITIONS.get(name, {})
        default_dur = info.get("default_duration", duration or 2)
        dur = duration if duration is not None else default_dur
        save_dc = dc if dc is not None else info.get("default_dc", 10)

        if name in self.conditions and info.get("stackable"):
            self.conditions[name]["stacks"] += stacks
            self.conditions[name]["duration"] = max(self.conditions[name]["duration"], dur)
            if save_dc > self.conditions[name].get("dc", 0):
                self.conditions[name]["dc"] = save_dc
        else:
            self.conditions[name] = {"stacks": stacks, "duration": dur, "dc": save_dc}

    def remove_condition(self, name):
        if name in self.conditions:
            del self.conditions[name]

    def tick_conditions(self):
        from .rules_engine import CONDITIONS
        damage_taken = {}
        expired = []
        for name, data in self.conditions.items():
            info = CONDITIONS.get(name, {})
            if info.get("damage_per_turn", 0) > 0:
                dmg = info["damage_per_turn"] * data["stacks"]
                dmg_type = info.get("damage_type", "True")
                damage_taken[name] = (dmg, dmg_type)
            data["duration"] -= 1
            if data["duration"] <= 0:
                expired.append(name)
        for name in expired:
            del self.conditions[name]
        return damage_taken

    def get_condition_penalties(self):
        from .rules_engine import CONDITIONS
        ac_penalty = 0
        atk_penalty = 0
        save_penalty = 0
        speed_mult = 1.0
        for name, data in self.conditions.items():
            info = CONDITIONS.get(name, {})
            ac_penalty += info.get("affects_ac", 0) * data["stacks"]
            atk_penalty += info.get("affects_attacks", 0) * data["stacks"]
            save_penalty += info.get("affects_saves", 0) * data["stacks"]
            spd = info.get("affects_speed_pct", 1.0)
            if spd < 1.0:
                speed_mult = min(speed_mult, spd)
        return {
            "ac": ac_penalty,
            "attack": atk_penalty,
            "save": save_penalty,
            "speed_mult": speed_mult,
        }

    # ---- Exhaustion System (1.3 Player Stats) ----
    def add_exhaustion(self, levels=1):
        self.exhaustion = min(6, self.exhaustion + levels)

    def remove_exhaustion(self, levels=1):
        self.exhaustion = max(0, self.exhaustion - levels)

    def get_exhaustion_penalties(self):
        from .rules_engine import EXHAUSTION_EFFECTS
        penalties = {}
        for lvl in range(1, self.exhaustion + 1):
            eff = EXHAUSTION_EFFECTS.get(lvl, {})
            if eff.get("death"):
                return {"dead": True}
            if eff.get("ability_disadvantage"):
                penalties["ability_disadvantage"] = True
            if eff.get("speed_halved"):
                penalties["speed_halved"] = True
            if eff.get("attack_disadvantage"):
                penalties["attack_disadvantage"] = True
                penalties["save_disadvantage"] = True
            if eff.get("hp_vit_max_halved"):
                penalties["hp_vit_halved"] = True
            if eff.get("speed_5ft"):
                penalties["speed_5ft"] = True
        return penalties

    # ---- Resting System (1.3 Player Stats) ----
    def short_rest(self, r):
        from .rules_engine import REST_RULES
        rr = REST_RULES["short_rest"]
        has_inj = self.has_injury()

        self.current_vit = self.vit_max(r)
        if has_inj:
            self.current_vit = int(self.current_vit * rr["with_injury_vit"])
        self.current_mana = int(self.mana_max(r) * (rr["with_injury_mana"] if has_inj else rr["mana_restore"]))
        return self.current_vit, self.current_mana

    def long_rest(self, r):
        from .rules_engine import REST_RULES
        rr = REST_RULES["long_rest"]
        has_inj = self.has_injury()

        self.current_hp = int(self.hp_max(r) * (rr["with_injury_hp"] if has_inj else 1.0))
        self.current_vit = int(self.vit_max(r) * (rr["with_injury_vit"] if has_inj else 1.0))
        self.current_mana = int(self.mana_max(r) * (rr["with_injury_mana"] if has_inj else 1.0))
        self.remove_exhaustion(rr["exhaustion_remove"])
        return self.current_hp, self.current_vit, self.current_mana

    # ---- Resistance / Weakness System (2.2 Damage Types) ----
    def add_resistance(self, dmg_type, level="Resistance"):
        from .rules_engine import RESISTANCE_MULTIPLIERS
        self.resistances[dmg_type] = RESISTANCE_MULTIPLIERS.get(level, 0.5)

    def add_weakness(self, dmg_type, level="Weakness"):
        from .rules_engine import RESISTANCE_MULTIPLIERS
        self.weaknesses[dmg_type] = RESISTANCE_MULTIPLIERS.get(level, 2.0)

    def add_immunity(self, dmg_type):
        if dmg_type not in self.immunities:
            self.immunities.append(dmg_type)

    def damage_multiplier(self, dmg_type):
        from .rules_engine import damage_group
        if dmg_type in self.immunities:
            return 0
        group = damage_group(dmg_type)
        if group in self.immunities:
            return 0
        if dmg_type in self.resistances:
            return self.resistances[dmg_type]
        if group in self.resistances:
            return self.resistances[group]
        if dmg_type in self.weaknesses:
            return self.weaknesses[dmg_type]
        if group in self.weaknesses:
            return self.weaknesses[group]
        return 1.0

    def apply_damage(self, damage, dmg_type, bypass_vit=False, is_aoe=False):
        """Apply damage to character, handling Vitality/HP split and resistance."""
        from .rules_engine import split_aoe_damage
        mult = self.damage_multiplier(dmg_type)
        total = int(damage * mult)

        if bypass_vit:
            self.current_hp = max(0, (self.current_hp or self.hp_max({})) - total)
            return {"vit_lost": 0, "hp_lost": total, "remaining_vit": self.current_vit,
                    "remaining_hp": self.current_hp}

        if is_aoe:
            hp_dmg, vit_dmg = split_aoe_damage(total)
        else:
            hp_dmg, vit_dmg = 0, total

        vit_lost = min(self.current_vit or 0, vit_dmg)
        self.current_vit = max(0, (self.current_vit or 0) - vit_dmg)
        hp_from_vit = max(0, vit_dmg - vit_lost)
        total_hp_dmg = hp_dmg + hp_from_vit
        self.current_hp = max(0, (self.current_hp or self.hp_max({})) - total_hp_dmg)

        return {"vit_lost": vit_lost, "hp_lost": total_hp_dmg,
                "remaining_vit": self.current_vit, "remaining_hp": self.current_hp}

    # ---- Alignment / Karma ----
    def set_karma(self, val):
        self.karma = max(-500, min(500, val))
        from .rules_engine import ALIGNMENT_THRESHOLDS
        for align, (lo, hi) in ALIGNMENT_THRESHOLDS.items():
            if lo <= self.karma <= hi:
                self.alignment = align

    def adjust_karma(self, delta):
        self.set_karma(self.karma + delta)

    # ---- Weapon/Armor Proficiency ----
    def is_proficient_with_weapon_type(self, weapon_type):
        return weapon_type in self.weapon_proficiency

    def has_weapon_expertise(self, weapon_name):
        return weapon_name in self.weapon_expertise

    def is_proficient_with_armor(self, armor_type):
        return armor_type in self.armor_proficiency

    def has_armor_expertise(self, armor_type):
        return armor_type in self.armor_expertise

    def armor_proficiency_penalty(self, armor_type):
        """Returns tuple of penalties if not proficient."""
        if self.is_proficient_with_armor(armor_type):
            return None
        penalties = {
            "Light": {"ac_penalty": 0, "dex_penalty": -1},
            "Medium": {"ac_penalty": -1, "speed_penalty": 0},
            "Heavy": {"ac_penalty": -1, "speed_penalty": -5},
        }
        return penalties.get(armor_type, {"ac_penalty": 0})

    # ---- Initialize pools to max after creation ----
    def init_pools(self, r):
        self.current_vit = self.vit_max(r)
        self.current_hp = self.hp_max(r)
        self.current_mana = self.mana_max(r)
