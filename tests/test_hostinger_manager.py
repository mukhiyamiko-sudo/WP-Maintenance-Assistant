import unittest
from types import SimpleNamespace

from core.hostinger_manager import HostingerManager, extract_sites_from_discovery
from core.models import Site


class HostingerDiscoveryTests(unittest.TestCase):
    def test_rejects_unrelated_domain_from_scan_results(self):
        payload = {
            "rows": [
                {
                    "domain": "site-zero.example",
                    "controls": [{"label": "WP Admin", "href": "/websites/site-zero.example/wp-admin"}],
                },
                {
                    "domain": "nexos.ai",
                    "controls": [],
                },
            ]
        }

        sites = extract_sites_from_discovery(payload)

        self.assertEqual([site.domain for site in sites], ["site-zero.example"])

    def test_does_not_save_ambiguous_hostinger_href_for_wrong_site(self):
        payload = {
            "rows": [
                {
                    "domain": "site-one.example",
                    "controls": [{"label": "WP Admin", "href": "/websites/first-row-admin"}],
                }
            ]
        }

        sites = extract_sites_from_discovery(payload)

        self.assertEqual(len(sites), 1)
        self.assertEqual(sites[0].domain, "site-one.example")
        self.assertEqual(sites[0].wp_admin_url, "")

    def test_keeps_domain_specific_admin_href(self):
        payload = {
            "rows": [
                {
                    "domain": "site-one.example",
                    "controls": [{"label": "WP Admin", "href": "/websites/site-one.example/wp-admin"}],
                }
            ]
        }

        sites = extract_sites_from_discovery(payload)

        self.assertEqual(sites[0].wp_admin_url, "https://hpanel.hostinger.com/websites/site-one.example/wp-admin")

    def test_open_wordpress_admin_switches_back_to_hostinger_list_before_locating_site(self):
        class FakeSwitchTo:
            def __init__(self, driver):
                self.driver = driver

            def window(self, handle):
                self.driver.current_handle = handle

        class FakeDriver:
            def __init__(self):
                self.current_handle = "wp"
                self.handles = ["hostinger", "wp"]
                self.urls = {
                    "hostinger": "https://hpanel.hostinger.com/websites",
                "wp": "https://site-one.example/wp-admin/edit-comments.php",
                }
                self.switch_to = FakeSwitchTo(self)
                self.located_from_handles = []

            @property
            def window_handles(self):
                return list(self.handles)

            @property
            def current_url(self):
                return self.urls[self.current_handle]

            def execute_script(self, script, *args):
                if "WP_AUTOMATION_OPEN_ADMIN" in script:
                    self.located_from_handles.append(self.current_handle)
                    if self.current_handle != "hostinger":
                        return {"opened": False, "reason": "domain row not found"}
                    return {"opened": True, "href": "https://site-two.example/wp-admin/"}
                if "window.open" in script:
                    self.handles.append("new-wp")
                    self.urls["new-wp"] = args[0]
                return None

        driver = FakeDriver()
        manager = HostingerManager(
            driver,
            config=SimpleNamespace(retry_load_timeout=1),
            sleeper=lambda _seconds: None,
        )

        handle = manager.open_wordpress_admin(Site(domain="site-two.example", wp_admin_url=""))

        self.assertEqual(driver.located_from_handles, ["hostinger"])
        self.assertEqual(driver.current_handle, "new-wp")
        self.assertEqual(handle, "new-wp")


if __name__ == "__main__":
    unittest.main()
