from __future__ import annotations

from collections.abc import Callable

from core.browser_manager import BrowserManager
from core.config import RuntimeConfig
from core.errors import BrowserConnectionError
from core.hostinger_manager import HostingerManager
from core.login_gate import LoginGate, LoginStatus
from core.maintenance_pipeline import SiteMaintenancePipeline, comment_cleanup_steps, update_only_steps
from core.models import Site
from core.task_manager import TaskManager
from logging_ext.markdown_logger import MarkdownLogger


class AutomationService:
    def __init__(self, config: RuntimeConfig, driver=None, diagnostic_sink=None, logger_factory=MarkdownLogger, pipeline_factory=SiteMaintenancePipeline, sleeper=None):
        self.config = config
        self.browser = BrowserManager(config, driver=driver, sleeper=sleeper) if driver else BrowserManager(config, sleeper=sleeper)
        self.driver = driver
        self.login_gate = LoginGate(driver) if driver else None
        self.hostinger = HostingerManager(driver, config, diagnostic_sink=diagnostic_sink) if driver else None
        self.diagnostic_sink = diagnostic_sink
        self.logger_factory = logger_factory
        self.pipeline_factory = pipeline_factory
        self.sleeper = sleeper
        self.task_manager = None

    def connect(self):
        self.driver = self.browser.connect()
        self.login_gate = LoginGate(self.driver)
        self.hostinger = HostingerManager(self.driver, self.config, diagnostic_sink=self.diagnostic_sink)
        return self.driver

    def login_status(self) -> LoginStatus:
        if not self.login_gate:
            self.connect()
        return self.login_gate.detect()

    def confirm_login_and_scan(self, confirm_callback: Callable[[], bool]) -> list[Site]:
        if not self.login_gate or not self.hostinger:
            raise BrowserConnectionError("Connect Chrome before scanning")
        self.browser.restore_hostinger_tab()
        self.login_gate.confirm_and_validate(confirm_callback)
        self.hostinger.ensure_list_ready()
        return self.hostinger.scan_all_pages()

    def run_selected(self, sites, manual_prompt=None, progress_callback=None):
        return self._run_with_steps(sites, None, manual_prompt, progress_callback)

    def run_updates(self, sites, manual_prompt=None, progress_callback=None):
        return self._run_with_steps(sites, update_only_steps(), manual_prompt, progress_callback)

    def run_comment_cleanup(self, sites, manual_prompt=None, progress_callback=None):
        return self._run_with_steps(sites, comment_cleanup_steps(), manual_prompt, progress_callback)

    def _run_with_steps(self, sites, steps, manual_prompt, progress_callback):
        if not self.hostinger:
            self.connect()
        logger = self.logger_factory(self.config.log_dir)
        pipeline = self.pipeline_factory(self.hostinger, self.browser, self.config, steps=steps, sleeper=self.sleeper, progress_callback=progress_callback)
        self.task_manager = TaskManager(lambda site: pipeline.run(site, manual_prompt), logger)
        try:
            return self.task_manager.run_selected(sites)
        finally:
            logger.finish()

    def pause(self) -> None:
        if self.task_manager:
            self.task_manager.pause()

    def resume(self) -> None:
        if self.task_manager:
            self.task_manager.resume()

    def stop(self) -> None:
        if self.task_manager:
            self.task_manager.stop()
