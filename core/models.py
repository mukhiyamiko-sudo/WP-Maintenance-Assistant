from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Site:
    domain: str
    wp_admin_url: str
    selected: bool = False


@dataclass
class SiteResult:
    domain: str
    success: bool
    core_updated: bool = False
    plugins_updated: list[str] = field(default_factory=list)
    themes_updated: list[str] = field(default_factory=list)
    comments_deleted: int = 0
    failure_reason: str | None = None


@dataclass
class RunSummary:
    started_at: str
    finished_at: str
    results: list[SiteResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(result.success for result in self.results)

    @property
    def failure_count(self) -> int:
        return sum(not result.success for result in self.results)


@dataclass
class UpdateState:
    plugin_names: list[str] = field(default_factory=list)
    theme_names: list[str] = field(default_factory=list)
    has_core_update: bool = False
    reinstall_controls_ignored: bool = False


@dataclass
class UpdateOutcome:
    plugin_names: list[str] = field(default_factory=list)
    theme_names: list[str] = field(default_factory=list)
    core_updated: bool = False
