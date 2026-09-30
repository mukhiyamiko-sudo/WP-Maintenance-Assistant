import os
import unittest
from pathlib import Path

from core.browser_manager import BrowserManager
from core.config import RuntimeConfig


class BrowserManagerCloseTabPatchTests(unittest.TestCase):
    def test_default_driver_uses_private_selenium_manager_cache(self):
        from core import browser_manager
        from core.browser_manager_patch import apply_safe_close_tab_patch

        original_paths = browser_manager.default_chromedriver_paths
        try:
            apply_safe_close_tab_patch()

            self.assertEqual(browser_manager.default_chromedriver_paths(), [])
            self.assertEqual(os.environ["SE_AVOID_STATS"], "true")
            self.assertEqual(os.environ["SE_AVOID_BROWSER_DOWNLOAD"], "true")
            self.assertEqual(os.environ["SE_SKIP_DRIVER_IN_PATH"], "true")
            self.assertEqual(
                Path(os.environ["SE_CACHE_PATH"]),
                browser_manager.runtime_base_dir() / "driver_cache",
            )
        finally:
            browser_manager.default_chromedriver_paths = original_paths

    def test_none_sleeper_uses_default(self):
        manager = BrowserManager(RuntimeConfig(), sleeper=None)

        self.assertTrue(callable(manager.sleeper))

    def test_close_tab_none_callable_error_is_cleanup_only_and_does_not_fail_site(self):
        from core.browser_manager_patch import apply_safe_close_tab_patch

        original_close_tab = BrowserManager.close_tab
        try:
            def broken_close_tab(self, handle):
                raise TypeError("'NoneType' object is not callable")

            BrowserManager.close_tab = broken_close_tab
            apply_safe_close_tab_patch()

            manager = object.__new__(BrowserManager)
            manager.automation_handles = {"site-tab"}
            manager.driver = None
            manager.hostinger_handle = "hostinger-tab"

            BrowserManager.close_tab(manager, "site-tab")

            self.assertEqual(manager.automation_handles, set())
        finally:
            BrowserManager.close_tab = original_close_tab


if __name__ == "__main__":
    unittest.main()
