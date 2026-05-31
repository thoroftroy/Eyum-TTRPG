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
from lib.gear import resolve_gear

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
    'rules.json', 'weapons.json', 'armor_types.json', 'paths.json',
    'gear_tiers.json', 'races.json', 'builds.json', 'spells.json',
    'feats.json', 'generation.json'
]

AVG_LINE_COLOR = '#333333'
AVG_LINE_WIDTH = 3.5
AVG_LINE_STYLE = '--'
HOVER_ALPHA = 0.15
FOCUSED_ALPHA = 1.0

plt.rcParams['figure.facecolor'] = '#fafafa'
plt.rcParams['axes.facecolor'] = '#fafafa'
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.alpha'] = 0.3


def create_backup():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    for fname in JSON_FILES:
        src = os.path.join(DATA_DIR, fname)
        dst = os.path.join(BACKUP_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)


def restore_backup():
    if not os.path.exists(BACKUP_DIR):
        return False
    for fname in JSON_FILES:
        src = os.path.join(BACKUP_DIR, fname)
        dst = os.path.join(DATA_DIR, fname)
        if os.path.exists(src):
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
            'ManaCost': int(d.get('mana_cost', 0)),
            'ManaStart5R': int(d5.get('mana_start', 0)),
            'ManaEnd5R': int(d5.get('mana_end', 0)),
            'ManaStart10R': int(d10.get('mana_start', 0)),
            'ManaEnd10R': int(d10.get('mana_end', 0)),
        }
    return build_data, levels


