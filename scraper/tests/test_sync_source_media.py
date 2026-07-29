import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

import sync_source_media


class SyncSourceMediaTests(unittest.TestCase):
    def test_replace_media_fields_preserves_unrelated_front_matter(self):
        original = """---
title: "Example"
doc_type: source
image: /images/first.jpg
regions:
  - "Africa"
---

Annotation.
"""
        updated = sync_source_media.replace_media_fields(
            original,
            image="/images/first.jpg",
            image_alt="A useful description",
            additional_images=[{"src": "/images/second.jpg", "alt": "Second"}],
            audio_files=[],
        )
        self.assertIn('image_alt: "A useful description"', updated)
        self.assertIn('  - src: "/images/second.jpg"', updated)
        self.assertIn('regions:\n  - "Africa"', updated)
        self.assertTrue(updated.endswith("\nAnnotation.\n"))

    def test_replace_media_fields_is_idempotent(self):
        original = """---
title: "Example"
image: /images/first.jpg
image_alt: "Old"
additional_images:
  - src: "/images/old.jpg"
    alt: "Old"
---
Body
"""
        arguments = {
            "image": "/images/first.jpg",
            "image_alt": "New",
            "additional_images": [{"src": "/images/new.jpg", "alt": "New"}],
            "audio_files": [{"src": "/audio/a.mp3", "label": "Download audio"}],
        }
        once = sync_source_media.replace_media_fields(original, **arguments)
        twice = sync_source_media.replace_media_fields(once, **arguments)
        self.assertEqual(once, twice)
        self.assertNotIn("/images/old.jpg", once)

    def test_does_not_add_an_empty_image_field(self):
        original = """---
title: "Text source"
doc_type: source
regions: []
---
Body
"""
        updated = sync_source_media.replace_media_fields(
            original,
            image="",
            image_alt="",
            additional_images=[],
            audio_files=[],
        )
        self.assertEqual(original, updated)

    def test_adds_upstream_media_gap_without_overwriting_existing_notice(self):
        original = """---
title: "Missing video"
doc_type: source
image:
---
Body
"""
        unavailable = {
            "type": "video",
            "message": "The original site does not provide video media for this source.",
        }
        once = sync_source_media.replace_media_fields(
            original,
            image="",
            image_alt="",
            additional_images=[],
            audio_files=[],
            media_unavailable=unavailable,
        )
        twice = sync_source_media.replace_media_fields(
            once,
            image="",
            image_alt="",
            additional_images=[],
            audio_files=[],
            media_unavailable=unavailable,
        )
        self.assertIn("media_unavailable:\n  type: video", once)
        self.assertEqual(once, twice)

    def test_audio_items_reports_empty_drupal_control(self):
        soup = BeautifulSoup(
            '<div class="audio-wrap"><a href="">Download Audio</a></div>',
            "html.parser",
        )
        items, empty = sync_source_media.audio_items(soup, "1")
        self.assertEqual(items, [])
        self.assertTrue(empty)

    def test_image_items_reuses_existing_primary_image(self):
        soup = BeautifulSoup(
            '<div class="two-cols"><div class="image-wrap">'
            '<img src="/first.jpg" alt="First">'
            "</div></div>",
            "html.parser",
        )
        items = sync_source_media.image_items(soup, "1", "/images/first.jpg")
        self.assertEqual(
            items,
            [{"src": "/images/first.jpg", "alt": "First"}],
        )


if __name__ == "__main__":
    unittest.main()
