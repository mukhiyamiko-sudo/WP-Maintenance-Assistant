from __future__ import annotations

from typing import Any


def _discard_automation_handle(manager: Any, handle: str) -> None:
    handles = getattr(manager, "automation_handles", None)
    discard = getattr(handles, "discard", None)
    if callable(discard):
        discard(handle)


def _window_handles(driver: Any) -> list[str]:
    try:
        return list(getattr(driver, "window_handles", []) or [])
    except Exception:
        return []


def _switch_to_window(driver: Any, handle: str) -> bool:
    switch_to = getattr(driver, "switch_to", None)
    window = getattr(switch_to, "window", None)
    if not callable(window):
        return False
    try:
        window(handle)
        return True
    except Exception:
        return False


def _best_effort_close_and_restore(manager: Any, handle: str) -> None:
    driver = getattr(manager, "driver", None)
    if driver is None:
        _discard_automation_handle(manager, handle)
        return

    handles = _window_handles(driver)
    if handle in handles and _switch_to_window(driver, handle):
        close = getattr(driver, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    hostinger_handle = getattr(manager, "hostinger_handle", None)
    handles = _window_handles(driver)
    if hostinger_handle and hostinger_handle in handles:
        _switch_to_window(driver, hostinger_handle)

    _discard_automation_handle(manager, handle)


def apply_safe_close_tab_patch() -> None:
    from core.browser_manager import BrowserManager

    original_close_tab = BrowserManager.close_tab
    if getattr(original_close_tab, "_wpautomation_safe_close_patch", False):
        return

    def safe_close_tab(self: Any, handle: str) -> None:
        try:
            original_close_tab(self, handle)
        except TypeError as exc:
            if "NoneType" not in str(exc) or "callable" not in str(exc):
                raise
            _best_effort_close_and_restore(self, handle)

    safe_close_tab._wpautomation_safe_close_patch = True  # type: ignore[attr-defined]
    BrowserManager.close_tab = safe_close_tab
