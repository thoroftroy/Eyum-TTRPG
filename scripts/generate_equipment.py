#!/usr/bin/env python3
"""Generate every weapon/armor/shield x material combination with full stats."""
import json, os, sys, math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(REPO_ROOT, 'Eyum TTRPG', 'Character Manager', 'data')
GEAR_DIR = os.path.join(DATA_DIR, 'gear')
DIST_DIR = os.path.join(REPO_ROOT, 'dist')

# Load gear data from new gear/ files
with open(os.path.join(GEAR_DIR, 'weapons.json')) as f:
    GEAR_WEAPONS = json.load(f)
with open(os.path.join(GEAR_DIR, 'armor.json')) as f:
    GEAR_ARMORS = json.load(f)
with open(os.path.join(GEAR_DIR, 'shields.json')) as f:
    GEAR_SHIELDS = json.load(f)
with open(os.path.join(GEAR_DIR, 'arrows.json')) as f:
    GEAR_ARROWS = json.load(f)

# Die averages
with open(os.path.join(DATA_DIR, 'rules.json')) as f:
    RULES = json.load(f)
DIE_AVG = RULES['die_averages']

def avg_die(die_str):
    if not die_str: return 0
    return DIE_AVG.get(die_str, 0)

# ── Build weapon list from gear/weapons.json ──
WEAPONS = []
for gw in GEAR_WEAPONS:
    w = {
        "name": gw["name"],
        "die": gw.get("die"),
        "dmg_type": gw.get("dmg_type", "Bludgeoning"),
        "range": gw.get("range", 5),
        "ranged_max": gw.get("ranged_max", gw.get("range", 5)),
        "types": gw.get("categories", []),
        "ap": 1,
        "notes": gw.get("notes", ""),
        "base_price": gw.get("price_copper", 0),
    }
    if gw.get("versatile_die"):
        w["versatile_die"] = gw["versatile_die"]
    if gw.get("magic_die"):
        w["magic_die"] = gw["magic_die"]
        w["die"] = None  # Magic weapons don't have a physical damage die
        w["dmg_type"] = "Magical"
    WEAPONS.append(w)

# Ranged weapons that use ammunition
RANGED_WEAPONS = {"Shortbow","Longbow","Light Crossbow","Heavy Crossbow","Hand Crossbow","Sling","Atlatl"}

# Macuahuitl embeddable materials (per handbook: Obsidian, animal claws, animal teeth, dragon scales)
MACUAHUITL_EMBEDS = [
    {"name": "Obsidian", "damage": 4, "accuracy": 1, "dmg_type": "Slashing", "notes": "Obsidian shards"},
    {"name": "Claws (Bear)", "damage": 1, "accuracy": 1, "dmg_type": "Slashing", "notes": "Bear claws embedded"},
    {"name": "Claws (Griffin)", "damage": 2, "accuracy": 1, "dmg_type": "Slashing", "notes": "Griffin claws embedded"},
    {"name": "Teeth (Wolf)", "damage": 1, "accuracy": 1, "dmg_type": "Piercing", "notes": "Wolf teeth embedded"},
    {"name": "Teeth (Shark)", "damage": 1, "accuracy": 0, "dmg_type": "Piercing", "notes": "Shark teeth embedded"},
    {"name": "Dragon Scale (Fire)", "damage": 9, "accuracy": 6, "dmg_type": "Fire", "notes": "Fire dragon scales embedded"},
    {"name": "Dragon Scale (Earth)", "damage": 8, "accuracy": 5, "dmg_type": "Earth", "notes": "Earth dragon scales embedded"},
    {"name": "Dragon Scale (Radiant)", "damage": 9, "accuracy": 7, "dmg_type": "Radiant", "notes": "Radiant dragon scales embedded"},
    {"name": "Dragon Scale (Necrotic)", "damage": 9, "accuracy": 7, "dmg_type": "Necrotic", "notes": "Necrotic dragon scales embedded"},
]

