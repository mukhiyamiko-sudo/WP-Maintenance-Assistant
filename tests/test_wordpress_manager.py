import unittest
from types import SimpleNamespace

from core.models import UpdateState
from core.wordpress_manager import WordPressManager


class WordPressUpdateLoopTests(unittest.TestCase):
    def test_open_admin_page_reads_state_from_reloaded_updates_page(self):
        class FakeDriver:
            def __init__(self):
                self.page = "plugin-result"
                self.dashboard_clicks = 0
                self.update_clicks = 0

            def execute_script(self, script, *_args):
                if "WP_AUTOMATION_OPEN_ADMIN_PAGE_V2" in script:
                    return "https://example.com/wp-admin/update-core.php"
                if "WP_AUTOMATION_DASHBOARD_NAV_V4" in script:
                    self.dashboard_clicks += 1
                    self.page = "dashboard"
                    return True
                if "WP_AUTOMATION_UPDATES_NAV_V4" in script:
                    self.update_clicks += 1
                    self.page = "updates"
                    return True
                if "WP_AUTOMATION_ADMIN_PAGE_READY_V4" in script:
                    expected_page = _args[0]
                    return (self.page, expected_page) in {
                        ("dashboard", "index.php"),
                        ("updates", "update-core.php"),
                    }
                if script == "return document.readyState":
                    return "complete"
                if "WP_AUTOMATION_UPDATE_STATE_V2" in script:
                    if self.page == "updates":
                        return {
                            "plugin_names": [],
                            "theme_names": ["Theme A"],
                            "has_core_update": False,
                        }
                    return {
                        "plugin_names": [],
                        "theme_names": [],
                        "has_core_update": False,
                    }
                raise AssertionError("Unexpected script")

            def get(self, url):
                self.page = "updates" if url.endswith("/wp-admin/update-core.php") else self.page

        manager = WordPressManager(
            driver=FakeDriver(),
            config=SimpleNamespace(first_load_timeout=1),
            sleeper=lambda _seconds: None,
        )

        manager.open_admin_page("update-core.php")

        self.assertEqual(manager.read_update_state().theme_names, ["Theme A"])
        self.assertEqual(manager.driver.dashboard_clicks, 1)
        self.assertEqual(manager.driver.update_clicks, 1)

    def test_update_wait_uses_default_sleep_when_sleeper_is_none(self):
        class FakeDriver:
            def execute_script(self, script, *_args):
                if "WP_AUTOMATION_UPDATE_COMPLETE_V4" in script:
                    return True
                raise AssertionError("Unexpected script")

        manager = WordPressManager(
            driver=FakeDriver(),
            config=SimpleNamespace(update_wait_max=1),
            sleeper=None,
        )

        manager._wait_after_update("plugins")

    def test_rechecks_updates_from_dashboard_before_declaring_site_clean(self):
        class FakeDriver:
            def __init__(self):
                self.page = "plugin-result"
                self.dashboard_clicks = 0
                self.update_clicks = 0

            def execute_script(self, script, *_args):
                if "WP_AUTOMATION_OPEN_ADMIN_PAGE_V2" in script:
                    return "https://example.com/wp-admin/update-core.php"
                if "WP_AUTOMATION_DASHBOARD_NAV_V4" in script:
                    self.dashboard_clicks += 1
                    self.page = "dashboard"
                    return True
                if "WP_AUTOMATION_UPDATES_NAV_V4" in script:
                    self.update_clicks += 1
                    self.page = "updates"
                    return True
                if "WP_AUTOMATION_ADMIN_PAGE_READY_V4" in script:
                    expected_page = _args[0]
                    return (self.page, expected_page) in {
                        ("dashboard", "index.php"),
                        ("updates", "update-core.php"),
                    }
                if script == "return document.readyState":
                    return "complete"
                if "WP_AUTOMATION_UPDATE_STATE_V2" in script:
                    return {
                        "plugin_names": [],
                        "theme_names": [],
                        "has_core_update": False,
                    }
                if "WP_AUTOMATION_TRANSLATION_UPDATE_V1" in script:
                    return False
                if "WP_AUTOMATION_UPDATES_BADGE_V1" in script:
                    return {"count": 0}
                raise AssertionError("Unexpected script")

            def get(self, _url):
                self.page = "updates"

        driver = FakeDriver()
        manager = WordPressManager(
            driver=driver,
            config=SimpleNamespace(first_load_timeout=1),
            sleeper=lambda _seconds: None,
        )

        manager.update_site("example.com")

        self.assertEqual(driver.dashboard_clicks, 3)
        self.assertEqual(driver.update_clicks, 3)

    def test_prioritizes_core_then_themes_then_plugins(self):
        class FakeWordPressManager(WordPressManager):
            def __init__(self):
                self.config = SimpleNamespace(update_wait_min=0, update_wait_max=0)
                self.submitted = []
                self.waited_for = []
                self.states = [
                    UpdateState(
                        has_core_update=True,
                        theme_names=["Theme A"],
                        plugin_names=["Plugin A"],
                    ),
                    UpdateState(theme_names=["Theme A"], plugin_names=["Plugin A"]),
                    UpdateState(plugin_names=["Plugin A"]),
                    UpdateState(),
                    UpdateState(),
                    UpdateState(),
                ]

            def open_admin_page(self, _page):
                return None

            def read_update_state(self):
                return self.states.pop(0)

            def _submit_update(self, kind):
                self.submitted.append(kind)

            def _wait_after_update(self, kind):
                self.waited_for.append(kind)

            def _has_translation_update(self):
                return False

            def _updates_badge_count(self):
                return 0

            def sleeper(self, _seconds):
                return None

        manager = FakeWordPressManager()

        outcome = manager.update_site("example.com")

        self.assertEqual(manager.submitted, ["core", "themes", "plugins"])
        self.assertEqual(manager.waited_for, ["core", "themes", "plugins"])
        self.assertTrue(outcome.core_updated)
        self.assertEqual(outcome.theme_names, ["Theme A"])
        self.assertEqual(outcome.plugin_names, ["Plugin A"])

    def test_waits_one_and_half_seconds_between_final_updates_refreshes(self):
        class FakeWordPressManager(WordPressManager):
            def __init__(self):
                self.config = SimpleNamespace(update_wait_min=0, update_wait_max=0)
                self.states = [UpdateState(), UpdateState(), UpdateState()]
                self.sleeps = []

            def open_admin_page(self, _page):
                return None

            def read_update_state(self):
                return self.states.pop(0)

            def _has_translation_update(self):
                return False

            def _updates_badge_count(self):
                return 0

            def sleeper(self, seconds):
                self.sleeps.append(seconds)

        manager = FakeWordPressManager()

        manager.update_site("example.com")

        self.assertEqual(manager.sleeps, [1.5, 1.5])

    def test_continues_after_plugin_update_when_updates_badge_still_has_number(self):
        class FakeWordPressManager(WordPressManager):
            def __init__(self):
                self.config = SimpleNamespace(update_wait_min=0, update_wait_max=0)
                self.opened_pages = []
                self.submitted = []
                self.states = [
                    UpdateState(plugin_names=["Plugin A"]),
                    UpdateState(),
                    UpdateState(theme_names=["Theme A"]),
                    UpdateState(),
                    UpdateState(),
                    UpdateState(),
                ]
                self.badges = [1, 0, 0, 0]

            def open_admin_page(self, page):
                self.opened_pages.append(page)

            def read_update_state(self):
                return self.states.pop(0)

            def _submit_update(self, kind):
                self.submitted.append(kind)

            def _wait_after_update(self, *_args):
                return None

            def _updates_badge_count(self):
                return self.badges.pop(0)

            def _has_translation_update(self):
                return False

            def sleeper(self, _seconds):
                return None

        manager = FakeWordPressManager()

        outcome = manager.update_site("example.com")

        self.assertEqual(manager.submitted, ["plugins", "themes"])
        self.assertEqual(outcome.plugin_names, ["Plugin A"])
        self.assertEqual(outcome.theme_names, ["Theme A"])
        self.assertEqual(manager.opened_pages, ["update-core.php"] * 6)

    def test_requires_multiple_clear_update_checks_before_leaving_updates_module(self):
        class FakeWordPressManager(WordPressManager):
            def __init__(self):
                self.config = SimpleNamespace(update_wait_min=0, update_wait_max=0)
                self.opened_pages = []
                self.submitted = []
                self.states = [
                    UpdateState(),
                    UpdateState(theme_names=["Delayed Theme"]),
                    UpdateState(),
                    UpdateState(),
                    UpdateState(),
                ]
                self.badges = [0, 0, 0, 0]

            def open_admin_page(self, page):
                self.opened_pages.append(page)

            def read_update_state(self):
                return self.states.pop(0)

            def _submit_update(self, kind):
                self.submitted.append(kind)

            def _wait_after_update(self, *_args):
                return None

            def _updates_badge_count(self):
                return self.badges.pop(0)

            def _has_translation_update(self):
                return False

            def sleeper(self, _seconds):
                return None

        manager = FakeWordPressManager()

        outcome = manager.update_site("example.com")

        self.assertEqual(manager.submitted, ["themes"])
        self.assertEqual(outcome.theme_names, ["Delayed Theme"])
        self.assertEqual(manager.opened_pages, ["update-core.php"] * 5)

    def test_submits_translation_update_before_treating_updates_badge_as_pending(self):
        class FakeWordPressManager(WordPressManager):
            def __init__(self):
                self.config = SimpleNamespace(update_wait_min=0, update_wait_max=0)
                self.submitted = []
                self.states = [UpdateState(), UpdateState(), UpdateState(), UpdateState()]
                self.translation_updates = [True, False, False, False]

            def open_admin_page(self, _page):
                return None

            def read_update_state(self):
                return self.states.pop(0)

            def _has_translation_update(self):
                return self.translation_updates.pop(0)

            def _submit_update(self, kind):
                self.submitted.append(kind)

            def _wait_after_update(self, *_args):
                return None

            def _updates_badge_count(self):
                return 0

            def sleeper(self, _seconds):
                return None

        manager = FakeWordPressManager()

        manager.update_site("example.com")

        self.assertEqual(manager.submitted, ["translations"])


if __name__ == "__main__":
    unittest.main()
