from __future__ import annotations

import time
from typing import Any


def _discard_automation_handle(browser: Any, handle: str) -> None:
    handles = getattr(browser, "automation_handles", None)
    discard = getattr(handles, "discard", None)
    if callable(discard):
        discard(handle)


def _is_safe_close_tab_error(exc: BaseException) -> bool:
    message = str(exc)
    return isinstance(exc, TypeError) and "NoneType" in message and "callable" in message


def _close_tab_without_masking_result(pipeline: Any, handle: str) -> None:
    try:
        pipeline.browser.close_tab(handle)
    except Exception as exc:
        _discard_automation_handle(pipeline.browser, handle)
        if not _is_safe_close_tab_error(exc):
            raise


def _safe_sleeper(value: Any) -> Any:
    return value if callable(value) else time.sleep


def apply_safe_pipeline_close_patch() -> None:
    from core.maintenance_pipeline import SiteContext, SiteMaintenancePipeline
    from core.models import SiteResult

    original_run = SiteMaintenancePipeline.run
    if getattr(original_run, "_wpautomation_safe_pipeline_close_patch", False):
        return

    def safe_run(self: Any, site: Any, manual_prompt: Any = None) -> Any:
        handle = None
        try:
            self._report(site, "正在打开 WordPress 后台")
            handle = self.hostinger.open_wordpress_admin(site)
            self.browser.automation_handles.add(handle)
            self._report(site, "WordPress 后台标签页已打开")

            result = SiteResult(domain=site.domain, success=True)
            context = SiteContext(
                site=site,
                driver=self._driver(),
                config=self.config,
                manual_prompt=manual_prompt,
                sleeper=_safe_sleeper(getattr(self, "sleeper", None)),
                progress=self.progress_callback,
            )

            for step in self.steps:
                step.run(context, result)

            self._report(site, "当前网站更新和删除已完成")
            return result
        finally:
            if handle:
                self._report(site, "正在关闭当前网站标签页")
                _close_tab_without_masking_result(self, handle)

    safe_run._wpautomation_safe_pipeline_close_patch = True  # type: ignore[attr-defined]
    SiteMaintenancePipeline.run = safe_run
