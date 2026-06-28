#!/usr/bin/env python3
"""
Eyum TTRPG Character Manager GUI
Interactive data visualization for balance analysis.
Runs the generator on startup and displays line graphs.
The original generator.py remains fully functional as a standalone script.
"""

import matplotlib
matplotlib.use('TkAgg')

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import re
import json
import shutil
import threading
import traceback
from collections import OrderedDict
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')
BACKUP_DIR = os.path.join(SCRIPT_DIR, 'backup')

sys.path.insert(0, SCRIPT_DIR)

from lib.config import load_settings
from lib.gear import resolve_gear, select_gear
from generator import generate_build

ALL_STATS = [
    'Vitality', 'Health', 'Mana', 'AC', 'Feats', 'Spells', 'To Hit',
    'Dmg/Turn', 'Dmg/5R', 'Dmg/10R',
    'STR', 'DEX', 'CON', 'WIS', 'INT', 'CHA'
]

COLOR_CYCLE = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
    '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
    '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5'
]

STAT_LABELS = OrderedDict([
    ('Vitality', 'Vitality'),
    ('Health', 'Health'),
    ('Mana', 'Mana'),
    ('AC', 'Armor Class'),
    ('Feats', 'Feats'),
    ('Spells', 'Spells'),
    ('To Hit', 'To Hit Bonus'),
    ('Dmg/Turn', 'Damage / Turn'),
    ('Dmg/5R', 'Damage / 5 Rounds'),
    ('Dmg/10R', 'Damage / 10 Rounds'),
    ('STR', 'Strength'),
    ('DEX', 'Dexterity'),
    ('CON', 'Constitution'),
    ('WIS', 'Wisdom'),
    ('INT', 'Intelligence'),
    ('CHA', 'Charisma'),
])

JSON_FILES = [
    'rules.json', 'armor_types.json', 'paths.json',
    'gear_tiers.json', 'races.json', 'builds.json', 'spells.json',
    'feats.json', 'generation.json',
    'gear/weapons.json', 'gear/armor.json', 'gear/shields.json', 'gear/arrows.json',
]

AVG_LINE_COLOR = '#333333'
AVG_LINE_WIDTH = 3.5
AVG_LINE_STYLE = '--'
HOVER_ALPHA = 0.15
FOCUSED_ALPHA = 1.0