# ── Materials with stat modifiers from 2.6 ──
MATERIALS = [
    {"name":"Junk Metal","damage":-5,"accuracy":-5,"ac_bonus":-6,"tool":-5,"ench":-5,"price_mult":0.1,"price_lbs":0.01},
    {"name":"Gold","damage":-2,"accuracy":-2,"ac_bonus":-2,"tool":2,"ench":12,"price_mult":35,"price_lbs":100},
    {"name":"Magnesium","damage":1,"accuracy":0,"ac_bonus":-3,"tool":1,"ench":1,"price_mult":0.8,"price_lbs":0.5},
    {"name":"Copper","damage":-1,"accuracy":-1,"ac_bonus":-2,"tool":1,"ench":4,"price_mult":0.5,"price_lbs":0.2},
    {"name":"Cadmium","damage":-1,"accuracy":1,"ac_bonus":-1,"tool":-1,"ench":5,"price_mult":1,"price_lbs":0.5},
    {"name":"Tin","damage":-1,"accuracy":0,"ac_bonus":-2,"tool":1,"ench":2,"price_mult":0.3,"price_lbs":0.2},
    {"name":"Zinc","damage":-1,"accuracy":0,"ac_bonus":-1,"tool":1,"ench":1,"price_mult":0.5,"price_lbs":0.3},
    {"name":"Lithium","damage":-2,"accuracy":-2,"ac_bonus":-2,"tool":-2,"ench":6,"price_mult":0.5,"price_lbs":0.3},
    {"name":"Aluminum","damage":-1,"accuracy":1,"ac_bonus":-1,"tool":1,"ench":0,"price_mult":0.7,"price_lbs":1},
    {"name":"Pewter","damage":-1,"accuracy":0,"ac_bonus":-1,"tool":2,"ench":3,"price_mult":0.6,"price_lbs":0.4},
    {"name":"Brass","damage":0,"accuracy":-1,"ac_bonus":-1,"tool":3,"ench":1,"price_mult":1.2,"price_lbs":0.5},
    {"name":"Lead","damage":1,"accuracy":-3,"ac_bonus":1,"tool":2,"ench":2,"price_mult":1.4,"price_lbs":0.3},
    {"name":"Silver","damage":0,"accuracy":1,"ac_bonus":0,"tool":2,"ench":3,"price_mult":5,"price_lbs":2},
    {"name":"Iron","damage":0,"accuracy":0,"ac_bonus":0,"tool":3,"ench":-1,"price_mult":1,"price_lbs":0.7},
    {"name":"Manganese","damage":1,"accuracy":-2,"ac_bonus":2,"tool":2,"ench":2,"price_mult":1,"price_lbs":0.7},
    {"name":"Nickel","damage":0,"accuracy":0,"ac_bonus":1,"tool":3,"ench":2,"price_mult":1.5,"price_lbs":1},
    {"name":"Bronze","damage":0,"accuracy":0,"ac_bonus":1,"tool":3,"ench":1,"price_mult":1.1,"price_lbs":0.8},
    {"name":"Osmium","damage":5,"accuracy":-5,"ac_bonus":5,"tool":-2,"ench":3,"price_mult":5,"price_lbs":400},
    {"name":"Tungsten","damage":3,"accuracy":-4,"ac_bonus":4,"tool":1,"ench":2,"price_mult":5,"price_lbs":200},
    {"name":"Obsidian","damage":4,"accuracy":1,"ac_bonus":-2,"tool":2,"ench":6,"price_mult":4,"price_lbs":6},
    {"name":"Electrum","damage":1,"accuracy":1,"ac_bonus":1,"tool":3,"ench":8,"price_mult":12,"price_lbs":200},
    {"name":"Steel","damage":1,"accuracy":1,"ac_bonus":1,"tool":5,"ench":0,"price_mult":3,"price_lbs":5},
    {"name":"Platinum","damage":1,"accuracy":1,"ac_bonus":2,"tool":4,"ench":6,"price_mult":18,"price_lbs":600},
    {"name":"Cobalt","damage":2,"accuracy":3,"ac_bonus":1,"tool":4,"ench":20,"price_mult":15,"price_lbs":200},
    {"name":"Iridium","damage":1,"accuracy":4,"ac_bonus":2,"tool":3,"ench":10,"price_mult":8,"price_lbs":300},
    {"name":"Carbon","damage":5,"accuracy":4,"ac_bonus":4,"tool":3,"ench":5,"price_mult":8,"price_lbs":400},
    {"name":"Chromium","damage":3,"accuracy":1,"ac_bonus":3,"tool":5,"ench":4,"price_mult":4,"price_lbs":6},
    {"name":"Duralumin","damage":4,"accuracy":3,"ac_bonus":1,"tool":6,"ench":4,"price_mult":7,"price_lbs":400},
    {"name":"Alnico","damage":2,"accuracy":4,"ac_bonus":2,"tool":8,"ench":6,"price_mult":10,"price_lbs":500},
    {"name":"Orichalcum","damage":3,"accuracy":2,"ac_bonus":2,"tool":9,"ench":7,"price_mult":22,"price_lbs":700},
    {"name":"Titanium","damage":5,"accuracy":2,"ac_bonus":3,"tool":6,"ench":3,"price_mult":12,"price_lbs":600},
    {"name":"Uranium","damage":8,"accuracy":3,"ac_bonus":-5,"tool":5,"ench":15,"price_mult":10,"price_lbs":100},
    {"name":"Alchemically Pure Metal","damage":3,"accuracy":3,"ac_bonus":3,"tool":8,"ench":18,"price_mult":25,"price_lbs":800},
    {"name":"Adamantine","damage":4,"accuracy":2,"ac_bonus":4,"tool":8,"ench":5,"price_mult":20,"price_lbs":700},
    {"name":"Mithril","damage":4,"accuracy":3,"ac_bonus":5,"tool":7,"ench":6,"price_mult":18,"price_lbs":700},
    {"name":"Infernal Iron","damage":5,"accuracy":4,"ac_bonus":4,"tool":10,"ench":8,"price_mult":30,"price_lbs":100},
    {"name":"Hallowed Iron","damage":3,"accuracy":4,"ac_bonus":5,"tool":12,"ench":9,"price_mult":30,"price_lbs":100},
    {"name":"Nerite","damage":6,"accuracy":6,"ac_bonus":6,"tool":11,"ench":10,"price_mult":40,"price_lbs":300},
    {"name":"Voidsteel","damage":7,"accuracy":7,"ac_bonus":7,"tool":12,"ench":9,"price_mult":60,"price_lbs":500},
]
# Gold price_lbs is 1 Nerite = 100 Gold; Nerite price_lbs is 3 Nerite = 300 Gold
# Uranium price_lbs is 1 Nerite = 100 Gold
# Infernal/Hallowed price_lbs is 1 Nerite = 100 Gold
# Voidsteel price_lbs is 5 Nerite = 500 Gold
# Let's fix prices to be in gold:
PRICE_FIX = {"Gold":10000,"Nerite":30000,"Uranium":10000,"Infernal Iron":10000,"Hallowed Iron":10000,"Voidsteel":50000,
             "Osmium":400,"Tungsten":200,"Electrum":200,"Platinum":6000,"Duralumin":400,"Alnico":500,"Orichalcum":700,
             "Titanium":600,"Alchemically Pure Metal":800,"Adamantine":700,"Mithril":700,"Cobalt":20000,"Iridium":300,"Carbon":400}
