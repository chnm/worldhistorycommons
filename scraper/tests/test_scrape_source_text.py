import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrape_source_text import (  # noqa: E402
    SourceSection,
    get_annotation,
    get_credits,
    get_source_citation,
    get_source_sections,
    merge_annotation,
    merge_front_matter_field,
    merge_source_sections,
    protect_source_text_markdown,
)
from bs4 import BeautifulSoup  # noqa: E402


DRUPAL_SECTIONS = """
<div class="content-details">
  <details>
    <summary><h3>Text</h3></summary>
    <div class="well--data"><p>Original language.</p></div>
  </details>
  <details>
    <summary><h3>Translation</h3></summary>
    <div class="well--data"><p>English translation.</p></div>
  </details>
  <details>
    <summary><h3>Credits</h3></summary>
    <div class="well--data"><p>Translator credit.</p></div>
  </details>
</div>
"""


class SourceSectionExtractionTests(unittest.TestCase):
    def test_extracts_distinct_sections_in_drupal_order(self):
        sections = get_source_sections(
            BeautifulSoup(DRUPAL_SECTIONS, "html.parser")
        )
        self.assertEqual(
            sections,
            [
                SourceSection("Text", "Original language."),
                SourceSection("Translation", "English translation."),
            ],
        )

    def test_preserves_whitespace_only_inline_markup(self):
        soup = BeautifulSoup(
            """
            <div class="box-border">
              <h2 class="box-border--title">Annotation</h2>
              <div><p><i>Young Girls</i> (1932)<i> </i>were created.</p></div>
            </div>
            """,
            "html.parser",
        )
        self.assertEqual(
            get_annotation(soup),
            "*Young Girls* (1932) were created.",
        )

    def test_protects_literal_source_notation_from_markdown_parsing(self):
        source = "1) First  \n6. Sixth\n``quoted''\n--------------------"
        self.assertEqual(
            protect_source_text_markdown(source),
            r"1\) First<br>" "\n"
            r"6\. Sixth" "\n"
            r"\`\`quoted''" "\n"
            r"\--------------------",
        )

    def test_extracts_source_citation_and_credits(self):
        soup = BeautifulSoup(
            """
            <div class="content-meta"><p>A <em>citation</em>.</p></div>
            <div class="content-details"><details>
              <summary><h3>Credits</h3></summary>
              <div class="well--data"><p>A <a href="/credit">credit</a>.</p></div>
            </details></div>
            """,
            "html.parser",
        )
        self.assertEqual(get_source_citation(soup), "A *citation*.")
        self.assertEqual(get_credits(soup), "A [credit](/credit).")


class SourceSectionMergeTests(unittest.TestCase):
    def test_appends_missing_translation_without_conflating_text(self):
        original = "---\ntitle: Example\n---\n\nAnnotation.\n\n## Text\n\nOriginal.\n"
        sections = [
            SourceSection("Text", "Original."),
            SourceSection("Translation", "Translated."),
        ]
        updated = merge_source_sections(original, sections)
        self.assertIn("## Text\n\nOriginal.", updated)
        self.assertIn("## Translation\n\nTranslated.", updated)
        self.assertEqual(updated.count("## Text"), 1)
        self.assertEqual(updated.count("## Translation"), 1)

    def test_replaces_existing_section_content(self):
        original = (
            "---\ntitle: Example\n---\n\nAnnotation.\n\n"
            "## Transcription\n\nOld transcription.\n"
        )
        updated = merge_source_sections(
            original,
            [SourceSection("Transcription", "Drupal transcription.")],
        )
        self.assertNotIn("Old transcription.", updated)
        self.assertIn("## Transcription\n\nDrupal transcription.", updated)

    def test_merge_is_idempotent(self):
        original = "---\ntitle: Example\n---\n\nAnnotation.\n"
        sections = [
            SourceSection("Transcription", "Transcribed."),
            SourceSection("Translation", "Translated."),
        ]
        once = merge_source_sections(original, sections)
        twice = merge_source_sections(once, sections)
        self.assertEqual(once, twice)

    def test_preserves_unrelated_and_local_only_sections(self):
        original = (
            "---\ntitle: Example\n---\n\nAnnotation.\n\n"
            "## Notes\n\nEditorial notes.\n\n"
            "## Translation\n\nLocal translation.\n"
        )
        updated = merge_source_sections(
            original,
            [SourceSection("Text", "Drupal text.")],
        )
        self.assertIn("## Notes\n\nEditorial notes.", updated)
        self.assertIn("## Translation\n\nLocal translation.", updated)
        self.assertIn("## Text\n\nDrupal text.", updated)

    def test_replaces_annotation_without_changing_source_sections(self):
        original = (
            "---\ntitle: Example\n---\n\nOld annotation.\n\n"
            "## Text\n\nOriginal text.\n"
        )
        updated = merge_annotation(original, "Drupal annotation.")
        self.assertNotIn("Old annotation.", updated)
        self.assertIn("Drupal annotation.", updated)
        self.assertIn("## Text\n\nOriginal text.", updated)

    def test_annotation_merge_is_idempotent(self):
        original = "---\ntitle: Example\n---\n\nOld annotation.\n"
        once = merge_annotation(original, "Drupal annotation.")
        twice = merge_annotation(once, "Drupal annotation.")
        self.assertEqual(once, twice)

    def test_replaces_front_matter_block_field(self):
        original = (
            "---\ntitle: Example\ncredits: |\n"
            "  Old credit.\nsource_citation: Existing.\n---\n\nAnnotation.\n"
        )
        updated = merge_front_matter_field(
            original,
            "credits",
            "First line.\n\nSecond line.",
        )
        self.assertIn(
            "credits: |\n  First line.\n\n  Second line.\n",
            updated,
        )
        self.assertIn("source_citation: Existing.", updated)
        self.assertTrue(updated.endswith("\n\nAnnotation.\n"))


if __name__ == "__main__":
    unittest.main()
