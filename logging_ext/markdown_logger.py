from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from core.models import SiteResult


class MarkdownLogger:
    def __init__(self, log_dir: Path, stamp: str | None = None):
        self.log_dir = Path(log_dir)
        self.stamp = stamp or datetime.now().strftime("%y-%m-%d-%H.%M")
        self.path = self.log_dir / f"{self.stamp}.md"
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.finished_at = ""
        self.successes: list[SiteResult] = []
        self.failures: list[SiteResult] = []

    def start_run(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        index = 1
        while self.path.exists():
            self.path = self.log_dir / f"{self.stamp}-{index:02d}.md"
            index += 1
        self._write()

    def record_success(self, result: SiteResult) -> None:
        self.successes.append(result)
        self._write()

    def record_failure(self, result: SiteResult) -> None:
        self.failures.append(result)
        self._write()

    def finish(self) -> None:
        self.finished_at = datetime.now().isoformat(timespec="seconds")
        self._write()

    def _write(self) -> None:
        if not self.log_dir.exists():
            return
        lines = ["# Maintenance run", "", f"- Started: {self.started_at}", f"- Finished: {self.finished_at or 'running'}", "", "## Successful sites"]
        for result in self.successes:
            lines.extend([f"- {result.domain}", f"  - Core updated: {'yes' if result.core_updated else 'no'}", f"  - Plugins: {', '.join(result.plugins_updated) or 'none'}", f"  - Themes: {', '.join(result.themes_updated) or 'none'}", f"  - Comments permanently deleted: {result.comments_deleted}"])
        lines.extend(["", "## Failed sites"])
        lines.extend(f"- {result.domain}: {result.failure_reason or 'unknown'}" for result in self.failures)
        lines.extend(["", f"- Success: {len(self.successes)}", f"- Failure: {len(self.failures)}", ""])
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text("\n".join(lines), encoding="utf-8")
        os.replace(temp, self.path)
