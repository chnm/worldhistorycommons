import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrape_source_text import (  # noqa: E402
    SourceSection,
    get_source_sections,
    merge_source_sections,
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


if __name__ == "__main__":
    unittest.main()
