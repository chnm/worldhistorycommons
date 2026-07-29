import sys
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sync_teaching_content import (  # noqa: E402
    ContentSection,
    existing_primary_images,
    format_body,
    get_sections,
    merge_front_matter_field,
    update_markdown,
)
from scrape import protect_nested_section_headings  # noqa: E402


DRUPAL_PAGE = """
<div class="box-border">
  <h2 class="box-border--title">Overview</h2>
  <div><p>Drupal overview.</p></div>
</div>
<div class="content-details">
  <details>
    <summary><h3>Primary Sources</h3></summary>
    <div class="well--data">
      <div class="slideshow-slide">
        <h4 class="slideshow-slide--title">A Source</h4>
        <a class="slideshow-slide--img" href="/a-source">
          <img src="/files/source.jpg" alt="Remote alt">
        </a>
        <h5>Annotation</h5>
        <div class="slideshow-slide--text">
          <p>Source annotation.</p>
          <p><br>Visible after a legacy break.</br></p>
          <template><p>Hidden replacement text.</p></template>
        </div>
      </div>
    </div>
  </details>
  <details>
    <summary><h3>Sample Analysis</h3></summary>
    <div class="well--data">
      <h2>First <em>analysis</em></h2>
      <p>Analysis text.</p>
      <p><a href="#14&gt;hidden replacement">15</a> Visible footnote text.</p>
      <table><tbody><tr><td><p>Layout-table text.</p></td></tr></tbody></table>
      <img src="/files/analysis.jpg" alt="Analysis image">
    </div>
  </details>
</div>
<div class="citation"><span>Teaching citation.</span></div>
"""

LOCAL_MARKDOWN = """---
title: Example
doc_type: methods
url: /example
image: /images/listing.jpg
related_sources:
  - link: /a-source
    image: /images/source.jpg
---

## Overview

Old overview.

## Primary Sources

### [A Source](/a-source)

![Existing alt](/images/source.jpg)

Old annotation.
"""


class TeachingContentTests(unittest.TestCase):
    def test_maps_existing_primary_images_by_source_path(self):
        self.assertEqual(
            existing_primary_images(LOCAL_MARKDOWN),
            {"/a-source": "![Existing alt](/images/source.jpg)"},
        )

    def test_formats_primary_sources_with_annotation_heading(self):
        soup = BeautifulSoup(DRUPAL_PAGE, "html.parser")
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)
            (static_dir / "analysis.jpg").write_bytes(b"image")
            sections = get_sections(
                soup,
                existing_primary_images(LOCAL_MARKDOWN),
                static_dir=static_dir,
                download_missing=False,
            )
        primary = sections[0]
        self.assertEqual(primary.label, "Primary Sources")
        self.assertIn("![Existing alt](/images/source.jpg)", primary.content)
        self.assertIn("#### Annotation\n\nSource annotation.", primary.content)
        self.assertIn("Visible after a legacy break.", primary.content)
        self.assertNotIn("Hidden replacement text", primary.content)

    def test_keeps_nested_headings_and_images_inside_sample_analysis(self):
        soup = BeautifulSoup(DRUPAL_PAGE, "html.parser")
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)
            (static_dir / "analysis.jpg").write_bytes(b"image")
            sections = get_sections(
                soup,
                {},
                static_dir=static_dir,
                download_missing=False,
            )
        sample = sections[1]
        self.assertIn("<h2>First <em>analysis</em></h2>", sample.content)
        self.assertIn("Layout-table text.", sample.content)
        self.assertNotIn("| Layout-table text.", sample.content)
        self.assertIn("15 Visible footnote text.", sample.content)
        self.assertNotIn("hidden replacement", sample.content)
        self.assertIn(
            "![Analysis image](/images/analysis.jpg)",
            sample.content,
        )
        body = format_body("Overview.", sections)
        self.assertEqual(body.count("\n## Sample Analysis\n"), 1)

    def test_adds_missing_front_matter_field(self):
        updated = merge_front_matter_field(
            LOCAL_MARKDOWN, "how_to_cite", "Teaching citation."
        )
        self.assertIn(
            "how_to_cite: |\n  Teaching citation.\n---",
            updated,
        )
        self.assertIn("related_sources:", updated)

    def test_canonical_scraper_preserves_inline_heading_markup(self):
        self.assertEqual(
            protect_nested_section_headings(
                "## Sample *Analysis* with [context](/context)"
            ),
            (
                '<h2>Sample <em>Analysis</em> with '
                '<a href="/context">context</a></h2>'
            ),
        )

    def test_full_update_preserves_front_matter_and_is_idempotent(self):
        soup = BeautifulSoup(DRUPAL_PAGE, "html.parser")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            filepath = root / "example.md"
            static_dir = root / "images"
            static_dir.mkdir()
            (static_dir / "analysis.jpg").write_bytes(b"image")
            filepath.write_text(LOCAL_MARKDOWN, encoding="utf-8")
            self.assertTrue(
                update_markdown(
                    filepath,
                    soup,
                    static_dir=static_dir,
                    download_missing=False,
                )
            )
            once = filepath.read_text(encoding="utf-8")
            self.assertIn("image: /images/listing.jpg", once)
            self.assertIn("related_sources:", once)
            self.assertIn("Drupal overview.", once)
            self.assertIn("how_to_cite: |\n  Teaching citation.", once)
            self.assertFalse(
                update_markdown(
                    filepath,
                    soup,
                    static_dir=static_dir,
                    download_missing=False,
                )
            )
            self.assertEqual(once, filepath.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