for m in MATERIALS:
    if m["name"] in PRICE_FIX:
        m["price_lbs"] = PRICE_FIX[m["name"]]

# ── Shield types ──
SHIELDS = [
    {"name":"Buckler","ac":1,"types":["Shield"],"notes":"Hand remains free"},
    {"name":"Small Shield","ac":1,"types":["Shield"],"notes":""},
    {"name":"Medium Shield","ac":2,"types":["Shield"],"notes":""},
    {"name":"Large Shield","ac":3,"types":["Shield"],"notes":""},
    {"name":"Heater Shield","ac":3,"types":["Shield"],"notes":""},
]

# ── Armor types ──
ARMORS = [
    {"name":"None","ac":0,"max_dex":4,"label":"No Armor"},
    {"name":"Light","ac":2,"max_dex":5,"label":"Light Armor"},
    {"name":"Medium","ac":5,"max_dex":4,"label":"Medium Armor"},
    {"name":"Heavy","ac":8,"max_dex":3,"label":"Heavy Armor"},
]

# ── Dex bonus table ──
DEX_TABLE = RULES["ac"]["dex_bonus_table"]

def dex_bonus(dex_mod):
    """Get AC bonus from DEX modifier using the handbook table."""
    return DEX_TABLE.get(str(dex_mod), min(7, max(0, dex_mod)))

