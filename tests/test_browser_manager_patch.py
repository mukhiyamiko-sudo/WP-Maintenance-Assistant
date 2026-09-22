import unittest

from core.browser_manager import BrowserManager
from core.config import RuntimeConfig


class BrowserManagerCloseTabPatchTests(unittest.TestCase):
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