def collect_all_data(settings, progress_callback=None):
    script_dir = SCRIPT_DIR
    base_output_dir = os.path.join(script_dir, "output")
    os.makedirs(base_output_dir, exist_ok=True)

    levels = settings['generation']['levels']
    gear_tiers = settings.get('gear_tiers', [{"name": "bad_gear", "label": "Bad Gear (Iron/Base)"}])

    all_collected = OrderedDict()
    total_builds = sum(1 for b in settings['builds'].values() if b.get('generate', True)) * len(gear_tiers)
    completed = 0

    for tier in gear_tiers:
        tier_name = tier['name']
        tier_label = tier['label']
        tier_dir = os.path.join(base_output_dir, tier_name)
        os.makedirs(tier_dir, exist_ok=True)

        tier_data = OrderedDict()
        all_level_data = []

        for build_name, build_config in settings['builds'].items():
            if not build_config.get('generate', True):
                continue

            if progress_callback:
                progress_callback(completed, total_builds, f"Generating {build_name} ({tier_label})...")

            gear_override = resolve_gear(build_config, tier) if 'gear' in build_config else None

            from generator import generate_build
            results = generate_build(build_name, build_config, settings, levels, gear_override, tier_label)
            build_data, build_levels = extract_build_data(settings, results)

            flattened = {}
            for lvl in sorted(build_data.keys()):
                flattened[lvl] = build_data[lvl]
            tier_data[build_name] = flattened
            all_level_data.append((build_name, flattened))
            completed += 1

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
    def __init__(self, root):
        self.root = root
        self.root.title("Eyum TTRPG Character Manager - Balance Visualizer")
        self.root.geometry("1400x900")
        self.root.minsize(1000, 650)

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
        self._focused_line_name = None
        self._selected_level = None
        self._click_annotation = None
        self._click_marker = None
        self._level_limit_enabled = False

        self._build_notebook()
        self._create_graph_tab()
        self._create_settings_tab()
        self._create_menu()

        create_backup()
        self.original_backups = get_original_backup()

        self.root.after(500, self._initial_generate)

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
        file_menu.add_command(label="Switch to Settings", command=lambda: self.notebook.select(1), accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Graph View", command=lambda: self.notebook.select(0), accelerator="Ctrl+G")
        view_menu.add_command(label="Settings Editor", command=lambda: self.notebook.select(1), accelerator="Ctrl+E")

        gen_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Generate", menu=gen_menu)
        gen_menu.add_command(label="Run Generator Now", command=self._run_generator_from_ui, accelerator="Ctrl+R")
        gen_menu.add_command(label="Settings → Run Generator", command=lambda: self._settings_run(keep_changes=False))

        self.root.bind_all('<Control-r>', lambda e: self._run_generator_from_ui())
        self.root.bind_all('<Control-g>', lambda e: self.notebook.select(0))
        self.root.bind_all('<Control-e>', lambda e: self.notebook.select(1))

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

        self.limit_btn = ttk.Checkbutton(
            toolbar_frame, text="Levels 1-30",
            command=self._toggle_level_limit
        )
        self.limit_btn.pack(side=tk.LEFT, padx=5)

        main_frame = ttk.Frame(self.graph_frame)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.fig.subplots_adjust(left=0.08, right=0.97, top=0.95, bottom=0.08)

        self.canvas = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        nav_frame = ttk.Frame(main_frame)
        nav_frame.pack(fill=tk.X)
        self.nav_toolbar = NavigationToolbar2Tk(self.canvas, nav_frame)
        self.nav_toolbar.update()

        self._setup_interactions()

        summary_frame = ttk.Frame(self.graph_frame)
        summary_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        self.summary_canvas = tk.Canvas(summary_frame, height=65, highlightthickness=0)
        self.summary_scroll = ttk.Scrollbar(summary_frame, orient=tk.HORIZONTAL, command=self.summary_canvas.xview)
        self.summary_inner = ttk.Frame(self.summary_canvas)

        self.summary_inner.bind('<Configure>', lambda e: self.summary_canvas.configure(
            scrollregion=self.summary_canvas.bbox('all')
        ))
        self.summary_canvas.create_window((0, 0), window=self.summary_inner, anchor='nw', tags='inner')
        self.summary_canvas.configure(xscrollcommand=self.summary_scroll.set)

        self.summary_canvas.pack(fill=tk.X, expand=True)
        self.summary_scroll.pack(fill=tk.X)

    def _create_settings_tab(self):
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings Editor")

        main_pane = ttk.PanedWindow(self.settings_frame, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_pane, width=220)
        main_pane.add(left_frame, weight=0)

        ttk.Label(left_frame, text="Data Files", font=('', 10, 'bold')).pack(anchor=tk.W, padx=5, pady=3)

        self.file_listbox = tk.Listbox(left_frame, exportselection=False)
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

        self.editor_text = tk.Text(right_frame, wrap=tk.NONE, font=('Courier', 10))
        self.editor_text.pack(fill=tk.BOTH, expand=True)

        self.editor_text.bind('<KeyRelease>', self._on_editor_change)

        h_scroll = ttk.Scrollbar(right_frame, orient=tk.HORIZONTAL, command=self.editor_text.xview)
        v_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.editor_text.yview)
        self.editor_text.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        h_scroll.pack(fill=tk.X)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _setup_interactions(self):
        self.canvas.mpl_connect('motion_notify_event', self._on_hover)
        self.canvas.mpl_connect('axes_leave_event', self._on_leave_axes)
        self.canvas.mpl_connect('button_press_event', self._on_click)

    def _initial_generate(self):
        self._run_generator()

    def _run_generator_from_ui(self):
        if self.settings is None:
            self._run_generator()
        else:
            self._run_generator()

    def _run_generator(self, custom_settings=None):
        if self.generating:
            messagebox.showinfo("Busy", "Generator is already running.")
            return

        def progress(cur, total, msg):
            self.root.after(0, lambda: self._update_progress(cur, total, msg))

        def _reenable():
            self.generating = False
            self.run_btn.config(state=tk.NORMAL)
            self.settings_run_btn.config(state=tk.NORMAL)
            self.settings_run_temp_btn.config(state=tk.NORMAL)

        def done(data):
            self.data = data
            tiers = list(data.keys())
            self.tier_combo['values'] = tiers
            if self.current_tier is None or self.current_tier not in tiers:
                self.current_tier = tiers[0]
                self.tier_var.set(tiers[0])
            else:
                self.tier_var.set(self.current_tier)
            self._update_graph()
            self.status_label.config(text="Ready")
            self.settings_status.config(text="Ready")
            _reenable()

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
                result = collect_all_data(settings, progress)
                self.root.after(0, lambda: done(result))
            except Exception as e:
                self.root.after(0, lambda: error(e))

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
        if self._level_limit_enabled:
            all_levels = [l for l in all_levels if 1 <= l <= 30]
        return all_levels

    def _toggle_level_limit(self):
        self._level_limit_enabled = not self._level_limit_enabled
        self._update_graph()

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
        self._lines = {}
        self._line_visible = {}
        self._focused_line_name = None
        self._selected_level = None

        build_names = [k for k in tier_data.keys() if k != '__average__']
        colors = {name: COLOR_CYCLE[i % len(COLOR_CYCLE)]
                  for i, name in enumerate(build_names)}

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
            self._line_visible[name] = True

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

        leg = self.ax.legend(
            loc='upper left', fontsize=8, framealpha=0.85,
            edgecolor='#cccccc'
        )
        leg.set_draggable(True)

        for leg_line, orig_label in zip(leg.get_lines(), [t.get_text() for t in leg.get_texts()]):
            leg_line.set_picker(True)
            leg_line.set_pickradius(5)
            leg_line.set_linewidth(3)
            leg_line._leg_label = orig_label

        self.ax.set_xlabel('Level', fontsize=11)
        self.ax.set_ylabel(STAT_LABELS.get(stat, stat), fontsize=11)
        self.ax.set_title(f'{STAT_LABELS.get(stat, stat)} by Level — {tier.replace("_", " ").title()}',
                          fontsize=13, fontweight='bold')

        self.ax.set_xlim(min(all_levels) - 1, max(all_levels) + 1)
        self.ax.tick_params(labelsize=9)

        self._rebuild_summary()
        self.canvas.draw()

    def _rebuild_summary(self):
        for w in self.summary_inner.winfo_children():
            w.destroy()

        if self.data is None:
            return

        tier = self.tier_var.get()
        stat = self.stat_var.get()
        if not tier or tier not in self.data:
            return

        tier_data = self.data[tier]
        build_names = [k for k in tier_data.keys() if k != '__average__']
        colors = {name: COLOR_CYCLE[i % len(COLOR_CYCLE)]
                  for i, name in enumerate(build_names)}

        row_frame = ttk.Frame(self.summary_inner)
        row_frame.pack(fill=tk.X, pady=1)

        for name in build_names:
            color = colors[name]
            is_visible = self._line_visible.get(name, True)
            bd = tier_data[name]
            last_lvl = max(bd.keys()) if bd else 0
            last_val = bd[last_lvl][stat] if bd and last_lvl else 0

            frame = ttk.Frame(row_frame)
            frame.pack(side=tk.LEFT, padx=3)

            color_box = tk.Frame(frame, width=16, height=16, bg=color,
                                 highlightbackground='#888', highlightthickness=1)
            color_box.pack(side=tk.LEFT, padx=2)
            color_box.pack_propagate(False)

            name_label = tk.Label(
                frame, text=f"{name}: {last_val}",
                font=('', 8), fg='#666' if not is_visible else '#000',
                cursor='hand2'
            )
            name_label.pack(side=tk.LEFT, padx=2)

            def make_toggle(n):
                return lambda e: self._toggle_line(n)

            frame.bind('<Button-1>', make_toggle(name))
            color_box.bind('<Button-1>', make_toggle(name))
            name_label.bind('<Button-1>', make_toggle(name))

            frame._build_name = name
            frame._orig_bg = None

        if '__average__' in tier_data:
            avg = tier_data['__average__']
            last_lvl = max(avg.keys()) if avg else 0
            last_val = avg[last_lvl][stat] if avg and last_lvl else 0
            is_visible = self._line_visible.get('__average__', True)

            frame = ttk.Frame(row_frame)
            frame.pack(side=tk.LEFT, padx=3)

            color_box = tk.Frame(frame, width=16, height=16, bg='#333',
                                 highlightbackground='#888', highlightthickness=1)
            color_box.pack(side=tk.LEFT, padx=2)
            color_box.pack_propagate(False)

            name_label = tk.Label(
                frame, text=f"Average: {last_val}",
                font=('', 8, 'bold'), fg='#666' if not is_visible else '#000',
                cursor='hand2'
            )
            name_label.pack(side=tk.LEFT, padx=2)

            def make_toggle_avg():
                return lambda e: self._toggle_line('__average__')

            frame._build_name = '__average__'

            frame.bind('<Button-1>', make_toggle_avg())
            color_box.bind('<Button-1>', make_toggle_avg())
            name_label.bind('<Button-1>', make_toggle_avg())

    def _toggle_line(self, name):
        if name in self._lines:
            is_visible = self._line_visible.get(name, True)
            self._line_visible[name] = not is_visible
            self._lines[name].set_visible(not is_visible)
            self.canvas.draw()
            self._rebuild_summary()

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
        for row in self.summary_inner.winfo_children():
            for widget in row.winfo_children():
                name = getattr(widget, '_build_name', None)
                if not name:
                    continue
                if name in tier_data and level in tier_data[name]:
                    val = tier_data[name][level][stat]
                    for child in widget.winfo_children():
                        if isinstance(child, tk.Label):
                            display = name if name != '__average__' else 'Average'
                            child.config(text=f"{display}: {val}")

    def _on_leave_axes(self, event):
        self._clear_hover()

    def _clear_hover(self):
        for name, line in self._lines.items():
            if not line.get_visible():
                continue
            line.set_alpha(FOCUSED_ALPHA)
        if self._vline:
            self._vline.remove()
            self._vline = None
        self._selected_level = None
        if self.data:
            self._rebuild_summary()
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
                lines = [f"{name}: {val}"]
                mc = bd.get('ManaCost', 0)
                if mc > 0:
                    mana_total = bd.get('Mana', 0)
                    ms5, me5 = bd.get('ManaStart5R', 0), bd.get('ManaEnd5R', 0)
                    ms10, me10 = bd.get('ManaStart10R', 0), bd.get('ManaEnd10R', 0)
                    u5, u10 = ms5 - me5, ms10 - me10
                    p5 = u5 / ms5 * 100 if ms5 > 0 else 0
                    p10 = u10 / ms10 * 100 if ms10 > 0 else 0
                    lines.append(f"Mana: {mana_total}  Cost/Cast: {mc}")
                    lines.append(f"5R: {ms5}→{me5} (used {u5}, {p5:.0f}%)")
                    lines.append(f"10R: {ms10}→{me10} (used {u10}, {p10:.0f}%)")
                self._click_annotation = self.ax.annotate(
                    "\n".join(lines),
                    xy=(nearest_level, val),
                    xytext=(12, 12), textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.3',
                              facecolor='#ffffcc', edgecolor='#888888',
                              alpha=0.9),
                    arrowprops=dict(arrowstyle='->',
                                    connectionstyle='arc3,rad=0'),
                    fontsize=9, zorder=10
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
