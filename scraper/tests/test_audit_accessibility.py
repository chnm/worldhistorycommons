import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_accessibility import audit_html  # noqa: E402


ACCESSIBLE_PAGE = """
<!doctype html>
<html lang="en">
<head><title>Example</title></head>
<body>
  <header><nav aria-label="Main"><a href="/">Home</a></nav></header>
  <main id="main"><h1>Example</h1>
    <img src="/decorative.jpg" alt="">
    <label for="query">Search</label><input id="query">
    <details><summary>More</summary><p>Details</p></details>
  </main>
</body>
</html>
"""


class AccessibilityAuditTests(unittest.TestCase):
    def test_accessible_fixture_has_no_violations(self):
        self.assertEqual(audit_html(ACCESSIBLE_PAGE), [])

    def test_reports_missing_names_and_structure(self):
        html = ACCESSIBLE_PAGE.replace("<h1>Example</h1>", "")
        html = html.replace('alt=""', "")
        html = html.replace(">Home</a>", "></a>")
        rules = {violation.rule for violation in audit_html(html)}
        self.assertEqual(rules, {"image-alt", "link-name", "page-h1"})

    def test_reports_heading_jump_and_untitled_iframe(self):
        html = ACCESSIBLE_PAGE.replace(
            "<h1>Example</h1>",
            '<h1>Example</h1><h3>Skipped level</h3><iframe src="/embed"></iframe>',
        )
        rules = {violation.rule for violation in audit_html(html)}
        self.assertEqual(rules, {"heading-order", "iframe-title"})

    def test_redirect_alias_is_ignored(self):
        html = '<html><head><meta http-equiv="refresh" content="0; url=/new/"></head></html>'
        self.assertEqual(audit_html(html), [])


if __name__ == "__main__":
    unittest.main()
