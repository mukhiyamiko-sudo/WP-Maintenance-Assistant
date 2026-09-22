from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from core.app_service import AutomationService
from core.config import RuntimeConfig
from gui.site_selection import resolve_action_sites


class HostingerAutomationApp(tk.Tk):
    def __init__(self, service_factory=AutomationService):
        super().__init__()
        self.title("Hostinger WordPress Maintenance Toolkit")
        self.geometry("980x680")
        self.minsize(780, 560)
        self.service_factory = service_factory
        self.service = None
        self.sites = []
        self.events: queue.Queue = queue.Queue()
        self.status_var = tk.StringVar(value="Connect Chrome, sign in manually, then scan your sites.")
        self.summary_var = tk.StringVar(value="No scan yet")
        self._build_ui()
        self.after(100, self._drain_events)

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=12)
        header.pack(fill=tk.X)
        ttk.Label(header, textvariable=self.status_var).pack(side=tk.LEFT)
        self.connect_button = ttk.Button(header, text="Connect Chrome", command=self.connect)
        self.connect_button.pack(side=tk.RIGHT, padx=4)
        self.scan_button = ttk.Button(header, text="I am signed in - scan", command=self.scan, state=tk.DISABLED)
        self.scan_button.pack(side=tk.RIGHT, padx=4)

        actions = ttk.Frame(self, padding=(12, 0, 12, 8))
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="Select all", command=lambda: self._set_all(True)).pack(side=tk.LEFT)
        ttk.Button(actions, text="Clear", command=lambda: self._set_all(False)).pack(side=tk.LEFT, padx=4)
        self.run_button = ttk.Button(actions, text="Update and clean comments", command=self.run_selected, state=tk.DISABLED)
        self.run_button.pack(side=tk.LEFT, padx=12)
        ttk.Button(actions, text="Pause", command=self.pause).pack(side=tk.LEFT)
        ttk.Button(actions, text="Resume", command=self.resume).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Stop", command=self.stop).pack(side=tk.LEFT)
        ttk.Button(actions, text="Open logs", command=self.open_log_dir).pack(side=tk.RIGHT)
        ttk.Label(actions, textvariable=self.summary_var).pack(side=tk.RIGHT, padx=12)

        body = ttk.Frame(self, padding=(12, 0, 12, 8))
        body.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(body, columns=("selected", "domain", "status"), show="headings", height=13)
        self.tree.heading("selected", text="Use")
        self.tree.heading("domain", text="Site")
        self.tree.heading("status", text="Status")
        self.tree.column("selected", width=60, anchor=tk.CENTER, stretch=False)
        self.tree.column("domain", width=360)
        self.tree.column("status", width=420)
        self.tree.bind("<Button-1>", self._toggle_site)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)

        self.log = tk.Text(self, height=12, state=tk.DISABLED, wrap="word")
        self.log.pack(fill=tk.BOTH, padx=12, pady=(0, 12))

    def _worker(self, target) -> None:
        def run():
            try:
                target()
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=run, daemon=True).start()

    def connect(self) -> None:
        self.connect_button.configure(state=tk.DISABLED)
        self.status_var.set("Connecting to Chrome...")

        def work():
            self.service = self.service_factory(RuntimeConfig(), diagnostic_sink=lambda data: self.events.put(("diagnostic", data)))
            self.service.connect()
            self.events.put(("connected", None))
        self._worker(work)

    def scan(self) -> None:
        self.scan_button.configure(state=tk.DISABLED)
        self.status_var.set("Scanning Hostinger sites...")

        def work():
            self.sites = self.service.confirm_login_and_scan(lambda: True)
            self.events.put(("sites", self.sites))
        self._worker(work)

    def run_selected(self) -> None:
        highlighted = [self.tree.item(item, "values")[1] for item in self.tree.selection()]
        selected = resolve_action_sites(self.sites, highlighted)
        if not selected:
            messagebox.showwarning("No sites selected", "Select at least one site before starting.")
            return
        for site in self.sites:
            site.selected = site in selected
        self.run_button.configure(state=tk.DISABLED)
        self.summary_var.set(f"Running {len(selected)} sites...")

        def prompt(domain: str, seconds: int) -> bool:
            response: queue.Queue = queue.Queue(maxsize=1)
            self.events.put(("prompt", (domain, seconds, response)))
            try:
                return bool(response.get(timeout=seconds))
            except queue.Empty:
                return False

        def progress(site, message):
            self.events.put(("progress", (site.domain, message)))

        def work():
            summary = self.service.run_selected(self.sites, manual_prompt=prompt, progress_callback=progress)
            self.events.put(("done", summary))
        self._worker(work)

    def pause(self) -> None:
        if self.service:
            self.service.pause()
            self._append_log("Paused")

    def resume(self) -> None:
        if self.service:
            self.service.resume()
            self._append_log("Resumed")

    def stop(self) -> None:
        if self.service:
            self.service.stop()
            self._append_log("Stop requested")

    def _toggle_site(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if not row or self.tree.identify_column(event.x) != "#1":
            return
        for site in self.sites:
            if site.domain == row:
                site.selected = not site.selected
                self._refresh_row(site)
                break

    def _set_all(self, selected: bool) -> None:
        for site in self.sites:
            site.selected = selected
            self._refresh_row(site)

    def _refresh_row(self, site, status: str = "") -> None:
        values = ("☑" if site.selected else "☐", site.domain, status)
        if self.tree.exists(site.domain):
            self.tree.item(site.domain, values=values)
        else:
            self.tree.insert("", tk.END, iid=site.domain, values=values)

    def open_log_dir(self) -> None:
        path = Path(self.service.config.log_dir if self.service else RuntimeConfig().log_dir)
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "connected":
                    self.status_var.set("Chrome connected. Complete manual sign-in, then scan.")
                    self.scan_button.configure(state=tk.NORMAL)
                elif kind == "sites":
                    for item in self.tree.get_children():
                        self.tree.delete(item)
                    for site in payload:
                        self._refresh_row(site)
                    self.status_var.set(f"Found {len(payload)} WordPress sites")
                    self.summary_var.set(f"{len(payload)} sites")
                    self.run_button.configure(state=tk.NORMAL if payload else tk.DISABLED)
                elif kind == "progress":
                    domain, message = payload
                    site = next((item for item in self.sites if item.domain == domain), None)
                    if site:
                        self._refresh_row(site, message)
                    self._append_log(f"{domain}: {message}")
                elif kind == "prompt":
                    domain, seconds, response = payload
                    response.put(messagebox.askyesno("Manual check needed", f"Complete any login or verification for {domain} in Chrome, then click Yes within {seconds} seconds."))
                elif kind == "done":
                    self.summary_var.set(f"Complete: {payload.success_count} successful, {payload.failure_count} failed")
                    self.run_button.configure(state=tk.NORMAL)
                elif kind == "diagnostic":
                    self._append_log("Scan diagnostic captured (private values are kept local).")
                elif kind == "error":
                    self.status_var.set(f"Task failed: {payload}")
                    self._append_log(f"Error: {payload}")
                    self.connect_button.configure(state=tk.NORMAL)
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _append_log(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)


def main() -> None:
    HostingerAutomationApp().mainloop()