# ── Generate ──
def hit_chance(accuracy, target_ac):
    """Probability to hit: roll d20 + accuracy >= target_ac."""
    needed = target_ac - accuracy
    if needed <= 1: return 0.95
    if needed >= 20: return 0.05
    return max(0.05, min(0.95, (21 - needed) / 20))

def crit_chance():
    return 0.05

def generate_weapons():
    results = []
    for w in WEAPONS:
        is_ranged = w["name"] in RANGED_WEAPONS
        is_macuahuitl = w["name"] == "Macuahuitl"

        for m in MATERIALS:
            base_die = w.get("versatile_die") or w["die"]
            die_str = base_die if base_die else w.get("magic_die")
            base_avg = avg_die(die_str) if die_str else 0

            dmg_mod = m["damage"]
            acc_mod = m["accuracy"]
            total_damage = base_avg + dmg_mod
            total_accuracy = acc_mod

            # Price
            mat_price_mult = m["price_mult"]
            mat_price_lbs = m["price_lbs"]
            is_two_handed = "Two-Handed" in w["types"]
            is_heavy = "Heavy" in w["types"]
            weight = 10 if is_two_handed else (7 if is_heavy else (3 if "Light" in w["types"] else 5))
            material_cost = mat_price_lbs * weight
            total_price_gold = (w["base_price"] / 100) * mat_price_mult + material_cost

            category = [t for t in w["types"] if t in [
                "Unarmed","Light","Finesse","Thrown","Versatile","Two-Handed","Heavy",
                "Reach","Martial","Hooking","Ranged","Loading","Magical","Restraining","Special"
            ]]

            entry = {
                "name": f"{m['name']} {w['name']}",
                "weapon": w["name"], "material": m["name"],
                "die": die_str, "dmg_type": w["dmg_type"],
                "base_avg_dmg": round(base_avg,1), "mat_dmg_mod": dmg_mod,
                "mat_acc_mod": acc_mod, "total_dmg": round(total_damage,1),
                "total_acc": total_accuracy, "range": w["range"],
                "ranged_max": w.get("ranged_max", w["range"]),
                "types": w["types"], "category": category,
                "ap": w["ap"], "weight_lbs": weight,
                "price_gold": round(total_price_gold,1),
                "price_mult": mat_price_mult, "ench": m["ench"],
                "notes": w.get("notes",""),
            }
            results.append(entry)

            # For ranged weapons: generate arrow variant with same material
            if is_ranged and m["name"] != "Junk Metal":
                ammo_entry = dict(entry)
                ammo_entry["name"] = f"{m['name']} {w['name']} ({m['name']} arrow)"
                ammo_entry["notes"] = f"Bow: {m['name']}, Arrow: {m['name']}"
                results.append(ammo_entry)

            # Macuahuitl: wooden base (Junk Metal stats), embeddable with specific materials
            if is_macuahuitl:
                # Only generate Macuahuitl with the actual wooden base (Junk Metal stats)
                # plus embedded material variants
                entry["name"] = f"Macuahuitl (wooden)"
                entry["material"] = "Wood"
                entry["notes"] = "Wooden club, no embedded materials yet"
                # Override stats for wooden base only
                entry["total_dmg"] = round(base_avg + m["damage"], 1)
                entry["total_acc"] = m["accuracy"]
                results.append(entry)

                for embed in MACUAHUITL_EMBEDS:
                    mac_entry = dict(entry)
                    mac_entry["name"] = f"Macuahuitl ({embed['name']})"
                    mac_entry["material"] = f"Wood+{embed['name']}"
                    mac_entry["dmg_type"] = embed["dmg_type"]
                    mac_entry["total_dmg"] = round(base_avg + embed["damage"], 1)
                    mac_entry["total_acc"] = embed["accuracy"]
                    mac_entry["notes"] = f"Wooden club, {embed['notes']}"
                    results.append(mac_entry)
                continue  # Skip the normal material loop for Macuahuitl (only wood base + embeds)

    return results

