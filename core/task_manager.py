from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime

from core.models import RunSummary, Site, SiteResult


class TaskManager:
    def __init__(self, site_runner: Callable[[Site], SiteResult], logger):
        self.site_runner = site_runner
        self.logger = logger
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()

    def stop(self) -> None:
        self.stop_event.set()

    def _wait_if_paused(self) -> None:
        while self.pause_event.is_set() and not self.stop_event.is_set():
            self.stop_event.wait(0.2)

    def run_selected(self, sites: list[Site]) -> RunSummary:
        selected = [site for site in sites if site.selected]
        if not selected:
            raise ValueError("Select at least one site")
        started = datetime.now().isoformat(timespec="seconds")
        self.stop_event.clear()
        self.logger.start_run()
        results: list[SiteResult] = []
        for site in selected:
            self._wait_if_paused()
            if self.stop_event.is_set():
                break
            try:
                result = self.site_runner(site)
                result.success = True
                self.logger.record_success(result)
            except Exception as exc:
                result = SiteResult(site.domain, False, failure_reason=f"{exc.__class__.__name__}: {exc}")
                self.logger.record_failure(result)
            results.append(result)
        finished = datetime.now().isoformat(timespec="seconds")
        return RunSummary(started, finished, results)
