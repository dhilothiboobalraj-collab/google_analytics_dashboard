import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "google_analytics.py"


def load_module():
    spec = importlib.util.spec_from_file_location("google_analytics", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GoogleAnalyticsModuleTests(unittest.TestCase):
    def test_normalize_property_id_strips_prefix(self):
        module = load_module()

        self.assertEqual(module.normalize_property_id("properties/123456789"), "123456789")
        self.assertEqual(module.normalize_property_id("123456789"), "123456789")

    def test_build_request_uses_expected_metrics(self):
        module = load_module()

        request = module.build_report_request("properties/123456789", days=7)

        self.assertEqual(request.property, "properties/123456789")
        self.assertEqual([metric.name for metric in request.metrics], ["activeUsers", "sessions", "screenPageViews", "newUsers"])


if __name__ == "__main__":
    unittest.main()