def generate_armors():
    results = []
    for a in ARMORS:
        for m in MATERIALS:
            if a["name"] == "None":
                results.append({
                    "name": "No Armor", "armor_type": "None", "material": "None",
                    "ac_bonus": 0, "mat_ac": 0, "total_ac": 0, "max_dex": a["max_dex"],
                    "price_gold": 0, "ench": 0
                })
                continue
            mat_ac = m["ac_bonus"]
            total_ac = a["ac"] + mat_ac
            results.append({
                "name": f"{m['name']} {a['label']}",
                "armor_type": a["name"],
                "material": m["name"],
                "ac_bonus": a["ac"],
                "mat_ac": mat_ac,
                "total_ac": total_ac,
                "max_dex": a["max_dex"],
                "price_gold": round(m["price_lbs"] * 25 * m["price_mult"], 1),
                "ench": m["ench"],
            })
    return results

def generate_shields():
    results = []
    for s in SHIELDS:
        for m in MATERIALS:
            mat_ac = m["ac_bonus"]
            # Shield material AC bonus is halved
            total_ac = s["ac"] + mat_ac // 2
            results.append({
                "name": f"{m['name']} {s['name']}",
                "shield_type": s["name"],
                "material": m["name"],
                "base_ac": s["ac"],
                "mat_ac_half": mat_ac // 2,
                "total_ac": total_ac,
                "price_gold": round(m["price_lbs"] * 10 * m["price_mult"], 1),
                "types": s["types"],
                "notes": s.get("notes",""),
            })
    return results

def compute_dpr_vs_ac(weapons, target_acs):
    """Add DPR columns for each target AC."""
    for w in weapons:
        for ac in target_acs:
            hc = hit_chance(w["total_acc"], ac)
            cc = crit_chance()
            avg_crit_dmg = w["total_dmg"] * 2  # crit = max damage, approx 2x avg
            dpr = hc * w["total_dmg"] + cc * (avg_crit_dmg - w["total_dmg"])
            w[f"hit_vs_ac{ac}"] = round(hc * 100, 1)
            w[f"dpr_vs_ac{ac}"] = round(dpr, 1)
        # Overall metric vs average AC 15
        w["dpr_vs_ac15"] = w.get("dpr_vs_ac15", 0)
    return weapons

def compute_ttk(weapons, target_hp, target_ac):
    """Rounds to kill target with given HP at given AC."""
    for w in weapons:
        dpr = w.get(f"dpr_vs_ac{target_ac}", 0)
        w[f"ttk_{target_hp}hp_ac{target_ac}"] = round(target_hp / dpr, 1) if dpr > 0 else 999

def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DIST_DIR, 'equipment.json')

    weapons = generate_weapons()
    armors = generate_armors()
    shields = generate_shields()

    target_acs = [10, 12, 14, 16, 18, 20, 22, 25, 30]
    weapons = compute_dpr_vs_ac(weapons, target_acs)

    # TTK for common enemy profiles
    for hp, ac in [(50,14),(100,16),(200,18),(500,20),(1000,22)]:
        compute_ttk(weapons, hp, ac)

    # Sort weapons by DPR vs AC 16
    weapons.sort(key=lambda x: x.get("dpr_vs_ac16", 0), reverse=True)

    # Categorize for display
    by_category = {}
    for w in weapons:
        for cat in w["category"]:
            by_category.setdefault(cat, []).append(w["name"])

    # Auto-tier: classify weapons into tiers by DPR
    dprs = [w.get("dpr_vs_ac16", 0) for w in weapons if w.get("dpr_vs_ac16", 0) > 0]
    if dprs:
        dprs.sort()
        q1 = dprs[len(dprs)//4]
        q2 = dprs[len(dprs)//2]
        q3 = dprs[3*len(dprs)//4]
        for w in weapons:
            dpr = w.get("dpr_vs_ac16", 0)
            if dpr <= q1: w["dpr_tier"] = "worst"
            elif dpr <= q2: w["dpr_tier"] = "below_avg"
            elif dpr <= q3: w["dpr_tier"] = "above_avg"
            else: w["dpr_tier"] = "best"

    output = {
        "weapons": weapons,
        "armors": armors,
        "shields": shields,
        "materials": MATERIALS,
        "by_category": by_category,
        "target_acs": target_acs,
        "die_averages": DIE_AVG,
        "generated_count": len(weapons),
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"Generated {len(weapons)} weapons, {len(armors)} armors, {len(shields)} shields → {out_path}")
    print(f"File size: {os.path.getsize(out_path) / 1024:.0f} KB")

if __name__ == '__main__':
    main()
