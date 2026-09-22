import unittest
from types import SimpleNamespace

from core.maintenance_pipeline_patch import apply_safe_pipeline_close_patch
from core.maintenance_pipeline import SiteMaintenancePipeline
from core.models import Site


class MaintenancePipelineCloseTests(unittest.TestCase):
    def test_pipeline_supplies_callable_sleeper_when_service_passes_none(self):
        apply_safe_pipeline_close_patch()

        class FakeHostinger:
            driver = object()

            def open_wordpress_admin(self, site):
                return "site-tab"

        class FakeBrowser:
            def __init__(self):
                self.automation_handles = set()

            def close_tab(self, handle):
                self.automation_handles.discard(handle)

        class StepUsingSleeper:
            def run(self, context, result):
                context.sleeper(0)
                result.comments_deleted = 1

        pipeline = SiteMaintenancePipeline(
            FakeHostinger(),
            FakeBrowser(),
            SimpleNamespace(),
            steps=[StepUsingSleeper()],
            sleeper=None,
        )

        result = pipeline.run(Site(domain="example.com", wp_admin_url=""))

        self.assertTrue(result.success)
        self.assertEqual(result.comments_deleted, 1)

    def test_close_tab_none_callable_error_does_not_turn_successful_site_into_failure(self):
        apply_safe_pipeline_close_patch()

        class FakeHostinger:
            driver = object()

            def open_wordpress_admin(self, site):
                return "site-tab"

        class FakeBrowser:
            def __init__(self):
                self.automation_handles = set()

            def close_tab(self, handle):
                self.automation_handles.discard(handle)
                raise TypeError("'NoneType' object is not callable")

        class SuccessfulStep:
            def run(self, context, result):
                result.comments_deleted = 2

        browser = FakeBrowser()
        pipeline = SiteMaintenancePipeline(
            FakeHostinger(),
            browser,
            SimpleNamespace(),
            steps=[SuccessfulStep()],
            sleeper=lambda _seconds: None,
        )

        result = pipeline.run(Site(domain="example.com", wp_admin_url=""))

        self.assertTrue(result.success)
        self.assertEqual(result.comments_deleted, 2)
        self.assertEqual(browser.automation_handles, set())


if __name__ == "__main__":
    unittest.main()
