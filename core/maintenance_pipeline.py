from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from core.browser_manager import BrowserManager
from core.comment_cleaner import CommentCleaner
from core.config import RuntimeConfig
from core.hostinger_manager import HostingerManager
from core.models import Site, SiteResult
from core.wordpress_manager import WordPressManager

ProgressCallback = Callable[[Site, str], None]


@dataclass
class SiteContext:
    site: Site
    driver: object
    config: RuntimeConfig
    manual_prompt: Callable[[str, int], bool] | None = None
    sleeper: Callable[[float], None] | None = None
    progress: ProgressCallback | None = None

    def report(self, message: str) -> None:
        if self.progress:
            self.progress(self.site, message)


class MaintenanceStep(Protocol):
    def run(self, context: SiteContext, result: SiteResult) -> None: ...


class WordPressLoadStep:
    def run(self, context: SiteContext, _result: SiteResult) -> None:
        context.report("Waiting for WordPress admin")
        WordPressManager(context.driver, context.config, sleeper=context.sleeper).wait_until_loaded(context.site.domain, context.manual_prompt)
        context.report("WordPress admin loaded")


class UpdateWordPressStep:
    def run(self, context: SiteContext, result: SiteResult) -> None:
        context.report("Checking WordPress, plugin, theme and translation updates")
        outcome = WordPressManager(context.driver, context.config, sleeper=context.sleeper).update_site(context.site.domain)
        result.core_updated = outcome.core_updated
        result.plugins_updated.extend(outcome.plugin_names)
        result.themes_updated.extend(outcome.theme_names)
        context.report(f"Updates complete: core={'updated' if outcome.core_updated else 'current'}, plugins={len(outcome.plugin_names)}, themes={len(outcome.theme_names)}")


class CleanCommentsStep:
    def run(self, context: SiteContext, result: SiteResult) -> None:
        context.report("Removing comments and emptying trash")
        result.comments_deleted = CommentCleaner(context.driver, context.config, sleeper=context.sleeper).clear_all()
        context.report(f"Comment cleanup complete: {result.comments_deleted}")


def default_maintenance_steps() -> list[MaintenanceStep]:
    return [WordPressLoadStep(), UpdateWordPressStep(), CleanCommentsStep()]


def update_only_steps() -> list[MaintenanceStep]:
    return [WordPressLoadStep(), UpdateWordPressStep()]


def comment_cleanup_steps() -> list[MaintenanceStep]:
    return [WordPressLoadStep(), CleanCommentsStep()]


class SiteMaintenancePipeline:
    def __init__(
        self,
        hostinger: HostingerManager,
        browser: BrowserManager,
        config: RuntimeConfig,
        steps: Sequence[MaintenanceStep] | None = None,
        sleeper: Callable[[float], None] | None = None,
        driver=None,
        progress_callback: ProgressCallback | None = None,
    ):
        self.hostinger = hostinger
        self.browser = browser
        self.config = config
        self.steps = list(steps or default_maintenance_steps())
        self.sleeper = sleeper
        self.driver = driver
        self.progress_callback = progress_callback

    def _report(self, site: Site, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(site, message)

    def run(self, site: Site, manual_prompt=None) -> SiteResult:
        self._report(site, "Opening WordPress admin")
        handle = self.hostinger.open_wordpress_admin(site)
        self.browser.automation_handles.add(handle)
        result = SiteResult(domain=site.domain, success=False)
        context = SiteContext(site, self._driver(), self.config, manual_prompt, self.sleeper, self.progress_callback)
        try:
            self._report(site, "WordPress admin tab opened")
            for step in self.steps:
                step.run(context, result)
            result.success = True
            self._report(site, "Site maintenance complete")
            return result
        finally:
            self._report(site, "Closing site tab")
            self.browser.close_tab(handle)

    def _driver(self):
        driver = self.driver or getattr(self.hostinger, "driver", None) or getattr(self.browser, "driver", None)
        if driver is None:
            raise RuntimeError("Maintenance pipeline has no browser driver")
        return driver
