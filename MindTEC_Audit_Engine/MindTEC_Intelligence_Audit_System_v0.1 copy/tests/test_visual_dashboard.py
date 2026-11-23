"""Smoke-test the Streamlit visual shell with synthetic session state only."""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"


class DashboardVisualTests(unittest.TestCase):
    def test_home_and_executive_navigation(self):
        at = AppTest.from_file(str(APP), default_timeout=60).run()
        self.assertEqual(len(at.exception), 0, str(list(at.exception)))
        self.assertGreaterEqual(len(at.sidebar.radio), 1)
        options = list(at.sidebar.radio[0].options)
        self.assertIn("Dashboard ejecutivo", options)
        self.assertIn("Dashboard HTML original", options)
        self.assertGreaterEqual(len(at.metric), 4)
        at.sidebar.radio[0].set_value("Dashboard ejecutivo").run()
        self.assertEqual(len(at.exception), 0, str(list(at.exception)))
        self.assertGreaterEqual(len(at.metric), 4)

    def test_optional_html_view_does_not_require_private_files(self):
        at = AppTest.from_file(str(APP), default_timeout=60).run()
        at.sidebar.radio[0].set_value("Dashboard HTML original").run()
        self.assertEqual(len(at.exception), 0, str(list(at.exception)))


if __name__ == "__main__":
    unittest.main()
