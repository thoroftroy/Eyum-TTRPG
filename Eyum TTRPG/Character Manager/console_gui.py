#!/usr/bin/env python3
"""Shared console GUI window for updater tools — progress bar + colored log output."""

import tkinter as tk
from tkinter import ttk
import threading
import time
import queue

class ConsoleWindow:
    def __init__(self, title="Updater", width=700, height=450, auto_close=True, close_delay=2):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry(f"{width}x{height}")
        self.root.resizable(True, True)
        self.auto_close = auto_close
        self.close_delay = close_delay
        self._done = False
        self._queue = queue.Queue()

        # Progress bar
        self.progress = ttk.Progressbar(self.root, mode='indeterminate')
        self.progress.pack(fill=tk.X, padx=10, pady=(10, 5))

        # Console text widget
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.console = tk.Text(frame, wrap=tk.WORD, bg='#1a1a2e', fg='#c0c0c0',
                                insertbackground='white', font=('Consolas', 10),
                                yscrollcommand=scrollbar.set, state=tk.DISABLED)
        self.console.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.console.yview)

        # Color tags
        self.console.tag_config('green', foreground='#00ff88')
        self.console.tag_config('red', foreground='#ff5555')
        self.console.tag_config('yellow', foreground='#ffcc00')
        self.console.tag_config('normal', foreground='#c0c0c0')
        self.console.tag_config('bold', foreground='#ffffff', font=('Consolas', 10, 'bold'))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def log(self, text, tag='normal'):
        self._queue.put((text, tag))

    def _process_queue(self):
        while True:
            try:
                text, tag = self._queue.get_nowait()
                self.console.config(state=tk.NORMAL)
                self.console.insert(tk.END, text + '\n', tag)
                self.console.see(tk.END)
                self.console.config(state=tk.DISABLED)
            except queue.Empty:
                break
        if self._done:
            self.progress.stop()
            self.root.after(int(self.close_delay * 1000), self.root.destroy)
        else:
            self.root.after(50, self._process_queue)

    def run(self, worker_func):
        """Start the worker thread and main loop."""
        self.progress.start(10)
        thread = threading.Thread(target=self._worker_wrapper, args=(worker_func,), daemon=True)
        thread.start()
        self.root.after(50, self._process_queue)
        self.root.mainloop()

    def _worker_wrapper(self, worker_func):
        try:
            worker_func(self)
        except Exception as e:
            self.log(f"[ERROR] {e}", 'red')
        self._done = True

    def _on_close(self):
        self._done = True
        self.root.destroy()


def run_with_gui(title, worker_func, auto_close=True, close_delay=2):
    win = ConsoleWindow(title=title, auto_close=auto_close, close_delay=close_delay)
    win.run(worker_func)