class ToolTip:
    """Hover tooltip for any widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tw = None
        widget.bind('<Enter>', self._show)
        widget.bind('<Leave>', self._hide)
    def _show(self, e=None):
        if self.tw: return
        x, y = self.widget.winfo_pointerxy()
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f'+{x+10}+{y+10}')
        lbl = ttk.Label(self.tw, text=self.text, background='#333', foreground='#eee',
                        relief='solid', borderwidth=1, padding=(6,3), font=('TkDefaultFont', 9))
        lbl.pack()
    def _hide(self, e=None):
        if self.tw: self.tw.destroy(); self.tw = None

plt.rcParams['figure.facecolor'] = '#1e1e1e'
plt.rcParams['axes.facecolor'] = '#252525'
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.alpha'] = 0.3


def create_backup():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    for fname in JSON_FILES:
        src = os.path.join(DATA_DIR, fname)
        dst = os.path.join(BACKUP_DIR, fname)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)


def restore_backup():
    if not os.path.exists(BACKUP_DIR):
        return False
    for fname in JSON_FILES:
        src = os.path.join(BACKUP_DIR, fname)
        dst = os.path.join(DATA_DIR, fname)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    return True


def get_original_backup():
    if not os.path.exists(BACKUP_DIR):
        return {}
    result = {}
    for fname in JSON_FILES:
        path = os.path.join(BACKUP_DIR, fname)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    result[fname] = f.read()
            except:
                result[fname] = ''
    return result


def extract_build_data(settings, results):
    r = settings['rules']
    armor_types = settings.get('armor_types', {})
    dex_table = r['ac']['dex_bonus_table']
    levels = sorted(set(res['level'] for res in results))
    build_data = {}

    for res in results:
        lvl = res['level']
        c = res['char']
        d = res['dmg_perturn']

        dmg_5 = res['dmg_5round']['total'] if isinstance(res['dmg_5round'], dict) else res['dmg_5round']
        dmg_10 = res['dmg_10round']['total'] if isinstance(res['dmg_10round'], dict) else res['dmg_10round']

        d5 = res['dmg_5round']
        d10 = res['dmg_10round']
        build_data[lvl] = {
            'Vitality': c.vit_max(r),
            'Health': c.hp_max(r),
            'Mana': c.mana_max(r),
            'AC': c.ac(c.gear.get('armor', 'none'), armor_types, dex_table),
            'Feats': c.feats,
            'Spells': c.starting_spells + c.spells_from_levels,
            'To Hit': max(c.to_hit_melee(), c.to_hit_ranged(), c.to_hit_magic()),
            'Dmg/Turn': int(d['per_turn']),
            'Dmg/5R': int(dmg_5),
            'Dmg/10R': int(dmg_10),
            'STR': c.str,
            'DEX': c.dex,
            'CON': c.con,
            'WIS': c.wis,
            'INT': c.int,
            'CHA': c.cha,
            'AP': c.ap,
            'BAp': c.bap,
            'ManaCost': int(d.get('mana_cost', 0)),
            'CondDmg': d.get('cond_dmg', 0),
            'CondNames': d.get('cond_names', []) if d.get('cond_dmg', 0) > 0 else [],
            'SpellExtra': d.get('spell_extra_effect', ''),
            'SpellName': d.get('spell_name', ''),
            'SpellElement': d.get('spell_element', ''),
            'SecondarySpell': d.get('secondary_spell', ''),
            'SecondaryCasts': d.get('secondary_casts', 0),
            'ManaStart5R': int(d5.get('mana_start', 0)),
            'ManaEnd5R': int(d5.get('mana_end', 0)),
            'ManaStart10R': int(d10.get('mana_start', 0)),
            'ManaEnd10R': int(d10.get('mana_end', 0)),
            'affinities': dict(c.affinities) if hasattr(c, 'affinities') else {},
            'race': res.get('race', 'none'),
        }
    return build_data, levels


def _gen_one_build(args):
    build_name, build_config, settings, levels, tier_dict, tier_label = args
    if not build_config.get('generate', True):
        return build_name, None
    # Use select_gear with max level budget for proper tiered gear
    tier_name = tier_dict.get('name', '')
    max_level = max(levels)
    if tier_name == 'no_gear':
        gear_override = {'weapon': None, 'armor': 'none'}
    else:
        gear_override = select_gear(build_config, tier_name, max_level)
    results = generate_build(build_name, build_config, settings, levels, gear_override, tier_label)
    bd, _ = extract_build_data(settings, results)
    flattened = {lvl: bd[lvl] for lvl in sorted(bd.keys())}
    return build_name, flattened


def collect_all_data(settings, progress_callback=None, build_filter=None):
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import multiprocessing
    script_dir = SCRIPT_DIR
    base_output_dir = os.path.join(script_dir, "output")
    os.makedirs(base_output_dir, exist_ok=True)

    gen = settings['generation']
    if 'max_level' in gen:
        levels = list(range(1, gen['max_level'] + 1))
    else:
        levels = gen['levels']
    gear_tiers = settings.get('gear_tiers', [{"name": "bad_gear", "label": "Bad Gear (Iron/Base)"}])

    # Filter builds if requested
    builds_source = settings['builds']
    if build_filter:
        builds_source = {k: v for k, v in builds_source.items() if v.get('generate', True) and k in build_filter}

    all_collected = OrderedDict()
    total_builds = sum(1 for b in builds_source.values() if b.get('generate', True)) * len(gear_tiers)
    workers = min(32, multiprocessing.cpu_count() or 8)

    for tier in gear_tiers:
        tier_name = tier['name']
        tier_label = tier['label']
        tier_dir = os.path.join(base_output_dir, tier_name)
        os.makedirs(tier_dir, exist_ok=True)

        builds = [(name, cfg, settings, levels, tier, tier_label)
                  for name, cfg in builds_source.items()]
        completed = 0

        tier_data = OrderedDict()
        all_level_data = []

        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_gen_one_build, args): args[0] for args in builds}
            for future in as_completed(futures):
                name, data = future.result()
                if data is not None:
                    tier_data[name] = data
                    all_level_data.append((name, data))
                completed += 1
                if progress_callback:
                    progress_callback(completed, total_builds, f"Generating {name} ({tier_label})...")

        tier_data = OrderedDict(sorted(tier_data.items()))
        all_level_data = sorted(all_level_data, key=lambda x: x[0])

        all_levels = sorted(set(
            lvl for _, bd in all_level_data for lvl in bd.keys()
        ))

        avg_data = {}
        for lvl in all_levels:
            avg_data[lvl] = {}
            for stat in ALL_STATS:
                vals = [bd[lvl][stat] for _, bd in all_level_data if lvl in bd]
                if vals:
                    avg_data[lvl][stat] = int(round(sum(vals) / len(vals)))
                else:
                    avg_data[lvl][stat] = 0

        tier_data['__average__'] = avg_data
        all_collected[tier_name] = tier_data

    if progress_callback:
        progress_callback(total_builds, total_builds, "Done!")

    return all_collected


class CharacterManagerGUI:
    UPCAST_RULES = {}
    _upcast_initialized = False

    def __init__(self, root):
        self.root = root
        self.root.title("Eyum TTRPG Character Manager - Balance Visualizer")
        self.root.geometry("1400x900")
        self.root.minsize(1000, 650)
        self._apply_dark_theme()

        self.data = None
        self.current_tier = None
        self.current_stat = 'Dmg/Turn'
        self.settings = None
        self.original_backups = {}
        self.generating = False
        self.editor_dirty = {}
        self.editor_buffers = {}
        self.current_file = None
        self.settings_dir = DATA_DIR

        self._hover_line = None
        self._vline = None
        self._tooltip = None
        self._lines = {}
        self._line_visible = {}
        self._build_enabled = {}
        self._build_names = []
        self._focused_line_name = None
        self._selected_level = None
        self._click_annotation = None
        self._click_marker = None
        self._level_limit_enabled = False
        self._affinity_markers = []
        self._max_level = 30

        self._spell_data = None
        self._spell_rules = None
        self._spell_zoomed = False
        self._spell_lines = []
        self._spell_line_data = {}
        self._spell_legend_entries = []
        self._spell_click_annotation = None
        self._spell_visibility = {}

        self._build_notebook()
        self._create_graph_tab()
        self._create_spell_tab()
        self._create_equipment_tab()
        self._create_settings_tab()
        self._create_menu()

        create_backup()
        self.original_backups = get_original_backup()

        self.root.after(500, self._initial_generate)

    def _apply_dark_theme(self):
        DARK_BG = '#1b1b1b'
        DARK_FG = '#e0e0e0'
        DARK_ENTRY = '#2b2b2b'
        DARK_BUTTON = '#333333'
        DARK_SELECT = '#264f78'

        self.root.configure(bg=DARK_BG)
        self.root.option_add('*background', DARK_BG)
        self.root.option_add('*foreground', DARK_FG)
        self.root.option_add('*selectBackground', DARK_SELECT)
        self.root.option_add('*selectForeground', '#ffffff')

        self.root.option_add('*Entry.background', DARK_ENTRY)
        self.root.option_add('*Entry.foreground', DARK_FG)
        self.root.option_add('*Entry.insertBackground', DARK_FG)
        self.root.option_add('*Entry.highlightBackground', DARK_SELECT)
        self.root.option_add('*Entry.highlightColor', DARK_SELECT)

        self.root.option_add('*Listbox.background', DARK_ENTRY)
        self.root.option_add('*Listbox.foreground', DARK_FG)

        self.root.option_add('*Text.background', DARK_ENTRY)
        self.root.option_add('*Text.foreground', DARK_FG)
        self.root.option_add('*Text.insertBackground', DARK_FG)

        self.root.option_add('*Canvas.background', DARK_BG)
        self.root.option_add('*Canvas.highlightBackground', DARK_BG)
        self.root.option_add('*Canvas.highlightThickness', 0)

        self.root.option_add('*Scale.background', DARK_BG)
        self.root.option_add('*Scale.troughColor', DARK_ENTRY)

        self.root.option_add('*Scrollbar.background', DARK_BUTTON)
        self.root.option_add('*Scrollbar.troughColor', DARK_ENTRY)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', background=DARK_BG, foreground=DARK_FG)
        style.configure('TFrame', background=DARK_BG)
        style.configure('TLabel', background=DARK_BG, foreground=DARK_FG)
        style.configure('TButton', background=DARK_BUTTON, foreground=DARK_FG, borderwidth=1)
        style.map('TButton', background=[('active', DARK_SELECT)])
        style.configure('TCheckbutton', background=DARK_BG, foreground=DARK_FG)
        style.configure('TEntry', fieldbackground=DARK_ENTRY, foreground=DARK_FG)
        style.configure('TCombobox', fieldbackground=DARK_ENTRY, background=DARK_BUTTON, foreground=DARK_FG)
        style.map('TCombobox', fieldbackground=[('readonly', DARK_ENTRY)])
        style.configure('TProgressbar', background=DARK_SELECT, troughcolor=DARK_ENTRY)
        style.configure('TSeparator', background='#444')
        style.configure('TNotebook', background=DARK_BG, borderwidth=0)
        style.configure('TNotebook.Tab', background=DARK_BUTTON, foreground=DARK_FG, padding=[10,2])
        style.map('TNotebook.Tab', background=[('selected', DARK_SELECT)])
        style.configure('TPanedWindow', background=DARK_BG)
        style.configure('TScale', background=DARK_BG, troughcolor=DARK_ENTRY)
        style.configure('TSpinbox', fieldbackground=DARK_ENTRY, foreground=DARK_FG)
        style.configure('TLabelframe', background=DARK_BG, foreground=DARK_FG)
        style.configure('TLabelframe.Label', background=DARK_BG, foreground=DARK_FG)

        plt.rcParams.update({
            'figure.facecolor': DARK_BG,
            'axes.facecolor': '#252525',
            'axes.edgecolor': '#555',
            'axes.labelcolor': DARK_FG,
            'text.color': DARK_FG,
            'xtick.color': '#999',
            'ytick.color': '#999',
            'grid.color': '#3a3a3a',
            'grid.alpha': 0.3,
            'legend.facecolor': '#2b2b2b',
            'legend.edgecolor': '#555',
        })
        global AVG_LINE_COLOR
        AVG_LINE_COLOR = '#aaaaaa'

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

    def _create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Run Generator", command=self._run_generator_from_ui, accelerator="Ctrl+R")
        file_menu.add_separator()
        file_menu.add_command(label="Switch to Graph View", command=lambda: self.notebook.select(0), accelerator="Ctrl+G")
        file_menu.add_command(label="Switch to Spell Analysis", command=lambda: self.notebook.select(1), accelerator="Ctrl+S")
        file_menu.add_command(label="Switch to Equipment Analyzer", command=lambda: self.notebook.select(2), accelerator="Ctrl+W")
        file_menu.add_command(label="Switch to Settings", command=lambda: self.notebook.select(3), accelerator="Ctrl+T")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Graph View", command=lambda: self.notebook.select(0), accelerator="Ctrl+G")
        view_menu.add_command(label="Spell Analysis", command=lambda: self.notebook.select(1), accelerator="Ctrl+S")
        view_menu.add_command(label="Equipment Analyzer", command=lambda: self.notebook.select(2), accelerator="Ctrl+W")
        view_menu.add_command(label="Settings Editor", command=lambda: self.notebook.select(3), accelerator="Ctrl+T")

        gen_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Generate", menu=gen_menu)
        gen_menu.add_command(label="Run Generator Now", command=self._run_generator_from_ui, accelerator="Ctrl+R")
        gen_menu.add_command(label="Settings → Run Generator", command=lambda: self._settings_run(keep_changes=False))

        self.root.bind_all('<Control-g>', lambda e: self.notebook.select(0))
        self.root.bind_all('<Control-s>', lambda e: self.notebook.select(1))
        self.root.bind_all('<Control-w>', lambda e: self.notebook.select(2))
        self.root.bind_all('<Control-t>', lambda e: self.notebook.select(3))

    def _create_graph_tab(self):
        self.graph_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.graph_frame, text="Graph View")

        toolbar_frame = ttk.Frame(self.graph_frame)
        toolbar_frame.pack(fill=tk.X, padx=5, pady=3)

        ttk.Label(toolbar_frame, text="Y-Axis:").pack(side=tk.LEFT, padx=5)
        self.stat_var = tk.StringVar(value='Dmg/Turn')
        self.stat_combo = ttk.Combobox(
            toolbar_frame, textvariable=self.stat_var,
            values=list(ALL_STATS), state='readonly', width=22
        )
        self.stat_combo.pack(side=tk.LEFT, padx=5)
        self.stat_combo.bind('<<ComboboxSelected>>', lambda e: self._update_graph())

        ttk.Label(toolbar_frame, text="Gear Tier:").pack(side=tk.LEFT, padx=(20, 5))
        self.tier_var = tk.StringVar()
        self.tier_combo = ttk.Combobox(
            toolbar_frame, textvariable=self.tier_var,
            state='readonly', width=22
        )
        self.tier_combo.pack(side=tk.LEFT, padx=5)
        self.tier_combo.bind('<<ComboboxSelected>>', lambda e: self._update_graph())

        ttk.Separator(toolbar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=15)

        self.run_btn = ttk.Button(
            toolbar_frame, text="▶ Run Generator",
            command=self._run_generator_from_ui
        )
        self.run_btn.pack(side=tk.LEFT, padx=5)

        self.progress_bar = ttk.Progressbar(
            toolbar_frame, mode='determinate', length=150
        )
        self.progress_bar.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(toolbar_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT, padx=5)

        ttk.Separator(toolbar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Label(toolbar_frame, text="Max Level:").pack(side=tk.LEFT, padx=2)
        self.level_slider = ttk.Scale(
            toolbar_frame, from_=1, to=150, orient=tk.HORIZONTAL,
            length=120, value=30
        )
        self.level_slider.pack(side=tk.LEFT, padx=2)
        self.level_slider_label = ttk.Label(toolbar_frame, text="30")
        self.level_slider_label.pack(side=tk.LEFT, padx=2)
        self.level_slider.config(command=self._on_slider_change)

        ttk.Separator(toolbar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        self.update_spells_btn = ttk.Button(
            toolbar_frame, text="⟳ Update Spells",
            command=self._update_spells_and_regen
        )
        self.update_spells_btn.pack(side=tk.LEFT, padx=5)

        main_pane = ttk.PanedWindow(self.graph_frame, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        graph_side = ttk.Frame(main_pane)
        main_pane.add(graph_side, weight=1)

        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.fig.subplots_adjust(left=0.08, right=0.97, top=0.95, bottom=0.08)

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_side)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        nav_frame = ttk.Frame(graph_side)
        nav_frame.pack(fill=tk.X)
        self.nav_toolbar = NavigationToolbar2Tk(self.canvas, nav_frame)
        self.nav_toolbar.update()

        self._setup_interactions()

        self.legend_frame = ttk.Frame(main_pane)
        main_pane.add(self.legend_frame, weight=0)

        ttk.Label(self.legend_frame, text="Legend", font=('', 9, 'bold')).pack(anchor=tk.W, padx=3, pady=2)

        self.legend_canvas = tk.Canvas(self.legend_frame, width=200, highlightthickness=0)
        self.legend_scroll = ttk.Scrollbar(self.legend_frame, orient=tk.VERTICAL, command=self.legend_canvas.yview)
        self.legend_inner = ttk.Frame(self.legend_canvas)

        self.legend_inner.bind('<Configure>', lambda e: self.legend_canvas.configure(
            scrollregion=(0, 0, self.legend_inner.winfo_reqwidth(), self.legend_inner.winfo_reqheight())
        ))
        self.legend_canvas.create_window((0, 0), window=self.legend_inner, anchor='nw', tags='inner')
        self.legend_canvas.configure(yscrollcommand=self.legend_scroll.set)

        self.legend_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.legend_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._bind_scrollwheel(self.legend_canvas)

    def _create_settings_tab(self):
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings Editor")

        main_pane = ttk.PanedWindow(self.settings_frame, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_pane, width=220)
        main_pane.add(left_frame, weight=0)

        ttk.Label(left_frame, text="Data Files", font=('', 10, 'bold')).pack(anchor=tk.W, padx=5, pady=3)

        self.file_listbox = tk.Listbox(left_frame, exportselection=False,
                                        bg='#2b2b2b', fg='#e0e0e0', selectbackground='#264f78')
        self.file_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)
        for fname in JSON_FILES:
            self.file_listbox.insert(tk.END, fname)
        self.file_listbox.bind('<<ListboxSelect>>', self._on_file_select)

        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=1)

        editor_toolbar = ttk.Frame(right_frame)
        editor_toolbar.pack(fill=tk.X, pady=(0, 3))

        def make_btn(text, cmd, **kw):
            return ttk.Button(editor_toolbar, text=text, command=cmd, **kw)

        self.settings_run_btn = make_btn("▶ Run Generator (Keep Changes)", lambda: self._settings_run(keep_changes=True))
        self.settings_run_btn.pack(side=tk.LEFT, padx=2)

        self.settings_run_temp_btn = make_btn("▶ Run Generator (Temporary)", lambda: self._settings_run(keep_changes=False))
        self.settings_run_temp_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(editor_toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.save_btn = make_btn("💾 Save", self._settings_save)
        self.save_btn.pack(side=tk.LEFT, padx=2)

        self.restore_btn = make_btn("↩ Restore Originals", self._settings_restore)
        self.restore_btn.pack(side=tk.LEFT, padx=2)

        self.settings_progress = ttk.Progressbar(editor_toolbar, mode='determinate', length=100)
        self.settings_progress.pack(side=tk.LEFT, padx=5)

        self.settings_status = ttk.Label(editor_toolbar, text="")
        self.settings_status.pack(side=tk.LEFT, padx=5)

        self.editor_text = tk.Text(right_frame, wrap=tk.NONE, font=('Courier', 10),
                                    bg='#2b2b2b', fg='#e0e0e0', insertbackground='#e0e0e0')
        self.editor_text.pack(fill=tk.BOTH, expand=True)

        self.editor_text.bind('<KeyRelease>', self._on_editor_change)

        h_scroll = ttk.Scrollbar(right_frame, orient=tk.HORIZONTAL, command=self.editor_text.xview)
        v_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.editor_text.yview)
        self.editor_text.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        h_scroll.pack(fill=tk.X)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    LINE_STYLES = ['solid', 'dashed', 'dotted', 'dashdot', (0, (3, 1, 1, 1))]

    def _create_spell_tab(self):
        self.spell_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.spell_frame, text="Spell Analysis")

        panes = ttk.PanedWindow(self.spell_frame, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(panes, width=300)
        panes.add(left_frame, weight=0)

        canvas_frame = ttk.Frame(left_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.spell_control_canvas = tk.Canvas(canvas_frame, width=280, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.spell_control_canvas.yview)
        self.spell_control_inner = ttk.Frame(self.spell_control_canvas)

        self.spell_control_inner.bind('<Configure>', lambda e: self.spell_control_canvas.configure(
            scrollregion=self.spell_control_canvas.bbox('all')
        ))
        self.spell_control_canvas.create_window((0, 0), window=self.spell_control_inner, anchor='nw', tags='inner')
        self.spell_control_canvas.configure(yscrollcommand=scrollbar.set)
        self.spell_control_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._bind_scrollwheel(self.spell_control_canvas)

        controls = self.spell_control_inner

        ttk.Label(controls, text="Spell Parameters", font=('', 10, 'bold')).pack(anchor=tk.W, padx=5, pady=(8, 2))

        f1 = ttk.Frame(controls)
        f1.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(f1, text="Max Mana:").pack(side=tk.LEFT)
        self._spell_mana_var = tk.StringVar(value="100")
        self._spell_mana_entry = ttk.Entry(f1, textvariable=self._spell_mana_var, width=8)
        self._spell_mana_entry.pack(side=tk.RIGHT)
        self._spell_mana_entry.bind('<Return>', lambda e: self._refresh_spell_graph())
        self._spell_mana_entry.bind('<FocusOut>', lambda e: self._refresh_spell_graph())

        f2 = ttk.Frame(controls)
        f2.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(f2, text="Target Count:").pack(side=tk.LEFT)
        self._spell_target_label = ttk.Label(f2, text="1")
        self._spell_target_label.pack(side=tk.RIGHT)
        self._spell_target_var = tk.IntVar(value=1)
        self._spell_target_scale = ttk.Scale(controls, from_=1, to=20, orient=tk.HORIZONTAL,
                                              variable=self._spell_target_var)
        self._spell_target_scale.pack(fill=tk.X, padx=5, pady=(0, 2))
        self._spell_target_scale.config(command=self._on_spell_target_change)

        f2b = ttk.Frame(controls)
        f2b.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(f2b, text="Max Rounds:").pack(side=tk.LEFT)
        self._spell_rounds_label = ttk.Label(f2b, text="10")
        self._spell_rounds_label.pack(side=tk.RIGHT)
        self._spell_rounds_var = tk.IntVar(value=10)
        self._spell_rounds_scale = ttk.Scale(controls, from_=1, to=100, orient=tk.HORIZONTAL,
                                              variable=self._spell_rounds_var)
        self._spell_rounds_scale.pack(fill=tk.X, padx=5, pady=(0, 2))
        self._spell_rounds_scale.config(command=self._on_spell_rounds_change)

        fup = ttk.Frame(controls)
        fup.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(fup, text="Upcasts:").pack(side=tk.LEFT)
        self._spell_upcast_label = ttk.Label(fup, text="0")
        self._spell_upcast_label.pack(side=tk.RIGHT)
        self._spell_upcast_var = tk.IntVar(value=0)
        self._spell_upcast_scale = ttk.Scale(controls, from_=0, to=5, orient=tk.HORIZONTAL,
                                              variable=self._spell_upcast_var)
        self._spell_upcast_scale.pack(fill=tk.X, padx=5, pady=(0, 2))
        self._spell_upcast_scale.config(command=lambda v: (self._spell_upcast_label.config(text=str(int(float(v)))), self._refresh_spell_graph()))

        f3 = ttk.Frame(controls)
        f3.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(f3, text="Damage Modifier:").pack(side=tk.LEFT)
        self._spell_dmg_mod_var = tk.StringVar(value="0")
        self._spell_dmg_mod_entry = ttk.Entry(f3, textvariable=self._spell_dmg_mod_var, width=8)
        self._spell_dmg_mod_entry.pack(side=tk.RIGHT)
        self._spell_dmg_mod_entry.bind('<Return>', lambda e: self._refresh_spell_graph())
        self._spell_dmg_mod_entry.bind('<FocusOut>', lambda e: self._refresh_spell_graph())

        self._spell_affinity_vars = {}
        self._spell_affinity_entries = {}
        ttk.Label(controls, text="Affinity Values", font=('', 9, 'bold')).pack(anchor=tk.W, padx=5, pady=(6, 2))
        base_affs = ['Fire', 'Earth', 'Water', 'Air', 'Necrotic', 'Radiant', 'Psychic', 'Generic', 'Eldritch']
        for aff in base_affs:
            f = ttk.Frame(controls)
            f.pack(fill=tk.X, padx=5, pady=1)
            ttk.Label(f, text=aff, width=10, anchor=tk.W).pack(side=tk.LEFT)
            v = tk.StringVar(value="0")
            e = ttk.Entry(f, textvariable=v, width=6)
            e.pack(side=tk.RIGHT)
            e.bind('<Return>', lambda e: self._refresh_spell_graph())
            e.bind('<FocusOut>', lambda e: self._refresh_spell_graph())
            self._spell_affinity_vars[aff] = v
            self._spell_affinity_entries[aff] = e

        ttk.Separator(controls, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=6)

        ttk.Label(controls, text="Mana Blast Affinity", font=('', 9, 'bold')).pack(anchor=tk.W, padx=5, pady=2)
        self._spell_mb_affinity_var = tk.StringVar(value="None")
        self._spell_mb_affinity_combo = ttk.Combobox(controls, textvariable=self._spell_mb_affinity_var,
                                                       state='readonly', width=22)
        self._spell_mb_affinity_combo.pack(fill=tk.X, padx=5, pady=2)

        ttk.Separator(controls, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=6)

        self._spell_show_healing_var = tk.BooleanVar(value=True)
        self._spell_leveled_only_var = tk.BooleanVar(value=False)

        ttk.Separator(controls, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=6)

        ttk.Label(controls, text="Character Bonuses", font=('', 10, 'bold')).pack(anchor=tk.W, padx=5, pady=(8, 2))

        fk = ttk.Frame(controls)
        fk.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(fk, text="Karma:").pack(side=tk.LEFT)
        self._spell_karma_var = tk.StringVar(value="0")
        self._spell_karma_entry = ttk.Entry(fk, textvariable=self._spell_karma_var, width=8)
        self._spell_karma_entry.pack(side=tk.RIGHT)
        self._spell_karma_entry.bind('<Return>', lambda e: self._refresh_spell_graph())
        self._spell_karma_entry.bind('<FocusOut>', lambda e: self._refresh_spell_graph())

        ttk.Label(controls, text="Eldritch Horror", font=('', 9)).pack(anchor=tk.W, padx=5, pady=(6, 1))
        self._spell_eldritch_vars = {}
        eldritch_toggles = [
            ('Blast 3 dmg (L2)', 'e_l2'),
            ('Blast costs 1 mana (L4)', 'e_l4'),
            ('Curse: 5 dmg/turn (L6.5)', 'e_l65'),
            ('Blast 6 dmg (L7)', 'e_l7'),
            ('3 beams (L8)', 'e_l8'),
            ('+25% all Eldritch (L11)', 'e_l11'),
            ('+50% via Shadow (L14)', 'e_l14'),
            ('Curse: 20 dmg/turn (L13)', 'e_l13'),
            ('+25% all Eldritch (L18)', 'e_l18'),
            ('+25% + karma/5 (L20)', 'e_l20'),
        ]
        for label, key in eldritch_toggles:
            v = tk.BooleanVar(value=False)
            self._spell_eldritch_vars[key] = v
            ttk.Checkbutton(controls, text=label, variable=v, command=self._refresh_spell_graph).pack(anchor=tk.W, padx=20, pady=0)

        aff_bonuses = [('Pyromancer +1d4 Fire', 'fire_bonus'), ('Geomancer +1d4 Earth', 'earth_bonus'),
                       ('Tidemaster +1d4 Water', 'water_bonus'), ('Windwalker +1d4 Air', 'air_bonus'),
                       ('Priest +1d4 Radiant', 'radiant_bonus'), ('Necromancer +1d4 Necrotic', 'necrotic_bonus')]
        ttk.Label(controls, text="Affinity Archetypes", font=('', 9)).pack(anchor=tk.W, padx=5, pady=(6, 1))
        self._spell_bonus_vars = {}
        for label, key in aff_bonuses:
            v = tk.BooleanVar(value=False)
            self._spell_bonus_vars[key] = v
            ttk.Checkbutton(controls, text=label, variable=v, command=self._refresh_spell_graph).pack(anchor=tk.W, padx=20, pady=0)

        feat_bonuses = [('Static Discharge: +1d6 Lightning', 'feat_static'),
                        ('Holy Radiance: +1d6 Radiant', 'feat_holy'),
                        ('Lingering Shadow: +5 Necrotic', 'feat_shadow'),
                        ('Explosive Power: +5 if 3+ tgt', 'feat_explosive'),
                        ('Chain Lightning: +1 target', 'feat_chain'),
                        ('Mind Spike: Psychic→HP', 'feat_mindspike'),
                        ('Firebrand: Fire +On Fire', 'feat_firebrand'),
                        ('Healer: Healing ×1.5', 'feat_healer')]
        ttk.Label(controls, text="Feats & Abilities", font=('', 9)).pack(anchor=tk.W, padx=5, pady=(6, 1))
        self._spell_feat_vars = {}
        for label, key in feat_bonuses:
            v = tk.BooleanVar(value=False)
            self._spell_feat_vars[key] = v
            ttk.Checkbutton(controls, text=label, variable=v, command=self._refresh_spell_graph).pack(anchor=tk.W, padx=20, pady=0)

        ttk.Separator(controls, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=8)

        self._spell_refresh_btn = ttk.Button(controls, text="Refresh Graph",
                                              command=self._refresh_spell_graph)
        self._spell_refresh_btn.pack(fill=tk.X, padx=5, pady=(4, 0))

        self._spell_zoom_reset_btn = ttk.Button(controls, text="Reset Zoom",
                                                 command=self._reset_spell_zoom)
        self._spell_zoom_reset_btn.pack(fill=tk.X, padx=5, pady=(2, 4))

        right_frame = ttk.Frame(panes)
        panes.add(right_frame, weight=1)

        graph_frame = ttk.Frame(right_frame)
        graph_frame.pack(fill=tk.BOTH, expand=True)

        self._spell_fig, self._spell_ax = plt.subplots(figsize=(10, 5))
        self._spell_fig.subplots_adjust(left=0.08, right=0.97, top=0.95, bottom=0.08)

        self._spell_canvas = FigureCanvasTkAgg(self._spell_fig, master=graph_frame)
        self._spell_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self._spell_canvas.mpl_connect('button_press_event', self._on_spell_click)
        self._spell_canvas.mpl_connect('scroll_event', self._on_spell_scroll)
        self._spell_pan_data = None
        self._spell_canvas.mpl_connect('button_press_event', self._on_spell_pan_press)
        self._spell_canvas.mpl_connect('motion_notify_event', self._on_spell_pan_move)
        self._spell_canvas.mpl_connect('button_release_event', self._on_spell_pan_release)

        self._spell_bottom_frame = ttk.Frame(right_frame)
        self._spell_bottom_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self._spell_legend_frame = ttk.LabelFrame(self._spell_bottom_frame, text="Spell Legend")
        self._spell_legend_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._spell_legend_canvas = tk.Canvas(self._spell_legend_frame, height=160, highlightthickness=0)
        self._spell_legend_scroll = ttk.Scrollbar(self._spell_legend_frame, orient=tk.VERTICAL,
                                                    command=self._spell_legend_canvas.yview)
        self._spell_legend_inner = ttk.Frame(self._spell_legend_canvas)

        self._spell_legend_inner.bind('<Configure>', lambda e: self._spell_legend_canvas.configure(
            scrollregion=(0, 0, self._spell_legend_inner.winfo_reqwidth(), self._spell_legend_inner.winfo_reqheight())
        ))
        self._spell_legend_canvas.create_window((0, 0), window=self._spell_legend_inner, anchor='nw', tags='inner')
        self._spell_legend_canvas.configure(yscrollcommand=self._spell_legend_scroll.set)

        self._spell_legend_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._spell_legend_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._bind_scrollwheel(self._spell_legend_canvas)

        self._spell_summary_frame = ttk.LabelFrame(self._spell_bottom_frame, text="Summary", width=200)
        self._spell_summary_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(3, 0))
        self._spell_summary_frame.pack_propagate(False)
        self._spell_summary_text = tk.Text(self._spell_summary_frame, font=('', 8), wrap=tk.WORD,
                                            state=tk.DISABLED, height=12, borderwidth=0, bg='#252525', fg='#d4d4d4')
        self._spell_summary_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

        self._load_spell_session()
        self.root.after(100, self._refresh_spell_graph)

    def _on_spell_target_change(self, val):
        self._spell_target_label.config(text=str(int(float(val))))
        self._refresh_spell_graph()

    def _on_spell_rounds_change(self, val):
        self._spell_rounds_label.config(text=str(int(float(val))))
        self._refresh_spell_graph()

    def _load_spell_data(self):
        if self._spell_data is not None and self._spell_rules is not None:
            return
        spells_path = os.path.join(DATA_DIR, 'spells.json')
        rules_path = os.path.join(DATA_DIR, 'rules.json')
        try:
            with open(spells_path, 'r') as f:
                self._spell_data = json.load(f)
        except Exception:
            self._spell_data = {}
        try:
            with open(rules_path, 'r') as f:
                self._spell_rules = json.load(f)
        except Exception:
            self._spell_rules = {}

    def _get_die_average(self, die_str, die_averages):
        if die_str in die_averages:
            return die_averages[die_str]
        import re
        m = re.match(r'^(\d+)d(\d+)$', die_str)
        if m:
            count = int(m.group(1))
            sides = int(m.group(2))
            return count * (sides / 2.0 + 0.5)
        return 0

    def _parse_formula(self, formula_str, affinity_value):
        sanitized = formula_str.replace(' ', '')
        try:
            safe = sanitized.replace('affinity_mod', str(affinity_value))
            result = eval(safe, {"__builtins__": {}}, {})
            return float(result)
        except Exception:
            return 0

    def _get_spell_damage_per_cast(self, spell, die_averages, base_dmg_mod, affinity_values, target_count, affinity):
        damage = base_dmg_mod

        if spell.get('damage_formula'):
            aff_val = affinity_values.get(affinity, affinity_values.get('Generic', 0))
            damage += self._parse_formula(spell['damage_formula'], aff_val)

        if spell.get('damage_dice'):
            damage += self._get_die_average(spell['damage_dice'], die_averages)

        if spell.get('damage_flat'):
            damage += spell['damage_flat']

        has_aoe = spell.get('aoe_radius', 0) or spell.get('aoe_cone') or spell.get('aoe_line') or spell.get('aoe_self')
        if has_aoe and target_count > 1:
            damage *= target_count

        return damage

    def _get_spell_bonus(self, affinity, spell_name, die_averages, target_count):
        bonus = 0

        aff_bonus_map = {
            'Fire': self._spell_bonus_vars.get('fire_bonus', tk.BooleanVar(value=False)),
            'Earth': self._spell_bonus_vars.get('earth_bonus', tk.BooleanVar(value=False)),
            'Water': self._spell_bonus_vars.get('water_bonus', tk.BooleanVar(value=False)),
            'Air': self._spell_bonus_vars.get('air_bonus', tk.BooleanVar(value=False)),
            'Radiant': self._spell_bonus_vars.get('radiant_bonus', tk.BooleanVar(value=False)),
            'Necrotic': self._spell_bonus_vars.get('necrotic_bonus', tk.BooleanVar(value=False)),
        }
        if affinity in aff_bonus_map and aff_bonus_map[affinity].get():
            bonus += die_averages.get('1d4', 2.5)

        feat_vars = self._spell_feat_vars
        if affinity == 'Lightning' and feat_vars.get('feat_static', tk.BooleanVar()).get():
            bonus += die_averages.get('1d6', 3.5)
        if affinity == 'Radiant' and feat_vars.get('feat_holy', tk.BooleanVar()).get():
            bonus += die_averages.get('1d6', 3.5)
        if affinity == 'Necrotic' and feat_vars.get('feat_shadow', tk.BooleanVar()).get():
            bonus += 5
        if target_count >= 3 and feat_vars.get('feat_explosive', tk.BooleanVar()).get():
            bonus += 5
        if affinity == 'Lightning' and feat_vars.get('feat_chain', tk.BooleanVar()).get():
            if target_count < 2:
                bonus += die_averages.get('3d6', 10.5)

        ev = getattr(self, '_spell_eldritch_vars', {})
        if affinity == 'Eldritch':
            try:
                karma = float(self._spell_karma_var.get())
            except ValueError:
                karma = 0
            if 'Eldritch Blast' in spell_name:
                base_dmg = 1
                if ev.get('e_l2', tk.BooleanVar()).get():
                    base_dmg = 3
                if ev.get('e_l7', tk.BooleanVar()).get():
                    base_dmg = 6
                bonus += base_dmg
            if ev.get('e_l65', tk.BooleanVar()).get():
                curse_base = 5
                if ev.get('e_l13', tk.BooleanVar()).get():
                    curse_base = 20
                bonus += self.CONDITION_DMG.get('Eldritch Curse', (0, 2))[1] * curse_base
            if ev.get('e_l20', tk.BooleanVar()).get():
                bonus += abs(karma) / 10

        eld_mult = 1.0
        if affinity == 'Eldritch':
            if ev.get('e_l11', tk.BooleanVar()).get():
                eld_mult += 0.25
            if ev.get('e_l14', tk.BooleanVar()).get():
                eld_mult += 0.50
            if ev.get('e_l18', tk.BooleanVar()).get():
                eld_mult += 0.25
            if ev.get('e_l20', tk.BooleanVar()).get():
                eld_mult += 0.25

        beams = 1
        if 'Eldritch Blast' in spell_name and ev.get('e_l8', tk.BooleanVar()).get():
            beams = 3

        if affinity == 'Healing' and feat_vars.get('feat_healer', tk.BooleanVar()).get():
            return bonus, 1.5, beams, eld_mult

        return bonus, 1.0, beams, eld_mult

    def _get_upcast_dice(self, affinity, spell_name, die_averages):
        if not CharacterManagerGUI._upcast_initialized:
            CharacterManagerGUI.UPCAST_RULES = {
                'Mana Decimation': (2, 30, None),
            'Cataclysm Pyre': (2, die_averages.get('3d6',10.5) + die_averages.get('1d6',3.5), None),
            'Worldbreak': (2, die_averages.get('2d6',7), None),
            'Maelstrom': (2, die_averages.get('2d6',7) + die_averages.get('1d6',3.5), None),
            'Sky Rend': (2, die_averages.get('2d6',7), None),
            'Necrotic Collapse': (2, die_averages.get('3d6',10.5), None),
            'Ascension Nova': (2, die_averages.get('3d6',10.5), None),
            'Ego Shatter': (2, die_averages.get('2d6',7), None),
            'Judgment Strike': (2, die_averages.get('10d8',45) + die_averages.get('8d8',36), None),
            'Frozen Cataclysm': (2, die_averages.get('3d6',10.5), None),
            'Singularity Core': (2, die_averages.get('4d8',18), None),
            'Plaguefall': (2, die_averages.get('10d8',45) + die_averages.get('4d8',18), None),
            'Ruin of the Soul': (2, die_averages.get('12d8',54), None),
            'Red Cataclysm': (2, die_averages.get('12d8',54) + die_averages.get('6d8',27), None),
            'Worldforge Collapse': (2, die_averages.get('8d8',36), None),
            'Solar Cataclysm': (2, die_averages.get('8d10',44) + die_averages.get('4d10',22), None),
            'Terminal Nova': (2, die_averages.get('12d12',78), None),
            'Heavenfall Pattern': (2, die_averages.get('4d8',18), None),
            'Swallowing Fen': (2, die_averages.get('3d8',13.5), None),
            'Burial Wind': (2, die_averages.get('3d8',13.5), None),
            'Engine Rupture': (2, die_averages.get('4d8',18) + die_averages.get('2d8',9), None),
            'Caldera Break': (2, die_averages.get('4d8',18) + die_averages.get('2d8',9), None),
            'Black Sky': (2, die_averages.get('3d8',13.5), None),
            'Final Season': (2, die_averages.get('4d8',18), None),
            'Suffocation Engine': (2, die_averages.get('4d8',18) + die_averages.get('2d8',9), None),
            'Collapse Identity': (2, die_averages.get('5d8',22.5), None),
            'Last Lament': (2, die_averages.get('3d8',13.5), None),
            'Disorder Engine': (2, die_averages.get('2d8',9), None),
            'Dislocation Gate': (2, die_averages.get('4d8',18), None),
            'Ruin Chime': (2, die_averages.get('4d8',18), None),
            'World Tempest': (2, 0, None),
            'Oblivion Cut': (2, die_averages.get('6d8',27), None),
            'Black Monolith': (2, die_averages.get('4d8',18), None),
            'Continental Break': (2, die_averages.get('4d8',18), None),
            'Thronefire': (2, die_averages.get('4d8',18) + die_averages.get('2d8',9), None),
            'Breakwater': (2, die_averages.get('4d8',18), None),
            'Rot Kingdom': (2, die_averages.get('5d8',22.5), None),
                'Last Sun': (3, 100 + die_averages.get('6d20',63), None),
            }
            CharacterManagerGUI._upcast_initialized = True
        rule = CharacterManagerGUI.UPCAST_RULES.get(spell_name, (2, die_averages.get('2d6',7), None))
        return rule[1]

    CONDITION_DMG = {
        'Burned': (2.5, 2), 'Burn': (2.5, 2), 'On Fire': (3.5, 3),
        'Bleeding': (2.5, 3), 'Bleed': (2.5, 3),
        'Necrosis': (4.5, 3), 'Diseased': (3.5, 2),
        'Shocked': (2.5, 2), 'Poisoned': (7.0, 3),
        'Corrupt': (2.5, 3), 'Hurting': (1.0, 3),
        'Suffocating': (3.5, 2), 'Frozen': (2.5, 2),
        'Slow Death': (2.5, 3), 'Frostbitten': (2.5, 3),
        'Hellfire': (4.5, 2), 'Radiation': (3.5, 3),
        'Withered': (7.5, 2), 'Plagued': (6.0, 3),
        'Eldritch Curse': (0, 2),
        'Psychic Drain': (0, 2),
        'Storm Shocked': (2.5, 2),
        'Frostburned': (2.5, 3),
        'Taboo': (2.5, 3),
        'Prone': (0, 2), 'Slowed': (0, 2), 'Stunned': (0, 2),
        'Blinded': (0, 2), 'Mute': (0, 2), 'Deafened': (0, 2),
        'Frightened': (0, 2), 'Demoralized': (0, 2), 'Despair': (0, 2),
        'Enraged': (0, 2), 'Paralyzed': (0, 2), 'Petrified': (0, 2),
        'Entangled': (0, 2), 'Restrained': (0, 2), 'Pinned': (0, 2),
        'Blessed': (0, 2), 'Cursed': (0, 2), 'Soaked': (0, 2),
        'Difficult Terrain': (0, 2), 'Pierced': (0, 2), 'Push': (0, 0),
        'Pull': (0, 0), 'Heal': (0, 0), 'NoFlight': (0, 2),
        'NoAdvantage': (0, 2), 'DoT': (7.0, 2), 'GroundBurn': (7.0, 2),
        'Scaling': (0, 2), 'Collision': (0, 0),
    }

    def _get_condition_damage(self, spell, die_averages):
        extra = spell.get('extra_effect', '')
        if not extra:
            return 0, []
        total_dmg = 0
        conditions_found = []
        parts = [p.strip() for p in extra.split('+') if p.strip()]
        for part in parts:
            multiplier = 1
            cond_name = part
            if ' x' in part:
                cond_name, mult_str = part.rsplit(' x', 1)
                cond_name = cond_name.strip()
                try:
                    multiplier = int(mult_str.strip())
                except ValueError:
                    multiplier = 1
            if cond_name in self.CONDITION_DMG:
                dmg, dur = self.CONDITION_DMG[cond_name]
                total_dmg += dmg * dur * multiplier
                label = f'{cond_name} x{multiplier}' if multiplier > 1 else cond_name
                conditions_found.append(label)
        return total_dmg, conditions_found

    def _refresh_spell_graph(self):
        self._load_spell_data()
        self._spell_ax.clear()
        self._clear_spell_click_annotation()
        self._spell_zoomed = False
        self._spell_lines = []
        self._spell_line_data = {}
        self._spell_legend_entries = []

        if not self._spell_data:
            self._spell_ax.text(0.5, 0.5, 'No spell data available.',
                                transform=self._spell_ax.transAxes, ha='center', va='center', fontsize=14)
            self._spell_canvas.draw()
            return

        die_averages = self._spell_rules.get('die_averages', {}) if self._spell_rules else {}

        try:
            max_mana = float(self._spell_mana_var.get())
        except ValueError:
            max_mana = 100
        try:
            base_dmg_mod = float(self._spell_dmg_mod_var.get())
        except ValueError:
            base_dmg_mod = 0
        affinity_values = {}
        for aff, var in getattr(self, '_spell_affinity_vars', {}).items():
            try:
                affinity_values[aff] = float(var.get())
            except ValueError:
                affinity_values[aff] = 0

        target_count = self._spell_target_var.get()
        show_healing = self._spell_show_healing_var.get()
        leveled_only = self._spell_leveled_only_var.get()
        all_affinity_names = sorted([k for k in self._spell_data.keys() if k != 'Generic'])
        if 'Generic' in self._spell_data:
            all_affinity_names.append('Generic')

        self._spell_mb_affinity_combo['values'] = ['None'] + [a for a in all_affinity_names if a != 'Generic']

        mb_affinity = self._spell_mb_affinity_var.get()
        if mb_affinity not in ('None', '') + tuple(all_affinity_names):
            mb_affinity = 'None'

        affinities_to_show = all_affinity_names

        color_idx = 0
        family_colors = {}
        unique_spell_count = 0

        for aff_name in all_affinity_names:
            spells = self._spell_data.get(aff_name, [])
            chain_spells = spells[:5]
            extra_spells = spells[5:]
            family_colors[aff_name] = COLOR_CYCLE[color_idx % len(COLOR_CYCLE)]
            color_idx += 1
            for _ in extra_spells:
                unique_spell_count += 1

        spell_list = []
        for aff_name in affinities_to_show:
            spells = self._spell_data.get(aff_name, [])
            chain_spells = spells[:5]
            extra_spells = spells[5:]
            for i, spell in enumerate(chain_spells):
                has_damage = spell.get('damage_dice') or spell.get('damage_flat') or spell.get('damage_formula')
                if not has_damage and not show_healing:
                    continue
                is_healing = not has_damage and bool(spell.get('mana') or True)
                spell_list.append((aff_name, spell, True, i, is_healing))
            if not leveled_only:
                for i, spell in enumerate(extra_spells):
                    has_damage = spell.get('damage_dice') or spell.get('damage_flat') or spell.get('damage_formula')
                    if not has_damage and not show_healing:
                        continue
                    is_healing = not has_damage and bool(spell.get('mana') or True)
                    spell_list.append((aff_name, spell, False, i, is_healing))

        unique_color_idx = 0
        extra_color_map = {}
        for aff_name in all_affinity_names:
            extra_spells = self._spell_data.get(aff_name, [])[5:]
            for s in extra_spells:
                key = (aff_name, s.get('name'))
                extra_color_map[key] = COLOR_CYCLE[(len(all_affinity_names) + unique_color_idx) % len(COLOR_CYCLE)]
                unique_color_idx += 1

        for aff_name, spell, is_chain, idx, is_healing in spell_list:
            if is_chain:
                color = family_colors[aff_name]
                linestyle = self.LINE_STYLES[idx % len(self.LINE_STYLES)]
            else:
                color = extra_color_map.get((aff_name, spell.get('name')), COLOR_CYCLE[0])
                linestyle = 'solid'

            dmg_per_cast = self._get_spell_damage_per_cast(spell, die_averages, base_dmg_mod, affinity_values, target_count, aff_name)

            bonus_aff = aff_name
            if spell.get('name', '').startswith('Mana'):
                mb_aff_sel = self._spell_mb_affinity_var.get()
                if mb_aff_sel and mb_aff_sel != 'None':
                    bonus_aff = mb_aff_sel
                    dmg_per_cast += affinity_values.get(mb_aff_sel, 0)

            bonus_dmg, heal_mult, beams, eld_mult = self._get_spell_bonus(bonus_aff, spell.get('name', ''), die_averages, target_count)
            dmg_per_cast = (dmg_per_cast + bonus_dmg) * eld_mult * heal_mult * beams

            mana_cost = spell.get('mana', 0)
            if spell.get('name') == 'Eldritch Blast' and getattr(self, '_spell_eldritch_vars', {}).get('e_l4', tk.BooleanVar()).get():
                mana_cost = 1
            upcasts = self._spell_upcast_var.get()
            if upcasts > 0 and mana_cost > 0 and is_chain:
                rule = CharacterManagerGUI.UPCAST_RULES.get(spell.get('name', ''), (2, die_averages.get('2d6',7), None))
                upcast_mult, upcast_dice, _ = rule
                mana_cost = int(mana_cost * (upcast_mult ** upcasts))
                dmg_per_cast += upcast_dice * upcasts

            cond_dmg, cond_list = self._get_condition_damage(spell, die_averages)
            dmg_per_cast += cond_dmg

            if mana_cost is None:
                mana_cost = 0

            max_display_rounds = self._spell_rounds_var.get()
            if mana_cost <= 0:
                max_rounds = max_display_rounds
            else:
                max_rounds = min(max_display_rounds, int(max_mana // mana_cost))

            rounds = list(range(max_rounds + 1))
            cumulative_dmg = [round(r * dmg_per_cast, 1) for r in rounds]

            label = f"{aff_name}: {spell['name']}"
            line, = self._spell_ax.plot(rounds, cumulative_dmg, color=color, linestyle=linestyle,
                                          linewidth=2, marker='o', markersize=3.5,
                                          markeredgecolor='#00000044',
                                          label='_nolegend_', picker=True, pickradius=5)
            self._spell_lines.append(line)
            self._spell_legend_entries.append((aff_name, spell['name'], color, linestyle, is_healing, is_chain))
            self._spell_line_data[line] = {
                'affinity': aff_name,
                'spell_name': spell['name'],
                'dmg_per_cast': dmg_per_cast,
                'mana_cost': mana_cost,
                'max_rounds': max_rounds,
                'is_healing': is_healing,
                'max_mana': max_mana,
                'upcasts': upcasts,
                'beams': beams,
                'conditions': cond_list,
                'cond_dmg': cond_dmg,
            }

        if not hasattr(self, '_spell_visibility'):
            self._spell_visibility = {}

        for line in self._spell_lines:
            ld = self._spell_line_data.get(line, {})
            key = (ld.get('affinity', ''), ld.get('spell_name', ''))
            if key in self._spell_visibility:
                line.set_visible(self._spell_visibility[key])

        self._rebuild_spell_legend()

        from matplotlib.ticker import MultipleLocator
        max_r = self._spell_rounds_var.get()
        step = 1 if max_r <= 20 else (2 if max_r <= 50 else (5 if max_r <= 100 else 10))
        self._spell_ax.xaxis.set_major_locator(MultipleLocator(step))

        self._spell_ax.set_xlabel('Round', fontsize=11)
        self._spell_ax.set_ylabel('Cumulative Damage', fontsize=11)
        self._spell_ax.set_title('Spell Damage Over Rounds', fontsize=13, fontweight='bold')
        self._spell_ax.tick_params(labelsize=9)
        for line in self._spell_lines:
            line.set_linewidth(2)
            line.set_alpha(1.0)
        for r in range(len(self._spell_lines[0].get_xdata()) if self._spell_lines else 0):
            y_count = {}
            for line in self._spell_lines:
                if r < len(line.get_ydata()):
                    y_count.setdefault(int(round(line.get_ydata()[r])), []).append(line)
            for overlap_lines in y_count.values():
                if len(overlap_lines) > 1:
                    for ol in overlap_lines:
                        ol.set_linewidth(3.5)
                        ol.set_alpha(0.55)

        self._spell_ax.set_xlim(left=0)
        self._spell_ax.set_ylim(bottom=0)
        self._auto_resize_spell_ylim()
        self._spell_canvas.draw()
        self._save_spell_session()

    def _save_spell_session(self):
        session = {
            'mana': self._spell_mana_var.get(),
            'target_count': self._spell_target_var.get(),
            'rounds': self._spell_rounds_var.get(),
            'dmg_mod': self._spell_dmg_mod_var.get(),
            'affinity_values': {k: v.get() for k, v in self._spell_affinity_vars.items()},
            'mb_affinity': self._spell_mb_affinity_var.get(),
            'karma': self._spell_karma_var.get(),
            'show_healing': self._spell_show_healing_var.get(),
            'leveled_only': self._spell_leveled_only_var.get(),
            'eldritch_vars': {k: v.get() for k, v in self._spell_eldritch_vars.items()},
            'bonus_vars': {k: v.get() for k, v in self._spell_bonus_vars.items()},
            'feat_vars': {k: v.get() for k, v in self._spell_feat_vars.items()},
            'upcasts': self._spell_upcast_var.get(),
            'visibility': {f'{k[0]}|{k[1]}': v for k, v in getattr(self, '_spell_visibility', {}).items()},
        }
        path = os.path.join(DATA_DIR, 'spell_session.json')
        with open(path, 'w') as f:
            json.dump(session, f)

    def _load_spell_session(self):
        path = os.path.join(DATA_DIR, 'spell_session.json')
        if not os.path.exists(path):
            if not hasattr(self, '_spell_visibility'):
                self._spell_visibility = {}
            return
        with open(path, 'r') as f:
            session = json.load(f)
        self._spell_mana_var.set(session.get('mana', '100'))
        self._spell_target_var.set(session.get('target_count', 1))
        self._spell_target_label.config(text=str(session.get('target_count', 1)))
        self._spell_rounds_var.set(session.get('rounds', 10))
        self._spell_rounds_label.config(text=str(session.get('rounds', 10)))
        self._spell_upcast_var.set(session.get('upcasts', 0))
        self._spell_upcast_label.config(text=str(session.get('upcasts', 0)))
        self._spell_dmg_mod_var.set(session.get('dmg_mod', '0'))
        for k, v in session.get('affinity_values', {}).items():
            if k in self._spell_affinity_vars:
                self._spell_affinity_vars[k].set(v)
        self._spell_mb_affinity_var.set(session.get('mb_affinity', 'None'))
        self._spell_karma_var.set(session.get('karma', '0'))
        self._spell_show_healing_var.set(session.get('show_healing', True))
        self._spell_leveled_only_var.set(session.get('leveled_only', False))
        for k, v in session.get('eldritch_vars', {}).items():
            if k in self._spell_eldritch_vars:
                self._spell_eldritch_vars[k].set(v)
        for k, v in session.get('bonus_vars', {}).items():
            if k in self._spell_bonus_vars:
                self._spell_bonus_vars[k].set(v)
        for k, v in session.get('feat_vars', {}).items():
            if k in self._spell_feat_vars:
                self._spell_feat_vars[k].set(v)
        if not hasattr(self, '_spell_visibility'):
            self._spell_visibility = {}
        for key_str, v in session.get('visibility', {}).items():
            parts = key_str.split('|', 1)
            if len(parts) == 2:
                self._spell_visibility[(parts[0], parts[1])] = v

    def _on_spell_scroll(self, event):
        if event.inaxes != self._spell_ax:
            return
        self._spell_zoomed = True
        scale = 0.85 if event.button == 'up' else 1.15
        xlim = self._spell_ax.get_xlim()
        ylim = self._spell_ax.get_ylim()
        xdata, ydata = event.xdata, event.ydata
        if xdata is None or ydata is None:
            return
        self._spell_ax.set_xlim([xdata - (xdata - xlim[0]) * scale,
                                  xdata + (xlim[1] - xdata) * scale])
        self._spell_ax.set_ylim([ydata - (ydata - ylim[0]) * scale,
                                  ydata + (ylim[1] - ydata) * scale])
        self._spell_canvas.draw_idle()

    def _auto_resize_spell_ylim(self):
        if getattr(self, '_spell_zoomed', False):
            return
        max_y = 0
        for line in self._spell_lines:
            if line.get_visible():
                yd = line.get_ydata()
                if len(yd) > 0:
                    max_y = max(max_y, max(yd))
        if max_y > 0:
            self._spell_ax.set_ylim(top=max_y * 1.05)

    def _on_spell_pan_press(self, event):
        if event.button != 2 or event.inaxes != self._spell_ax:
            return
        self._spell_pan_data = (event.x, event.y)
        self._spell_pan_xlim = self._spell_ax.get_xlim()
        self._spell_pan_ylim = self._spell_ax.get_ylim()
        self._spell_zoomed = True

    def _on_spell_pan_move(self, event):
        if self._spell_pan_data is None or event.inaxes != self._spell_ax:
            return
        if event.x is None or event.y is None:
            return
        dx = event.x - self._spell_pan_data[0]
        dy = event.y - self._spell_pan_data[1]
        xlim = self._spell_pan_xlim
        ylim = self._spell_pan_ylim
        bbox = self._spell_ax.bbox
        xscale = (xlim[1] - xlim[0]) / bbox.width if bbox.width > 0 else 1
        yscale = (ylim[1] - ylim[0]) / bbox.height if bbox.height > 0 else 1
        self._spell_ax.set_xlim(xlim[0] - dx * xscale, xlim[1] - dx * xscale)
        self._spell_ax.set_ylim(ylim[0] - dy * yscale, ylim[1] - dy * yscale)
        self._spell_canvas.draw_idle()

    def _on_spell_pan_release(self, event):
        self._spell_pan_data = None

    def _reset_spell_zoom(self):
        self._spell_zoomed = False
        self._spell_ax.set_xlim(left=0)
        self._spell_ax.set_ylim(bottom=0)
        self._auto_resize_spell_ylim()
        self._spell_ax.autoscale(axis='x')
        self._spell_canvas.draw()

    def _rebuild_spell_legend(self):
        for w in self._spell_legend_inner.winfo_children():
            w.destroy()

        btn_row = ttk.Frame(self._spell_legend_inner)
        btn_row.grid(row=0, column=0, columnspan=20, sticky='ew', padx=2, pady=2)
        ttk.Button(btn_row, text="All On", command=lambda: self._spell_toggle_all(True), width=7).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_row, text="All Off", command=lambda: self._spell_toggle_all(False), width=7).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_row, text="Base Mage", command=self._spell_toggle_base_mage, width=10).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_row, text="Complex Only", command=self._spell_toggle_complex_only, width=11).pack(side=tk.LEFT, padx=1)
        ttk.Separator(btn_row, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        ttk.Button(btn_row, text="Healing", command=self._spell_toggle_healing, width=7).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_row, text="Leveled", command=self._spell_toggle_leveled, width=7).pack(side=tk.LEFT, padx=1)

        if not hasattr(self, '_spell_visibility'):
            self._spell_visibility = {}

        families = {}
        for aff_name, spell_name, color, linestyle, is_healing, is_chain in self._spell_legend_entries:
            families.setdefault(aff_name, []).append((spell_name, color, linestyle, is_healing))

        COLS = 9
        sorted_fams = sorted(families.items())
        for idx, (aff_name, entries) in enumerate(sorted_fams):
            col = idx % COLS
            row = 1 + idx // COLS
            fcolor = entries[0][1] if entries else '#888'
            all_vis = all(self._spell_visibility.get((aff_name, sn), True) for sn, _, _, _ in entries)

            group = ttk.Frame(self._spell_legend_inner, relief='groove', borderwidth=1)
            group.grid(row=row, column=col, sticky='new', padx=2, pady=2)

            header = ttk.Frame(group)
            header.pack(fill=tk.X)

            fam_box = tk.Frame(header, width=12, height=12, bg=fcolor if all_vis else '#dddddd',
                              highlightbackground='#888', highlightthickness=1)
            fam_box.pack(side=tk.LEFT, padx=2)
            fam_box.pack_propagate(False)
            fam_box.bind('<Button-1>', lambda e, a=aff_name: self._spell_toggle_family(a))

            hdr_lbl = tk.Label(header, text=aff_name[:14], font=('', 7, 'bold'),
                              fg='#ccc' if all_vis else '#555', cursor='hand2')
            hdr_lbl.pack(side=tk.LEFT)
            hdr_lbl.bind('<Button-1>', lambda e, a=aff_name: self._spell_toggle_family(a))

            for spell_name, color, linestyle, is_healing in entries:
                entry_key = (aff_name, spell_name)
                is_vis = self._spell_visibility.get(entry_key, True)

                row_f = ttk.Frame(group)
                row_f.pack(fill=tk.X, padx=10)

                box = tk.Frame(row_f, width=10, height=10, bg=color if is_vis else '#dddddd',
                              highlightbackground='#888', highlightthickness=1)
                box.pack(side=tk.LEFT, padx=1)
                box.pack_propagate(False)

                display = f"{spell_name[:18]}"
                if is_healing:
                    display += ' ♥'
                lbl = tk.Label(row_f, text=display, font=('', 7),
                              fg='#ccc' if is_vis else '#555', anchor=tk.W, cursor='hand2')
                lbl.pack(side=tk.LEFT, fill=tk.X)

                def make_toggle(a, s):
                    return lambda e: self._spell_toggle_one(a, s)
                box.bind('<Button-1>', make_toggle(aff_name, spell_name))
                lbl.bind('<Button-1>', make_toggle(aff_name, spell_name))

        self._update_spell_summary()

    def _update_spell_summary(self):
        self._spell_summary_text.config(state=tk.NORMAL)
        self._spell_summary_text.delete('1.0', tk.END)

        best_dmg = ('', 0)
        best_eff = ('', 0)
        best_s3 = ('', 0)
        best_max = ('', 0)

        for line, ld in self._spell_line_data.items():
            if not line.get_visible():
                continue
            dmg = ld.get('dmg_per_cast', 0)
            mana = ld.get('mana_cost', 0)
            max_r = ld.get('max_rounds', 0)
            aff = ld.get('affinity', '')
            name = ld.get('spell_name', '')
            label = f"{aff}:{name}"

            total_dmg = dmg * max_r if max_r > 0 else dmg * self._spell_rounds_var.get()
            if total_dmg > best_dmg[1]:
                best_dmg = (label, total_dmg)

            if mana > 0:
                eff = dmg / mana
                if eff > best_eff[1]:
                    best_eff = (label, eff)

            s3 = dmg * min(3, max_r)
            if s3 > best_s3[1]:
                best_s3 = (label, s3)

            full_dmg = dmg * max_r
            if full_dmg > best_max[1]:
                best_max = (label, full_dmg)

        lines = []
        if best_dmg[1] > 0:
            lines.append(f"Top Damage:\n{best_dmg[0]}\n{best_dmg[1]:.0f} total")
        if best_eff[1] > 0:
            lines.append(f"Best Efficiency:\n{best_eff[0]}\n{best_eff[1]:.1f} dmg/mana")
        if best_s3[1] > 0:
            lines.append(f"Best Short (3r):\n{best_s3[0]}\n{best_s3[1]:.0f} dmg")
        if best_max[1] > 0:
            lines.append(f"Best Long ({self._spell_rounds_var.get()}r):\n{best_max[0]}\n{best_max[1]:.0f} dmg")

        vis_count = sum(1 for line in self._spell_lines if line.get_visible())
        total_count = len(self._spell_lines)
        lines.append(f"\nVisible: {vis_count}/{total_count}")

        if not lines:
            lines.append("No spells visible")

        self._spell_summary_text.insert('1.0', '\n\n'.join(lines))
        self._spell_summary_text.config(state=tk.DISABLED)

    def _spell_toggle_one(self, aff_name, spell_name):
        key = (aff_name, spell_name)
        self._spell_visibility[key] = not self._spell_visibility.get(key, True)
        for line in self._spell_lines:
            ld = self._spell_line_data.get(line, {})
            if ld.get('affinity') == aff_name and ld.get('spell_name') == spell_name:
                line.set_visible(self._spell_visibility[key])
                break
        self._auto_resize_spell_ylim()
        self._spell_canvas.draw()
        self._rebuild_spell_legend()

    def _spell_toggle_family(self, aff_name):
        entries = [e for e in self._spell_legend_entries if e[0] == aff_name]
        all_vis = all(self._spell_visibility.get((e[0], e[1]), True) for e in entries)
        new_state = not all_vis
        for e in entries:
            self._spell_visibility[(e[0], e[1])] = new_state
        for line in self._spell_lines:
            ld = self._spell_line_data.get(line, {})
            if ld.get('affinity') == aff_name:
                line.set_visible(new_state)
        self._auto_resize_spell_ylim()
        self._spell_canvas.draw()
        self._rebuild_spell_legend()

    def _spell_toggle_all(self, state):
        for e in self._spell_legend_entries:
            self._spell_visibility[(e[0], e[1])] = state
        for line in self._spell_lines:
            line.set_visible(state)
        self._spell_canvas.draw()
        self._rebuild_spell_legend()

    def _spell_toggle_healing(self):
        current = self._spell_show_healing_var.get()
        self._spell_show_healing_var.set(not current)
        self._refresh_spell_graph()

    def _spell_toggle_leveled(self):
        current = self._spell_leveled_only_var.get()
        self._spell_leveled_only_var.set(not current)
        self._refresh_spell_graph()

    def _spell_toggle_base_mage(self):
        base = {'Fire', 'Earth', 'Water', 'Air', 'Necrotic', 'Radiant', 'Psychic', 'Generic'}
        for entry in self._spell_legend_entries:
            aff_name = entry[0]
            sn = entry[1]
            is_chain = entry[5] if len(entry) > 5 else False
            visible = (aff_name in base and is_chain)
            self._spell_visibility[(aff_name, sn)] = visible
        for line in self._spell_lines:
            ld = self._spell_line_data.get(line, {})
            key = (ld.get('affinity', ''), ld.get('spell_name', ''))
            line.set_visible(self._spell_visibility.get(key, True))
        self._spell_canvas.draw()
        self._rebuild_spell_legend()

    def _spell_toggle_complex_only(self):
        base = {'Fire', 'Earth', 'Water', 'Air', 'Necrotic', 'Radiant', 'Psychic'}
        for entry in self._spell_legend_entries:
            aff_name = entry[0]
            sn = entry[1]
            visible = (aff_name not in base)
            self._spell_visibility[(aff_name, sn)] = visible
        for line in self._spell_lines:
            ld = self._spell_line_data.get(line, {})
            key = (ld.get('affinity', ''), ld.get('spell_name', ''))
            line.set_visible(self._spell_visibility.get(key, True))
        self._spell_canvas.draw()
        self._rebuild_spell_legend()

    def _clear_spell_click_annotation(self):
        if self._spell_click_annotation is not None:
            try:
                self._spell_click_annotation.remove()
            except Exception:
                pass
            self._spell_click_annotation = None

    def _on_spell_click(self, event):
        if event.button != 1 or event.inaxes != self._spell_ax:
            return

        self._clear_spell_click_annotation()

        xdata, ydata = event.xdata, event.ydata
        if xdata is None or ydata is None:
            self._spell_canvas.draw_idle()
            return

        self._spell_zoomed = True
        round_num = int(round(xdata))
        groups = {}
        for line in self._spell_lines:
            if not line.get_visible():
                continue
            xarr = line.get_xdata()
            yarr = line.get_ydata()
            if round_num < 0 or round_num >= len(xarr):
                continue
            if abs(xarr[round_num] - round_num) > 0.1:
                continue
            yd = yarr[round_num]
            ykey = int(round(yd))
            groups.setdefault(ykey, []).append((line, round_num, yd))

        if not groups:
            self._spell_canvas.draw_idle()
            return

        closest_ykey = min(groups.keys(), key=lambda k: abs(k - ydata))
        group = groups[closest_ykey]

        r = group[0][1]
        y = group[0][2]

        if len(group) == 1:
            line, r, y = group[0]
            data = self._spell_line_data.get(line, {})
            if data:
                self._show_single_info(line, data, r, y)
        else:
            self._show_multi_selector([(0, l, r, y) for l, r, y in group])

    def _show_single_info(self, line, data, closest_round, closest_ydata):
        aff_name = data['affinity']
        spell_name = data['spell_name']
        dmg_per_cast = data['dmg_per_cast']
        mana_cost = data['mana_cost']
        max_rounds = data['max_rounds']
        is_healing = data['is_healing']
        max_mana = data['max_mana']
        upcasts = data.get('upcasts', 0)
        beams = data.get('beams', 1)
        conditions = data.get('conditions', [])
        cond_dmg = data.get('cond_dmg', 0)

        total_mana_spent = mana_cost * closest_round
        remaining_mana = max(max_mana - total_mana_spent, 0)
        pct_left = (remaining_mana / max_mana * 100) if max_mana > 0 else 100
        efficiency = closest_ydata / total_mana_spent if total_mana_spent > 0 else 0

        info_lines = [f"{spell_name} ({aff_name})"]
        info_lines.append(f"{'─'*35}")
        info_lines.append(f"Round:              {closest_round}")
        info_lines.append(f"Cumulative Damage:  {closest_ydata:.1f}")
        info_lines.append(f"Mana per Cast:      {mana_cost}")
        info_lines.append(f"Total Mana Spent:   {total_mana_spent:.0f}")
        info_lines.append(f"Remaining Mana:     {remaining_mana:.0f} ({pct_left:.0f}%)")
        info_lines.append(f"Damage per Mana:    {efficiency:.2f}")
        if beams > 1:
            info_lines.append(f"Beams:              {beams}")
        if conditions:
            info_lines.append(f"Conditions:         {', '.join(conditions)}")
        if cond_dmg > 0:
            info_lines.append(f"Condition Dmg:      +{cond_dmg:.1f}/cast")
        if upcasts > 0:
            info_lines.append(f"Upcast Tier:        {upcasts} (mana x{2**upcasts})")
        if is_healing:
            info_lines.append(f"{'─'*35}")
            info_lines.append("This is healing, not damage")

        self._place_annotation(info_lines, closest_round, closest_ydata)
        self._spell_canvas.draw_idle()

    def _place_annotation(self, lines, x, y):
        xlim = self._spell_ax.get_xlim()
        ylim = self._spell_ax.get_ylim()
        tx = 0.98 if x < (xlim[0] + xlim[1]) / 2 else 0.02
        ty = 0.02 if y > (ylim[0] + ylim[1]) / 2 else 0.98
        ha = 'right' if tx > 0.5 else 'left'
        va = 'bottom' if ty < 0.5 else 'top'
        self._spell_click_annotation = self._spell_ax.annotate(
            "\n".join(lines), xy=(x, y), xycoords='data',
            xytext=(tx, ty), textcoords='axes fraction',
            ha=ha, va=va, annotation_clip=False,
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#2d2d30',
                      edgecolor='#888888', alpha=0.95),
            arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='#555555'),
            fontsize=8, fontfamily='monospace', zorder=10
        )

    def _show_multi_selector(self, candidates):
        all_lines = [f"{len(candidates)} spells overlap here:"]
        for dist, line, round_num, yd in candidates:
            ld = self._spell_line_data.get(line, {})
            if not ld:
                continue
            data = ld
            aff = data['affinity']
            sn = data['spell_name']
            mc = data['mana_cost']
            cond = data.get('conditions', [])
            cdmg = data.get('cond_dmg', 0)
            beams = data.get('beams', 1)
            upc = data.get('upcasts', 0)
            total_mana = mc * round_num
            pct = max(100 - (total_mana / max(data['max_mana'], 1) * 100), 0)
            
            all_lines.append(f"{'─'*30}")
            all_lines.append(f"  {sn} ({aff})")
            all_lines.append(f"  Round:{round_num}  Dmg:{yd:.0f}  Mana/cast:{mc}")
            all_lines.append(f"  Used:{total_mana:.0f}  Left:{pct:.0f}%")
            if beams > 1: all_lines.append(f"  Beams:{beams}")
            if cond: all_lines.append(f"  Cond:{', '.join(cond)} +{cdmg:.0f}")
            if upc > 0: all_lines.append(f"  Upcast:x{2**upc}")
        self._place_annotation(all_lines, candidates[0][2], candidates[0][3])
        self._spell_canvas.draw_idle()

    def _create_equipment_tab(self):
        self.eq_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.eq_frame, text="Equipment Analyzer")

        # ── Top controls row 1 ──
        ctrl1 = ttk.Frame(self.eq_frame)
        ctrl1.pack(fill=tk.X, padx=5, pady=3)
        def _spin(parent, label, var, fr, to, w, cmd):
            ttk.Label(parent, text=label).pack(side=tk.LEFT, padx=(8,2))
            s = ttk.Spinbox(parent, from_=fr, to=to, textvariable=var, width=w, command=cmd)
            s.pack(side=tk.LEFT, padx=2)
            return s

        self.eq_target_ac = tk.IntVar(value=16)
        _spin(ctrl1, "Target AC:", self.eq_target_ac, 0, 999, 4, self._update_equipment)
        self.eq_target_hp = tk.IntVar(value=100)
        _spin(ctrl1, "HP:", self.eq_target_hp, 10, 5000, 5, self._update_equipment)
        self.eq_str = tk.IntVar(value=3)
        _spin(ctrl1, "STR:", self.eq_str, -5, 20, 4, self._update_equipment)
        self.eq_dex = tk.IntVar(value=3)
        _spin(ctrl1, "DEX:", self.eq_dex, -5, 20, 4, self._update_equipment)
        self.eq_prof = tk.IntVar(value=2)
        _spin(ctrl1, "Prof:", self.eq_prof, 0, 10, 3, self._update_equipment)
        self.eq_ap = tk.IntVar(value=1)
        _spin(ctrl1, "AP:", self.eq_ap, 1, 5, 3, self._update_equipment)
        self.eq_extra = tk.IntVar(value=0)
        _spin(ctrl1, "Extra Atk:", self.eq_extra, 0, 5, 3, self._update_equipment)
        self.eq_flat_dmg = tk.IntVar(value=0)
        _spin(ctrl1, "Dmg+:", self.eq_flat_dmg, 0, 50, 4, self._update_equipment)
        self.eq_flat_acc = tk.IntVar(value=0)
        _spin(ctrl1, "Acc+:", self.eq_flat_acc, 0, 20, 4, self._update_equipment)
        self.eq_top_n = tk.IntVar(value=30)
        _spin(ctrl1, "Top N:", self.eq_top_n, 5, 100, 4, self._update_equipment)

        # ── Filter row (include + exclude) ──
        flt = ttk.Frame(self.eq_frame)
        flt.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(flt, text="Include:").pack(side=tk.LEFT, padx=5)
        self.eq_cat_var = tk.StringVar(value='')
        self.eq_cat_combo = ttk.Combobox(flt, textvariable=self.eq_cat_var, width=14)
        self.eq_cat_combo.pack(side=tk.LEFT, padx=2)
        self.eq_cat_combo.bind('<<ComboboxSelected>>', lambda e: self._eq_append_filter(self.eq_cat_var, self.eq_cat_combo))
        self.eq_cat_combo.bind('<Return>', lambda e: self._update_equipment())

        self.eq_mat_var = tk.StringVar(value='')
        self.eq_mat_combo = ttk.Combobox(flt, textvariable=self.eq_mat_var, width=14)
        self.eq_mat_combo.pack(side=tk.LEFT, padx=2)
        self.eq_mat_combo.bind('<<ComboboxSelected>>', lambda e: self._eq_append_filter(self.eq_mat_var, self.eq_mat_combo))
        self.eq_mat_combo.bind('<Return>', lambda e: self._update_equipment())

        ttk.Label(flt, text="Exclude:").pack(side=tk.LEFT, padx=(15,5))
        self.eq_ex_cat_var = tk.StringVar(value='')
        self.eq_ex_cat_combo = ttk.Combobox(flt, textvariable=self.eq_ex_cat_var, width=14)
        self.eq_ex_cat_combo.pack(side=tk.LEFT, padx=2)
        self.eq_ex_cat_combo.bind('<<ComboboxSelected>>', lambda e: self._eq_append_filter(self.eq_ex_cat_var, self.eq_ex_cat_combo))
        self.eq_ex_cat_combo.bind('<Return>', lambda e: self._update_equipment())
        self.eq_ex_mat_var = tk.StringVar(value='')
        self.eq_ex_mat_combo = ttk.Combobox(flt, textvariable=self.eq_ex_mat_var, width=14)
        self.eq_ex_mat_combo.pack(side=tk.LEFT, padx=2)
        self.eq_ex_mat_combo.bind('<<ComboboxSelected>>', lambda e: self._eq_append_filter(self.eq_ex_mat_var, self.eq_ex_mat_combo))
        self.eq_ex_mat_combo.bind('<Return>', lambda e: self._update_equipment())
        ttk.Button(flt, text="Clear", command=self._eq_clear_filters).pack(side=tk.LEFT, padx=10)

        # ── Sort radio buttons with tooltips ──
        ttk.Label(flt, text="Sort:").pack(side=tk.LEFT, padx=(15,2))
        self.eq_sort_var = tk.StringVar(value='DPR')
        TOOLTIPS = {
            'DPR': 'Expected Damage Per Round: avg dmg x hit chance x attacks/round. Measures sustained output against target AC.',
            'TTK': 'Time To Kill: rounds needed to deal target HP. Lower is better. Incorporates accuracy, damage, and AP economy.',
            'DMG': 'Effective Damage: raw damage per hit including all bonuses. Ignores accuracy, so favors high-damage weapons.',
            'Acc': 'Effective Accuracy: total attack bonus. Ignores damage, so favors reliable-hit weapons.',
        }
        self._eq_tooltip_lbl = ttk.Label(self.eq_frame, text='', foreground='#888', font=('TkDefaultFont', 9))
        self._eq_tooltip_lbl.pack(fill=tk.X, padx=10, pady=0)
        for val, lbl in [('DPR','DPR'),('TTK','TTK'),('DMG','DMG'),('Acc','Acc')]:
            rb = ttk.Radiobutton(flt, text=lbl, variable=self.eq_sort_var, value=val, command=self._update_equipment)
            rb.pack(side=tk.LEFT, padx=3)
            rb.bind('<Enter>', lambda e, v=val: self._eq_tooltip_lbl.configure(text=TOOLTIPS.get(v,'')))
            rb.bind('<Leave>', lambda e: self._eq_tooltip_lbl.configure(text=''))

        # Feat / Skill tree toggles
        feat_container = ttk.LabelFrame(self.eq_frame, text="Feats and Skill Tree Effects")
        feat_container.pack(fill=tk.X, padx=5, pady=(5,2))

        feat_inner = ttk.Frame(feat_container)
        feat_inner.pack(fill=tk.X, padx=4, pady=4)

        FEATS = [
            ('Brutal Crit', '+1d8 on critical hits', 'bc'),
            ('Brawler 3', 'Unarmed damage up 3 die tiers', 'brawler'),
            ('Weapon Master', '+1 Accuracy with weapon type', 'wm'),
            ('Heavy Hitter', '+5 melee damage (two-handed)', 'hh'),
            ('Dual Wielder', '+2 attack rolls (dual wielding)', 'dw'),
            ('Great Cleave', 'Free attack on kill (+3 dmg)', 'gc'),
            ('Charging Strike', '+1d6 damage after 15ft move', 'cs'),
            ('Executioner', 'Auto-crit vs <10% HP targets', 'ex'),
            ('Point Blank Shot', 'No disadvantage in melee range', 'pbs'),
            ('Vital Spot', '+1d12 vs Prone/Restrained', 'vs'),
            ('Steady Aim', '+5 Accuracy if no movement', 'ss'),
            ('Duelist L1', '+1 melee accuracy (Duelist L1)', 'du1'),
            ('Marksman L1', '+1 ranged accuracy (Marksman L1)', 'ma1'),
            ('Quick Reflexes', '+1 Reaction Point', 'qr'),
            ('Fast Hands', '+1 Bonus Action Point', 'fh'),
            ('R: Energy', 'Rune Energy: +1 Accuracy', 'r_energy'),
            ('R: G. Energy', 'Rune Greater Energy: +2 Accuracy', 'r_genergy'),
            ('R: Fire', 'Rune Fire: +1d6 Fire damage', 'r_fire'),
            ('R: G. Fire', 'Rune Greater Fire: +2d8 Fire damage', 'r_gfire'),
            ('R: Earth', 'Rune Earth: +1d6 Earth damage', 'r_earth'),
            ('R: Water', 'Rune Water: +1d6 Water damage', 'r_water'),
            ('R: Air', 'Rune Air: +1d6 Air damage', 'r_air'),
            ('R: Force', 'Rune Force: +1d6 Force damage', 'r_force'),
            ('R: Necrotic', 'Rune Necrotic: +1d6 Necrotic damage', 'r_necrotic'),
            ('R: Radiant', 'Rune Radiant: +1d6 Radiant damage', 'r_radiant'),
            ('R: Psychic', 'Rune Psychic: +1d6 Psychic damage', 'r_psychic'),
        ]
        num_cols = 3
        for i, (short, desc, key) in enumerate(FEATS):
            v = tk.BooleanVar(value=False)
            v.trace_add('write', lambda *a: self._update_equipment())
            setattr(self, f'_eq_feat_{key}', v)
            row = i % num_cols
            col = i // num_cols
            cb = ttk.Checkbutton(feat_inner, text=short, variable=v)
            cb.grid(row=row, column=col, sticky='w', padx=4, pady=1)
            ToolTip(cb, desc)

        # Graphs
        # Info label at bottom for click details
        self.eq_info_var = tk.StringVar(value='')
        info_lbl = ttk.Label(self.eq_frame, textvariable=self.eq_info_var, font=('TkDefaultFont', 8),
                            foreground='#aaa', wraplength=1200, justify='left')
        info_lbl.pack(fill=tk.X, padx=8, pady=(0,4))
        self.eq_fig = plt.figure(figsize=(14, 8), dpi=100)
        self.eq_ax1 = self.eq_fig.add_subplot(2, 2, 1)
        self.eq_ax2 = self.eq_fig.add_subplot(2, 2, 2)
        self.eq_ax3 = self.eq_fig.add_subplot(2, 2, 3)
        self.eq_ax4 = self.eq_fig.add_subplot(2, 2, 4)
        self.eq_fig.tight_layout(pad=3)

        self.eq_canvas = FigureCanvasTkAgg(self.eq_fig, self.eq_frame)
        self.eq_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Scatter hover state
        self._eq_scatter_annot = None
        self._eq_scatter_points = None
        self._eq_scatter_weapons = []

        self._eq_data = None
        self._eq_weapons = []
        self._load_equipment_data()
        self.eq_canvas.mpl_connect('button_press_event', self._on_eq_click)
        self.eq_canvas.mpl_connect('motion_notify_event', self._on_eq_hover)

    def _load_equipment_data(self):
        import json, os
        paths = [
            os.path.join(DATA_DIR, 'equipment.json'),
            os.path.join(os.path.dirname(DATA_DIR), '..', 'dist', 'equipment.json'),
        ]
        for p in paths:
            try:
                with open(p) as f:
                    self._eq_data = json.load(f)
                self._eq_weapons = self._eq_data.get('weapons', [])
                cats = sorted(self._eq_data.get('by_category', {}).keys())
                weapon_names = sorted(set(w['weapon'] for w in self._eq_weapons))
                mats = sorted(set(w['material'] for w in self._eq_weapons))
                all_filter_vals = [''] + cats + weapon_names
                for combo in [self.eq_cat_combo, self.eq_ex_cat_combo]:
                    combo['values'] = all_filter_vals
                for combo in [self.eq_mat_combo, self.eq_ex_mat_combo]:
                    combo['values'] = [''] + mats
                self._update_equipment()
                return
            except Exception:
                continue
        self._eq_data = {'weapons': [], 'by_category': {}, 'materials': []}
        self._eq_weapons = []

    def _eq_clear_filters(self):
        self.eq_cat_var.set(''); self.eq_mat_var.set('')
        self.eq_ex_cat_var.set(''); self.eq_ex_mat_var.set('')
        self._update_equipment()

    def _eq_append_filter(self, var, combo):
        """When dropdown item clicked, append after comma instead of replacing."""
        current = var.get().strip()
        selected = combo.get().strip()
        if not selected: return
        if current:
            parts = [x.strip() for x in current.split(',') if x.strip()]
            if selected not in parts:
                parts.append(selected)
            var.set(', '.join(parts))
        else:
            var.set(selected)
        self._update_equipment()

    def _hit_chance(self, acc, target_ac):
        needed = target_ac - acc
        if needed <= 1: return 0.95
        if needed >= 20: return 0.05
        return max(0.05, min(0.95, (21 - needed) / 20))

    def _eq_feat_on(self, key):
        try: return getattr(self, f'_eq_feat_{key}').get()
        except: return False

    def _update_equipment(self, *args):
        if not self._eq_weapons:
            return
        target_ac = self.eq_target_ac.get()
        target_hp = self.eq_target_hp.get()
        str_mod = self.eq_str.get()
        prof = self.eq_prof.get()
        ap = self.eq_ap.get()
        extra = self.eq_extra.get()
        flat_dmg = self.eq_flat_dmg.get()
        flat_acc = self.eq_flat_acc.get()
        top_n = self.eq_top_n.get()
        sort_by = self.eq_sort_var.get()
        inc_cats = [x.strip() for x in self.eq_cat_var.get().split(',') if x.strip()]
        inc_mats = [x.strip() for x in self.eq_mat_var.get().split(',') if x.strip()]
        exc_cats = [x.strip() for x in self.eq_ex_cat_var.get().split(',') if x.strip()]
        exc_mats = [x.strip() for x in self.eq_ex_mat_var.get().split(',') if x.strip()]

        # Apply feat bonuses from actual handbook feats
        dmg_bonus = str_mod + flat_dmg
        acc_bonus = str_mod + prof + flat_acc
        if self._eq_feat_on('dw'): acc_bonus += 2
        if self._eq_feat_on('hh'): dmg_bonus += 5
        if self._eq_feat_on('wm'): acc_bonus += 1
        if self._eq_feat_on('gc'): dmg_bonus += 3
        if self._eq_feat_on('cs'): dmg_bonus += 3.5
        if self._eq_feat_on('du1'): acc_bonus += 1
        if self._eq_feat_on('ma1'): acc_bonus += 1
        if self._eq_feat_on('ss'): acc_bonus += 5
        if self._eq_feat_on('r_energy'): acc_bonus += 1
        if self._eq_feat_on('r_genergy'): acc_bonus += 2
        if self._eq_feat_on('r_fire'): dmg_bonus += 3.5    # 1d6
        if self._eq_feat_on('r_gfire'): dmg_bonus += 9      # 2d8
        if self._eq_feat_on('r_earth'): dmg_bonus += 3.5
        if self._eq_feat_on('r_water'): dmg_bonus += 3.5
        if self._eq_feat_on('r_air'): dmg_bonus += 3.5
        if self._eq_feat_on('r_force'): dmg_bonus += 3.5
        if self._eq_feat_on('r_necrotic'): dmg_bonus += 3.5
        if self._eq_feat_on('r_radiant'): dmg_bonus += 3.5
        if self._eq_feat_on('r_psychic'): dmg_bonus += 3.5
        attacks = ap + extra
        if self._eq_feat_on('fh'): attacks += 0.5  # BAp gives ~0.5 extra attacks per round

        weapons = self._eq_weapons[:]
        if inc_cats:
            weapons = [w for w in weapons if any(c in w.get('category', []) or c == w.get('weapon','') for c in inc_cats)]
        if inc_mats:
            weapons = [w for w in weapons if w['material'] in inc_mats]
        if exc_cats:
            weapons = [w for w in weapons if not any(c in w.get('category', []) or c == w.get('weapon','') for c in exc_cats)]
        if exc_mats:
            weapons = [w for w in weapons if w['material'] not in exc_mats]

        DIE_AVG = {}
        if self._eq_data:
            DIE_AVG = self._eq_data.get('die_averages', {})

        for w in weapons:
            acc = w['total_acc'] + acc_bonus
            dmg = w['total_dmg'] + dmg_bonus
            # Brutal Crit
            if self._eq_feat_on('bc'):
                bc_extra = DIE_AVG.get('1d8', 4.5)
            else:
                bc_extra = 0
            hc = self._hit_chance(acc, target_ac)
            cc = 0.05
            crit_dmg = dmg * 2 + bc_extra
            normal_hit = hc - cc
            if normal_hit < 0: normal_hit = 0
            w['_dpr'] = (normal_hit * dmg + cc * crit_dmg) * attacks
            w['_hit'] = hc * 100
            w['_ttk'] = target_hp / w['_dpr'] if w['_dpr'] > 0 else 999
            w['_eff_acc'] = acc
            w['_eff_dmg'] = dmg

        if sort_by == 'DPR':
            weapons.sort(key=lambda x: x['_dpr'], reverse=True)
        elif sort_by == 'TTK':
            weapons.sort(key=lambda x: x['_ttk'])
        elif sort_by == 'DMG':
            weapons.sort(key=lambda x: x['_eff_dmg'], reverse=True)
        elif sort_by == 'Acc':
            weapons.sort(key=lambda x: x['_eff_acc'], reverse=True)

        top = weapons[:top_n]

        for ax in [self.eq_ax1, self.eq_ax2, self.eq_ax3, self.eq_ax4]:
            ax.clear()

        # Ax1: Horizontal bar chart with wrapped names
        names = [w['name'][:40] for w in top]
        dprs = [w['_dpr'] for w in top]
        colors = [f'C{i}' for i in range(len(top))]
        self.eq_ax1.barh(range(len(top)), dprs, color=colors, height=0.7)
        self.eq_ax1.set_yticks(range(len(top)))
        self.eq_ax1.set_yticklabels(names, fontsize=6)
        self.eq_ax1.invert_yaxis()
        self.eq_ax1.set_xlabel(f'DPR vs AC {target_ac}')
        self.eq_ax1.set_title(f'Top {len(top)} Weapons by {sort_by}')

        # Ax2: Scatter — DMG vs Hit%, with hover
        hits = [w['_hit'] for w in top]
        dmgs = [w['_eff_dmg'] for w in top]
        sc = self.eq_ax2.scatter(hits, dmgs, c=range(len(top)), cmap='viridis', s=50, alpha=0.85, picker=5)
        self.eq_ax2.set_xlabel('Hit Chance %')
        self.eq_ax2.set_ylabel('Effective Damage')
        self.eq_ax2.set_title('DMG x Accuracy: hover for details')
        self._eq_scatter_points = sc
        self._eq_scatter_weapons = top

        # Ax3: By material — top 5
        by_mat = {}
        for w in weapons:
            by_mat[w['material']] = by_mat.get(w['material'], 0) + w['_dpr']
        mat_items = sorted(by_mat.items(), key=lambda x: x[1], reverse=True)[:5]
        if mat_items:
            mnames = [m[0] for m in mat_items]
            mvals = [m[1] for m in mat_items]
            self.eq_ax3.bar(range(len(mnames)), mvals, color=[f'C{i}' for i in range(len(mnames))])
            self.eq_ax3.set_xticks(range(len(mnames)))
            self.eq_ax3.set_xticklabels(mnames, rotation=30, ha='right', fontsize=8)
            self.eq_ax3.set_ylabel('Sum DPR')
            self.eq_ax3.set_title('By Material (Top 5)')

        # Ax4: By category
        by_cat = {}
        for w in weapons:
            for c in w.get('category', []):
                by_cat[c] = by_cat.get(c, 0) + w['_dpr']
        cat_items = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
        if cat_items:
            cnames = [c[0] for c in cat_items]
            cvals = [c[1] for c in cat_items]
            self.eq_ax4.bar(range(len(cnames)), cvals, color=[f'C{i}' for i in range(len(cnames))])
            self.eq_ax4.set_xticks(range(len(cnames)))
            self.eq_ax4.set_xticklabels(cnames, rotation=45, ha='right', fontsize=7)
            self.eq_ax4.set_ylabel('Sum DPR')
            self.eq_ax4.set_title('By Category')

        self.eq_fig.tight_layout(pad=3)
        self.eq_canvas.draw_idle()

    def _on_eq_hover(self, event):
        if event.inaxes != self.eq_ax2 or not self._eq_scatter_weapons:
            if self._eq_scatter_annot:
                self._eq_scatter_annot.set_visible(False)
                self.eq_canvas.draw_idle()
            return
        top = self._eq_scatter_weapons
        # Find closest point
        min_dist = 999
        closest = None
        for i, w in enumerate(top):
            dx = event.xdata - w['_hit']
            dy = event.ydata - w['_eff_dmg']
            dist = (dx*dx + dy*dy) ** 0.5
            if dist < min_dist:
                min_dist = dist
                closest = (i, w)
        if min_dist < 8 and closest:
            i, w = closest
            txt = f"{w['name']}\nMaterial: {w['material']}\nDMG: {w['_eff_dmg']:.1f}  Hit: {w['_hit']:.0f}%  DPR: {w['_dpr']:.1f}"
            if self._eq_scatter_annot:
                self._eq_scatter_annot.set_text(txt)
                self._eq_scatter_annot.xy = (w['_hit'], w['_eff_dmg'])
                self._eq_scatter_annot.set_visible(True)
            else:
                self._eq_scatter_annot = self.eq_ax2.annotate(txt, xy=(w['_hit'], w['_eff_dmg']),
                    xytext=(10, 10), textcoords='offset points', fontsize=8, fontfamily='monospace',
                    bbox=dict(boxstyle='round', facecolor='#2d2d30', edgecolor='#888', alpha=0.95),
                    arrowprops=dict(arrowstyle='->', color='#555'))
            self.eq_canvas.draw_idle()
        elif self._eq_scatter_annot:
            self._eq_scatter_annot.set_visible(False)
            self.eq_canvas.draw_idle()

    def _on_eq_click(self, event):
        if event.inaxes != self.eq_ax1 or not self._eq_weapons:
            return
        target_ac = self.eq_target_ac.get()
        target_hp = self.eq_target_hp.get()
        weapons = self._eq_weapons[:]
        inc_cats = [x.strip() for x in self.eq_cat_var.get().split(',') if x.strip()]
        inc_mats = [x.strip() for x in self.eq_mat_var.get().split(',') if x.strip()]
        exc_cats = [x.strip() for x in self.eq_ex_cat_var.get().split(',') if x.strip()]
        exc_mats = [x.strip() for x in self.eq_ex_mat_var.get().split(',') if x.strip()]
        if inc_cats: weapons = [w for w in weapons if any(c in w.get('category', []) or c == w.get('weapon','') for c in inc_cats)]
        if inc_mats: weapons = [w for w in weapons if w['material'] in inc_mats]
        if exc_cats: weapons = [w for w in weapons if not any(c in w.get('category', []) or c == w.get('weapon','') for c in exc_cats)]
        if exc_mats: weapons = [w for w in weapons if w['material'] not in exc_mats]
        sort_by = self.eq_sort_var.get()
        if sort_by == 'DPR': weapons.sort(key=lambda x: x.get('_dpr', 0), reverse=True)
        elif sort_by == 'TTK': weapons.sort(key=lambda x: x.get('_ttk', 999))
        elif sort_by == 'DMG': weapons.sort(key=lambda x: x.get('_eff_dmg', 0), reverse=True)
        elif sort_by == 'Acc': weapons.sort(key=lambda x: x.get('_eff_acc', 0), reverse=True)
        top = weapons[:self.eq_top_n.get()]
        idx = int(round(event.ydata))
        if 0 <= idx < len(top):
            w = top[idx]
            lines = [
                f"  {w['name']}",
                f"  Material: {w['material']} | {w['dmg_type']}",
                f"  Die: {w['die']} | Range: {w['range']}ft",
                f"  Acc: {w['_eff_acc']} | DMG: {w['_eff_dmg']:.1f}",
                f"  DPR: {w['_dpr']:.1f} | Hit%: {w['_hit']:.0f}%",
                f"  TTK({target_hp}hp): {w['_ttk']:.1f}r | Price: {w['price_gold']:.0f}g",
            ]
            self.eq_info_var.set("\n".join(lines))
            self.eq_canvas.draw_idle()

    def _bind_scrollwheel(self, widget):
        def _on_mousewheel(event):
            if event.num == 4 or event.delta > 0:
                widget.yview_scroll(-1, 'units')
            elif event.num == 5 or event.delta < 0:
                widget.yview_scroll(1, 'units')
        widget.bind('<Button-4>', _on_mousewheel)
        widget.bind('<Button-5>', _on_mousewheel)
        widget.bind('<MouseWheel>', _on_mousewheel)

    def _setup_interactions(self):
        self.canvas.mpl_connect('motion_notify_event', self._on_hover)
        self.canvas.mpl_connect('axes_leave_event', self._on_leave_axes)
        self.canvas.mpl_connect('button_press_event', self._on_click)

    def _initial_generate(self):
        self._load_graph_data()

    def _save_graph_data(self):
        try:
            if self.data is None:
                return
            path = os.path.join(DATA_DIR, 'graph_cache.json')
            with open(path, 'w') as f:
                json.dump(self.data, f)
            session = {
                'build_enabled': self._build_enabled,
                'line_visible': self._line_visible,
                'current_tier': self.current_tier,
                'current_stat': self.stat_var.get(),
                'max_level': int(self.level_slider.get()),
            }
            with open(os.path.join(DATA_DIR, 'gui_session.json'), 'w') as f:
                json.dump(session, f)
        except Exception:
            pass

    def _load_graph_data(self):
        try:
            path = os.path.join(DATA_DIR, 'graph_cache.json')
            if not os.path.exists(path):
                return
            with open(path, 'r') as f:
                raw = json.load(f)
            self.data = {}
            for tier_name, tier_data in raw.items():
                self.data[tier_name] = {}
                for build_name, bd in tier_data.items():
                    self.data[tier_name][build_name] = {}
                    for lvl_str, stats in bd.items():
                        self.data[tier_name][build_name][int(lvl_str)] = stats
            self.settings = load_settings(DATA_DIR)
            spath = os.path.join(DATA_DIR, 'gui_session.json')
            if os.path.exists(spath):
                with open(spath, 'r') as f:
                    session = json.load(f)
                self._build_enabled = session.get('build_enabled', {})
                self._line_visible = session.get('line_visible', {})
                self.current_tier = session.get('current_tier')
                self.stat_var.set(session.get('current_stat', 'Dmg/Turn'))
                ml = session.get('max_level', 30)
                self.level_slider.set(ml)
                if hasattr(self, 'level_slider_label'):
                    self.level_slider_label.config(text=str(ml))
            tiers = list(self.data.keys())
            self.tier_combo['values'] = tiers
            if self.current_tier not in tiers:
                self.current_tier = tiers[0]
            self.tier_var.set(self.current_tier)
            self._update_graph()
            self.status_label.config(text="Loaded cached data")
        except Exception:
            pass

    def _run_generator_from_ui(self):
        if self.settings is None:
            self._run_generator()
        else:
            self._run_generator()

    def _run_generator(self, custom_settings=None, build_filter=None):
        if self.generating:
            messagebox.showinfo("Busy", "Generator is already running.")
            return

        saved_build_enabled = dict(getattr(self, '_build_enabled', {}))
        saved_line_visible = dict(getattr(self, '_line_visible', {}))

        def progress(cur, total, msg):
            self.root.after(0, lambda: self._update_progress(cur, total, msg))

        def _reenable():
            self.generating = False
            self.run_btn.config(state=tk.NORMAL)
            self.settings_run_btn.config(state=tk.NORMAL)
            self.settings_run_temp_btn.config(state=tk.NORMAL)
            self.update_spells_btn.config(state=tk.NORMAL)

        def done(data):
            if build_filter and self.data:
                # Merge: update only the regenerated builds, keep others
                for tier_name, tier_data in data.items():
                    if tier_name not in self.data:
                        self.data[tier_name] = {}
                    for build_name, build_data in tier_data.items():
                        self.data[tier_name][build_name] = build_data
                    # Recalculate averages for this tier
                    all_builds = [(n, d) for n, d in self.data.get(tier_name, {}).items() if n != '__average__']
                    all_levels = sorted(set(l for _, bd in all_builds for l in bd.keys()))
                    avg = {}
                    for lvl in all_levels:
                        avg[lvl] = {}
                        vals = {stat: [bd[lvl].get(stat, 0) for _, bd in all_builds if lvl in bd] for stat in ALL_STATS}
                        for stat, vlist in vals.items():
                            avg[lvl][stat] = int(round(sum(vlist) / len(vlist))) if vlist else 0
                    self.data[tier_name]['__average__'] = avg
            else:
                self.data = data
            tiers = list(data.keys())
            self.tier_combo['values'] = tiers
            if self.current_tier is None or self.current_tier not in tiers:
                self.current_tier = tiers[0]
                self.tier_var.set(tiers[0])
            else:
                self.tier_var.set(self.current_tier)
            max_lvl = max(lvl for td in data.values() for build in td.values() for lvl in build.keys() if build != '__average__')
            self.level_slider.configure(to=max_lvl)
            self.level_slider.set(max_lvl)
            self.level_slider_label.config(text=str(max_lvl))
            self._build_enabled = saved_build_enabled
            self._line_visible = saved_line_visible
            self._update_graph()
            self.status_label.config(text="Ready")
            self.settings_status.config(text="Ready")
            _reenable()
            self._save_graph_data()

        def error(exc):
            _reenable()
            self.status_label.config(text="Error")
            self.settings_status.config(text="Error")
            traceback.print_exc()
            self.root.after(0, lambda: messagebox.showerror("Generation Error", str(exc)))

        def worker():
            try:
                settings = custom_settings if custom_settings is not None else load_settings(DATA_DIR)
                self.settings = settings
                result = collect_all_data(settings, progress, build_filter)
                self.root.after(0, lambda: done(result))
            except Exception as e:
                self.root.after(0, lambda e=e: error(e))

        self.generating = True
        self.run_btn.config(state=tk.DISABLED)
        self.settings_run_btn.config(state=tk.DISABLED)
        self.settings_run_temp_btn.config(state=tk.DISABLED)
        self.progress_bar['value'] = 0
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _update_progress(self, cur, total, msg):
        if total > 0:
            pct = min(100, int(cur / total * 100))
            self.progress_bar['value'] = pct
            self.settings_progress['value'] = pct
        self.status_label.config(text=msg)
        self.settings_status.config(text=msg)
        self.root.update_idletasks()

    def _get_plot_levels(self, tier_data):
        all_levels = sorted(set(
            lvl for bd in tier_data.values() for lvl in bd.keys()
        ))
        return [l for l in all_levels if l <= int(self.level_slider.get())]

    def _on_slider_change(self, val):
        self.level_slider_label.config(text=str(int(float(val))))
        self._update_graph()

    def _update_spells_and_regen(self):
        """Run the spell updater script then regenerate all builds."""
        if self.generating:
            messagebox.showinfo("Busy", "Already generating.")
            return
        import subprocess, threading
        script = os.path.join(SCRIPT_DIR, 'update_spells.py')
        if not os.path.exists(script):
            messagebox.showerror("Error", f"update_spells.py not found at:\n{script}")
            return

        self.generating = True
        self.update_spells_btn.config(state=tk.DISABLED)
        self.run_btn.config(state=tk.DISABLED)

        def run():
            self.root.after(0, lambda: self.status_label.config(text="Running spell updater..."))
            self.root.after(0, lambda: self.settings_status.config(text="Updating..."))
            try:
                proc = subprocess.run(
                    [sys.executable, script],
                    input='n\n',
                    capture_output=True, text=True, timeout=120,
                    cwd=SCRIPT_DIR
                )
                if proc.returncode == 0:
                    self.root.after(0, lambda: self.status_label.config(
                        text="Spells updated. Rebuilding affected builds..."))
                else:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Updater Error", proc.stderr[:500] or f"Exit code {proc.returncode}"))
                    self.root.after(0, lambda: self._regen_reenable())
                    return
                proc = subprocess.run(
                    [sys.executable, script],
                    input='n\n',
                    capture_output=True, text=True, timeout=120,
                    cwd=SCRIPT_DIR
                )

                # Parse stdout: "Spell Updater — 3 changed, 302 unchanged"
                changed_count = 0
                for line in proc.stdout.splitlines():
                    m = re.search(r'(\d+)\s+changed', line)
                    if m:
                        changed_count = int(m.group(1))
                        break

                if changed_count == 0:
                    self.root.after(0, lambda: self.status_label.config(text="No handbook changes detected"))
                    self.root.after(0, lambda: self._regen_reenable())
                    self.generating = False
                    return

                self.root.after(0, lambda: self.status_label.config(text=f"{changed_count} spells changed, rebuilding..."))
                self.settings = None
                self.generating = False
                self.root.after(100, lambda: self._run_generator())
            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: messagebox.showerror("Updater Error", "Timed out after 120s"))
                self.root.after(0, lambda: self._regen_reenable())
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Updater Error", str(e)))
                self.root.after(0, lambda: self._regen_reenable())

        threading.Thread(target=run, daemon=True).start()

    def _regen_reenable(self):
        self.generating = False
        self.update_spells_btn.config(state=tk.NORMAL)
        self.run_btn.config(state=tk.NORMAL)

    def _rebuild_legend_panel(self, build_names, colors):
        for w in self.legend_inner.winfo_children():
            w.destroy()

        builds_config = self.settings.get('builds', {}) if self.settings else {}

        archetypes = []; races = []; affinities = []
        for name in build_names:
            if name.startswith('Archetype:'):
                archetypes.append(name)
            elif name.startswith('Race:'):
                races.append(name)
            elif name.startswith('Affinity:'):
                affinities.append(name)

        def build_group(title, group, group_color):
            if not group:
                return
            all_vis = all(self._line_visible.get(n, True) for n in group)
            header = ttk.Frame(self.legend_inner)
            header.pack(fill=tk.X, padx=1, pady=(4, 0))
            fam_cb = ttk.Checkbutton(header, command=lambda g=group: self._toggle_group(g))
            fam_cb.state(('selected',) if all_vis else ('!selected',))
            fam_cb.pack(side=tk.LEFT)
            tk.Label(header, text=f'{title} ({len(group)})', font=('', 7, 'bold'), fg=group_color).pack(side=tk.LEFT, padx=2)

            for name in group:
                color = colors.get(name, '#888')
                is_visible = self._line_visible.get(name, True)
                row = ttk.Frame(self.legend_inner)
                row.pack(fill=tk.X, padx=12, pady=0)
                cb = ttk.Checkbutton(row, command=lambda n=name: self._toggle_build_check(n))
                cb.state(('!selected',) if not is_visible else ('selected',))
                cb.pack(side=tk.LEFT)
                box = tk.Frame(row, width=10, height=10, bg=color if is_visible else '#ddd',
                              highlightbackground='#888', highlightthickness=1)
                box.pack(side=tk.LEFT, padx=2)
                box.pack_propagate(False)
                # Show short name
                short = name.split(':', 1)[1].strip() if ':' in name else name
                lbl = tk.Label(row, text=short, font=('', 7),
                               fg='#ccc' if is_visible else '#555', anchor=tk.W, cursor='hand2')
                lbl.pack(side=tk.LEFT, fill=tk.X, padx=2)
                def make_toggle(n):
                    return lambda e: self._toggle_line(n)
                box.bind('<Button-1>', make_toggle(name))
                lbl.bind('<Button-1>', make_toggle(name))

        COLORS = {'Archetype': '#d62728', 'Race': '#2ca02c', 'Affinity': '#9467bd'}
        build_group('Archetypes', sorted(archetypes), COLORS['Archetype'])
        build_group('Races', sorted(races), COLORS['Race'])
        build_group('Affinities', sorted(affinities), COLORS['Affinity'])

        if '__average__' in self._lines:
            is_vis = self._line_visible.get('__average__', True)
            sep = ttk.Separator(self.legend_inner, orient=tk.HORIZONTAL)
            sep.pack(fill=tk.X, padx=2, pady=4)
            row = ttk.Frame(self.legend_inner)
            row.pack(fill=tk.X, padx=1, pady=1)
            cb = ttk.Checkbutton(row, command=lambda: self._toggle_line('__average__'))
            cb.state(('selected',) if is_vis else ('!selected',))
            cb.pack(side=tk.LEFT)
            box = tk.Frame(row, width=10, height=10, bg=AVG_LINE_COLOR if is_vis else '#ddd',
                          highlightbackground='#888', highlightthickness=1)
            box.pack(side=tk.LEFT, padx=2)
            box.pack_propagate(False)
            lbl = tk.Label(row, text='Average', font=('', 7, 'bold'),
                          fg='#ccc' if is_vis else '#555', anchor=tk.W, cursor='hand2')
            lbl.pack(side=tk.LEFT, fill=tk.X, padx=2)
            def make_toggle_avg():
                return lambda e: self._toggle_line('__average__')
            box.bind('<Button-1>', make_toggle_avg())
            lbl.bind('<Button-1>', make_toggle_avg())

    def _toggle_group(self, group):
        all_vis = all(self._line_visible.get(n, True) for n in group)
        new_state = not all_vis
        for name in group:
            if name in self._lines:
                self._line_visible[name] = new_state
                self._build_enabled[name] = new_state
                self._lines[name].set_visible(new_state)
        self._rebuild_legend()
        self.canvas.draw()

    def _rebuild_legend(self):
        if self._build_names:
            builds_config = self.settings.get('builds', {}) if self.settings else {}
            color_used = set()
            colors = {}
            for i, name in enumerate(self._build_names):
                cfg = builds_config.get(name, {})
                c = cfg.get('color', None)
                if c and c not in color_used:
                    color_used.add(c)
                    colors[name] = c
                else:
                    for ci in range(100):
                        fallback = COLOR_CYCLE[(i + ci) % len(COLOR_CYCLE)]
                        if fallback not in color_used:
                            color_used.add(fallback)
                            colors[name] = fallback
                            break
                    else:
                        colors[name] = COLOR_CYCLE[i % len(COLOR_CYCLE)]
            self._rebuild_legend_panel(self._build_names, colors)

    def _update_graph(self):
        if self.data is None:
            self.ax.clear()
            self.ax.text(0.5, 0.5, 'No data. Run generator first.',
                         transform=self.ax.transAxes, ha='center', va='center', fontsize=14)
            self.canvas.draw()
            return

        tier = self.tier_var.get() or list(self.data.keys())[0]
        stat = self.stat_var.get() or 'Dmg/Turn'

        if tier not in self.data:
            return

        tier_data = self.data[tier]
        self.ax.clear()

        self._clear_click_annotation()
        saved_visible = self._line_visible.copy()
        self._lines = {}
        self._line_visible = {}
        self._focused_line_name = None
        self._selected_level = None
        self._affinity_markers = []

        build_names = [k for k in tier_data.keys() if k != '__average__']
        self._build_names = build_names
        builds_config = self.settings.get('builds', {}) if self.settings else {}
        color_used = set()
        colors = {}
        for i, name in enumerate(build_names):
            cfg = builds_config.get(name, {})
            c = cfg.get('color', None)
            if c and c not in color_used:
                color_used.add(c)
                colors[name] = c
            else:
                for ci in range(100):
                    fallback = COLOR_CYCLE[(i + ci) % len(COLOR_CYCLE)]
                    if fallback not in color_used:
                        color_used.add(fallback)
                        colors[name] = fallback
                        break
                else:
                    colors[name] = COLOR_CYCLE[i % len(COLOR_CYCLE)]

        all_levels = self._get_plot_levels(tier_data)

        for i, name in enumerate(build_names):
            bd = tier_data[name]
            xs = sorted(k for k in bd.keys() if k in all_levels)
            ys = [bd[x][stat] for x in xs]
            line, = self.ax.plot(
                xs, ys, color=colors[name], linewidth=2,
                marker='o', markersize=4, label=name,
                picker=True, pickradius=5,
                alpha=FOCUSED_ALPHA
            )
            self._lines[name] = line
            if name in saved_visible:
                visible = saved_visible[name]
            else:
                visible = True
            self._line_visible[name] = visible
            self._lines[name].set_visible(visible)
            if name not in self._build_enabled:
                self._build_enabled[name] = visible

        if '__average__' in tier_data:
            avg = tier_data['__average__']
            xs = sorted(k for k in avg.keys() if k in all_levels)
            ys = [avg[x][stat] for x in xs]
            line, = self.ax.plot(
                xs, ys, color=AVG_LINE_COLOR, linewidth=AVG_LINE_WIDTH,
                linestyle=AVG_LINE_STYLE, marker='s', markersize=5,
                label='Average', zorder=5, alpha=1.0
            )
            self._lines['__average__'] = line
            self._line_visible['__average__'] = True

        self._rebuild_legend_panel(build_names, colors)

        self.ax.set_xlabel('Level', fontsize=11)
        self.ax.set_ylabel(STAT_LABELS.get(stat, stat), fontsize=11)
        self.ax.set_title(f'{STAT_LABELS.get(stat, stat)} by Level - {tier.replace("_", " ").title()}',
                          fontsize=13, fontweight='bold')

        self.ax.set_xlim(min(all_levels) - 1, max(all_levels) + 1)
        self.ax.tick_params(labelsize=9)

        self._draw_affinity_markers(tier_data, build_names, all_levels)

        self._rebuild_summary()
        self.canvas.draw()

    def _rebuild_summary(self):
        pass

    def _draw_affinity_markers(self, tier_data, build_names, all_levels):
        for m in self._affinity_markers:
            try:
                m.remove()
            except:
                pass
        self._affinity_markers = []
        if not all_levels or not self.settings:
            return
        builds_config = self.settings.get('builds', {})
        for name in build_names:
            bc = builds_config.get(name, {})
            primary = bc.get('primary_affinity', None)
            if not primary:
                continue
            if name not in tier_data:
                continue
            bd = tier_data[name]
            found_10 = None
            found_15 = None
            for lvl in sorted(bd.keys()):
                if lvl not in all_levels:
                    continue
                affs = bd[lvl].get('affinities', {})
                primary_val = affs.get(primary, 0)
                if primary_val >= 10 and found_10 is None:
                    found_10 = lvl
                if primary_val >= 15 and found_15 is None:
                    found_15 = lvl
            for found_lvl, label in [(found_10, 'Aff 10+'), (found_15, 'Aff 15+')]:
                if found_lvl is not None:
                    m = self.ax.axvline(x=found_lvl, color='#888888',
                                        linestyle=':', linewidth=0.8, alpha=0.4, zorder=2)
                    self._affinity_markers.append(m)

    def _toggle_line(self, name):
        if name in self._lines:
            is_visible = self._line_visible.get(name, True)
            self._line_visible[name] = not is_visible
            self._lines[name].set_visible(not is_visible)
            self._build_enabled[name] = not is_visible
            if self._build_names:
                builds_config = self.settings.get('builds', {}) if self.settings else {}
                color_used = set()
                colors = {}
                for i, bn in enumerate(self._build_names):
                    cfg = builds_config.get(bn, {})
                    c = cfg.get('color', None)
                    if c and c not in color_used:
                        color_used.add(c)
                        colors[bn] = c
                    else:
                        for ci in range(100):
                            fallback = COLOR_CYCLE[(i + ci) % len(COLOR_CYCLE)]
                            if fallback not in color_used:
                                color_used.add(fallback)
                                colors[bn] = fallback
                                break
                        else:
                            colors[bn] = COLOR_CYCLE[i % len(COLOR_CYCLE)]
                self._rebuild_legend_panel(self._build_names, colors)
            self.canvas.draw()
            self._rebuild_summary()

    def _toggle_build_check(self, name):
        self._toggle_line(name)

    def _on_hover(self, event):
        if not self.data or not self._lines:
            return

        if event.inaxes != self.ax:
            self._clear_hover()
            return

        tier = self.tier_var.get()
        stat = self.stat_var.get()
        if not tier or tier not in self.data:
            return

        tier_data = self.data[tier]
        all_levels = self._get_plot_levels(tier_data)

        if not all_levels:
            return

        xdata, ydata = event.xdata, event.ydata
        if xdata is None or ydata is None:
            return

        nearest_level = min(all_levels, key=lambda l: abs(l - xdata))
        self._selected_level = nearest_level

        xs = sorted(all_levels)
        if nearest_level not in xs:
            return

        nearest_dist = abs(nearest_level - xdata)

        closest_line = None
        closest_dist = float('inf')
        for name, line in self._lines.items():
            if not line.get_visible():
                continue
            if name in tier_data and nearest_level in tier_data[name]:
                val = tier_data[name][nearest_level][stat]
                ldist = abs(val - ydata)
                if ldist < closest_dist:
                    closest_dist = ldist
                    closest_line = name

        for name, line in self._lines.items():
            if not line.get_visible():
                continue
            if closest_line and name == closest_line:
                line.set_alpha(FOCUSED_ALPHA)
                line.set_linewidth(line.get_linewidth())
            else:
                line.set_alpha(HOVER_ALPHA + 0.2)

        if self._vline:
            self._vline.remove()
        self._vline = self.ax.axvline(x=nearest_level, color='#888888',
                                       linestyle=':', linewidth=1.2, alpha=0.7, zorder=3)

        self._update_hover_summary(nearest_level, tier, stat, tier_data)
        self.canvas.draw_idle()

    def _update_hover_summary(self, level, tier, stat, tier_data):
        pass

    def _on_leave_axes(self, event):
        self._clear_hover()

    def _clear_hover(self):
        for name, line in self._lines.items():
            if not line.get_visible():
                continue
            line.set_alpha(FOCUSED_ALPHA)
        if self._vline:
            try:
                self._vline.remove()
            except NotImplementedError:
                pass
            self._vline = None
        self._selected_level = None
        self.canvas.draw_idle()

    def _clear_click_annotation(self):
        if self._click_annotation:
            try:
                self._click_annotation.remove()
            except:
                pass
            self._click_annotation = None
        if self._click_marker:
            try:
                self._click_marker.remove()
            except:
                pass
            self._click_marker = None

    def _on_click(self, event):
        if event.inaxes != self.ax:
            return
        if not self.data:
            return

        self._clear_click_annotation()

        tier = self.tier_var.get()
        if not tier or tier not in self.data:
            return

        tier_data = self.data[tier]
        stat = self.stat_var.get()
        all_levels = self._get_plot_levels(tier_data)
        if not all_levels:
            return

        xdata, ydata = event.xdata, event.ydata
        if xdata is None or ydata is None:
            self.canvas.draw_idle()
            return

        nearest_level = min(all_levels, key=lambda l: abs(l - xdata))

        for name, line in self._lines.items():
            if not line.get_visible():
                continue
            contains, _ = line.contains(event)
            if contains:
                bd = tier_data[name][nearest_level]
                val = bd[stat]
                self._click_marker, = self.ax.plot(
                    nearest_level, val, 'o',
                    color=line.get_color(),
                    markersize=10, markeredgecolor='black',
                    markeredgewidth=1.5, zorder=9
                )
                lines = [f"{name} @ Level {nearest_level}"]
                lines.append(f"{'─'*30}")
                lines.append(f"{'Stat':12s} {'Value':>6s}")
                for sk in ['STR', 'DEX', 'CON', 'WIS', 'INT', 'CHA']:
                    lines.append(f"  {sk:10s}: {bd.get(sk,0):>3d}")
                lines.append(f"{'─'*30}")
                lines.append(f"{'Combat':12s} {'Value':>6s}")
                for sk in ['Vitality', 'Health', 'Mana', 'AC']:
                    lines.append(f"  {sk:10s}: {bd.get(sk,0):>3d}")
                lines.append(f"  To Hit    : {bd.get('To Hit',0):>3d}")
                lines.append(f"  AP        : {bd.get('AP',0):>3d}  BAp: {bd.get('BAp',0)}")
                lines.append(f"{'─'*30}")
                lines.append(f"{'Damage':12s} {'Value':>6s}")
                lines.append(f"  Dmg/Turn  : {bd.get('Dmg/Turn',0):>6d}")
                lines.append(f"  Dmg/5R    : {bd.get('Dmg/5R',0):>6d}")
                lines.append(f"  Dmg/10R   : {bd.get('Dmg/10R',0):>6d}")
                mc = bd.get('ManaCost', 0)
                if mc > 0:
                    spell_name = bd.get('SpellName', '')
                    spell_elem = bd.get('SpellElement', '')
                    if spell_name:
                        elem_str = f" ({spell_elem})" if spell_elem else ''
                        lines.append(f"Spell      : {spell_name}{elem_str}")
                    sspell = bd.get('SecondarySpell', '')
                    scasts = bd.get('SecondaryCasts', 0)
                    if sspell:
                        lines.append(f"Secondary  : {sspell} x{scasts}")
                    mana_total = bd.get('Mana', 0)
                    ms5, me5 = bd.get('ManaStart5R', 0), bd.get('ManaEnd5R', 0)
                    ms10, me10 = bd.get('ManaStart10R', 0), bd.get('ManaEnd10R', 0)
                    u5, u10 = ms5 - me5, ms10 - me10
                    p5 = u5 / ms5 * 100 if ms5 > 0 else 0
                    p10 = u10 / ms10 * 100 if ms10 > 0 else 0
                    lines.append(f"{'─'*30}")
                    lines.append(f"Mana/Cast  : {mc:>3d}  Pool: {mana_total}")
                    lines.append(f"5R Mana    : {ms5}→{me5} (used {u5}, {p5:.0f}%)")
                    lines.append(f"10R Mana   : {ms10}→{me10} (used {u10}, {p10:.0f}%)")
                    cd = bd.get('CondDmg', 0)
                    cn = bd.get('CondNames', [])
                    if cd > 0:
                        lines.append(f"{'─'*30}")
                        lines.append(f"Cond Dmg   : +{cd:.1f}/cast from {', '.join(cn)}")
                xlim = self.ax.get_xlim()
                ylim = self.ax.get_ylim()
                xmid = (xlim[0] + xlim[1]) / 2
                ymid = (ylim[0] + ylim[1]) / 2
                if nearest_level < xmid:
                    tx, ha = 0.98, 'right'
                else:
                    tx, ha = 0.02, 'left'
                if val > ymid:
                    ty, va = 0.98, 'top'
                else:
                    ty, va = 0.02, 'bottom'
                self._click_annotation = self.ax.annotate(
                    "\n".join(lines),
                    xy=(nearest_level, val), xycoords='data',
                    xytext=(tx, ty), textcoords='axes fraction',
                    ha=ha, va=va,
                    annotation_clip=False,
                    bbox=dict(boxstyle='round,pad=0.4',
                              facecolor='#2d2d30', edgecolor='#888888',
                              alpha=0.95),
                    arrowprops=dict(arrowstyle='->',
                                    connectionstyle='arc3,rad=0',
                                    color='#555555'),
                    fontsize=8, fontfamily='monospace', zorder=10
                )
                self.canvas.draw_idle()
                return

        self.canvas.draw_idle()

    def _on_file_select(self, event):
        if self.current_file:
            self.editor_buffers[self.current_file] = self.editor_text.get('1.0', tk.END).strip()

        sel = self.file_listbox.curselection()
        if not sel:
            return
        fname = self.file_listbox.get(sel[0])
        self.current_file = fname

        if fname in self.editor_buffers:
            content = self.editor_buffers[fname]
        elif fname in self.original_backups:
            content = self.original_backups[fname]
        else:
            path = os.path.join(DATA_DIR, fname)
            try:
                with open(path, 'r') as f:
                    content = f.read()
            except:
                content = ''

        self.editor_text.delete('1.0', tk.END)
        self.editor_text.insert('1.0', content)
        self.editor_dirty[fname] = False

    def _on_editor_change(self, event=None):
        if self.current_file:
            self.editor_dirty[self.current_file] = True

    def _settings_run(self, keep_changes=False):
        if self.generating:
            messagebox.showinfo("Busy", "Generator is already running.")
            return

        try:
            modified_settings = self._build_modified_settings()
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Invalid JSON in editor:\n{e}")
            return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        if keep_changes:
            self._flush_all_buffers()
            self.editor_buffers.clear()

        self._run_generator(custom_settings=modified_settings)

    def _build_modified_settings(self):
        settings = load_settings(DATA_DIR)

        for fname in JSON_FILES:
            key = fname.replace('.json', '')
            content = None

            if fname == self.current_file:
                content = self.editor_text.get('1.0', tk.END).strip()
            elif fname in self.editor_buffers:
                content = self.editor_buffers[fname]

            if content is not None and content:
                try:
                    parsed = json.loads(content)
                    settings[key] = parsed
                except json.JSONDecodeError:
                    if fname == self.current_file:
                        raise

        return settings

    def _get_file_content(self, fname):
        if fname == self.current_file:
            return self.editor_text.get('1.0', tk.END).strip()
        return self.editor_buffers.get(fname, '')

    def _flush_editor_to_file(self, fname=None):
        if fname is None:
            fname = self.current_file
        if not fname:
            return
        content = self._get_file_content(fname)
        if not content:
            return
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            if fname == self.current_file:
                messagebox.showerror("JSON Error", f"Cannot save: invalid JSON:\n{e}")
            return
        path = os.path.join(DATA_DIR, fname)
        with open(path, 'w') as f:
            f.write(content + '\n')
        self.editor_dirty.pop(fname, None)
        self.editor_buffers.pop(fname, None)

    def _flush_all_buffers(self):
        saved = []
        for fname in list(self.editor_buffers.keys()):
            if fname in JSON_FILES:
                self._flush_editor_to_file(fname)
                saved.append(fname)
        if self.current_file and self.current_file not in saved:
            self._flush_editor_to_file(self.current_file)

    def _settings_save(self):
        if not self.current_file:
            messagebox.showinfo("Info", "Select a file to save.")
            return
        self._flush_editor_to_file()
        if self.settings:
            self.settings = load_settings(DATA_DIR)
        messagebox.showinfo("Saved", f"{self.current_file} saved to disk.")

    def _settings_restore(self):
        if not messagebox.askyesno("Restore", "Restore all JSON files to original backups?"):
            return
        restore_backup()
        self.original_backups = get_original_backup()
        self.editor_buffers.clear()
        self.editor_dirty.clear()
        if self.current_file and self.current_file in self.original_backups:
            self.editor_text.delete('1.0', tk.END)
            self.editor_text.insert('1.0', self.original_backups[self.current_file])
        self.settings = load_settings(DATA_DIR)
        self._run_generator()
        messagebox.showinfo("Restored", "All files restored from backup. Generator re-running.")

    def _view_graph(self):
        self.notebook.select(0)
        self._update_graph()


def main():
    root = tk.Tk()
    app = CharacterManagerGUI(root)

    def on_close():
        try:
            plt.close('all')
        except:
            pass
        root.quit()
        root.destroy()
        os._exit(0)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
