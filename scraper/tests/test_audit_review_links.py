import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from audit_review_links import (
    LinkResult,
    classify_response,
    extract_link_references,
    write_report,
)


class ReviewLinkAuditTests(unittest.TestCase):
    def test_extracts_reviewed_url_and_body_links(self):
        markdown = """---
title: "Example"
reviewed_url: "https://example.org/"
---

[Deep link](https://example.org/deep)
[Query link](https://example.org/search?page=1&section=about&amp;mode=all)
[Parentheses](https://example.org/results-(archives)/?term=treaty)
![Image](https://example.org/image.jpg)
<a href="https://example.net/page">Raw link</a>
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            content_dir = Path(temp_dir)
            (content_dir / "example.md").write_text(markdown)
            references = extract_link_references(content_dir)

        self.assertEqual(
            {(ref.context, ref.url) for ref in references},
            {
                ("reviewed_url", "https://example.org/"),
                ("body", "https://example.org/deep"),
                (
                    "body",
                    "https://example.org/search?page=1&section=about&mode=all",
                ),
                (
                    "body",
                    "https://example.org/results-(archives)/?term=treaty",
                ),
                ("body", "https://example.net/page"),
            },
        )

    def test_classifies_redirect_and_access_responses(self):
        redirected = Mock(status_code=200, history=[Mock()])
        restricted = Mock(status_code=403, history=[])
        dead = Mock(status_code=410, history=[])
        transient = Mock(status_code=503, history=[])

        self.assertEqual(classify_response(redirected), "redirect")
        self.assertEqual(classify_response(restricted), "access_restricted")
        self.assertEqual(classify_response(dead), "dead")
        self.assertEqual(classify_response(transient), "transient_failure")

    def test_report_preserves_each_reference(self):
        markdown = """---
reviewed_url: "https://example.org/"
---
[Example](https://example.org/)
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "example.md").write_text(markdown)
            references = extract_link_references(temp_path)
            output = temp_path / "report.csv"
            write_report(
                output,
                references,
                {
                    "https://example.org/": LinkResult(
                        url="https://example.org/",
                        classification="ok",
                        status_code=200,
                    )
                },
            )
            rows = output.read_text().splitlines()

        self.assertEqual(len(rows), 3)
        self.assertTrue(any(",reviewed_url," in row for row in rows[1:]))
        self.assertTrue(any(",body," in row for row in rows[1:]))


if __name__ == "__main__":
    unittest.main()
