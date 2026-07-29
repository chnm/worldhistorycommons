import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_parity import (  # noqa: E402
    Target,
    compare_snapshots,
    discover_csv_targets,
    parse_snapshot,
)


SOURCE_DRUPAL = """
<div class="content-header">
  <div class="content-header--label">Primary Source</div>
  <h1>Example Source</h1>
</div>
<div class="two-cols">
  <div class="image-wrap"><img src="/sites/default/files/source.jpg" alt="Source"></div>
  <div class="box-border">
    <h2 class="box-border--title">Annotation</h2>
    <div><p>An annotation.</p></div>
  </div>
</div>
<div class="content-meta"><p>A citation.</p></div>
<div class="content-details">
  <details><summary><h3>Transcription</h3></summary>
    <div class="well--data"><p>Transcribed text.</p></div>
  </details>
  <details><summary><h3>Translation</h3></summary>
    <div class="well--data"><p>Translated text.</p></div>
  </details>
</div>
<div class="tags">
  <a href="/region/europe">Europe</a>
  <a href="/subject/politics">Politics</a>
</div>
"""

SOURCE_HUGO_MISSING_TRANSLATION = """
<div class="content-header">
  <div class="content-header--label">Primary Source</div>
  <h1>Example Source</h1>
</div>
<div class="two-cols">
  <div class="image-wrap"><img src="/images/source.jpg" alt="Example Source"></div>
  <div class="box-border">
    <h2 class="box-border--title">Annotation</h2>
    <div><p>An annotation.</p></div>
  </div>
</div>
<div class="content-meta"><p>A citation.</p></div>
<div class="content-details">
  <details><summary><h3>Transcription</h3></summary>
    <div class="well--data"><p>Transcribed text.</p></div>
  </details>
</div>
<div class="tags">
  <a href="/regions/europe/">Europe</a>
  <a href="/subjects/politics/">Politics</a>
</div>
"""

TEACHING_HTML = """
<div class="content-header">
  <div class="content-header--label">Teaching</div>
  <h1>Example Teaching Module</h1>
  <div class="content-header--author"><div>Example Author</div></div>
</div>
<div class="two-cols">
  <div class="box-tile">
    <a href="/source-one"><img src="/source-one.jpg" alt="Source one"></a>
  </div>
  <div class="box-border">
    <h2 class="box-border--title">Overview</h2>
    <div><p>Module overview.</p></div>
  </div>
</div>
<div class="content-details">
  <details><summary><h3>Essay</h3></summary>
    <div class="well--data"><p>Module essay.</p></div>
  </details>
</div>
"""

METHODS_HTML = TEACHING_HTML.replace(
    "Teaching", "Methods"
).replace(
    "Teaching Module", "Methods Module"
)

REVIEW_DRUPAL = """
<a href="https://example.org/resource" class="content-header review-header">
  <div class="content-header--label">Website Review</div>
  <h1>Example Review</h1>
  <div class="content-header--author"><div>Site Author</div></div>
</a>
<div class="review-well"><p>Review body.</p></div>
<div class="citation"><div class="credit">
  <div class="text">Reviewed by Reviewer</div>
  <div class="link"><strong>Url:</strong>
    <a href="https://example.org/resource">https://example.org/resource</a>
  </div>
</div></div>
<div class="pull-quote--sidebar"><div class="quote">A quote.</div></div>
"""

REVIEW_HUGO_EMPTY_URL = REVIEW_DRUPAL.replace(
    'href="https://example.org/resource"', 'href=""'
)


class SnapshotTests(unittest.TestCase):
    def test_source_reports_missing_translation(self):
        drupal = parse_snapshot(SOURCE_DRUPAL, "/example", "source")
        hugo = parse_snapshot(
            SOURCE_HUGO_MISSING_TRANSLATION,
            "/example",
            "source",
        )
        findings = compare_snapshots(
            drupal,
            hugo,
            Target("/example", "source", "text"),
        )

        missing = [
            finding
            for finding in findings
            if finding.classification == "migration_loss"
        ]
        self.assertTrue(
            any(
                finding.field == "section_names"
                and "Translation" in finding.drupal
                for finding in missing
            )
        )

    def test_identical_teaching_pages_have_no_findings(self):
        drupal = parse_snapshot(TEACHING_HTML, "/teaching", "teaching")
        hugo = parse_snapshot(TEACHING_HTML, "/teaching", "teaching")
        self.assertEqual(
            compare_snapshots(
                drupal,
                hugo,
                Target("/teaching", "teaching"),
            ),
            [],
        )

    def test_identical_methods_pages_have_no_findings(self):
        drupal = parse_snapshot(METHODS_HTML, "/methods", "methods")
        hugo = parse_snapshot(METHODS_HTML, "/methods", "methods")
        self.assertEqual(
            compare_snapshots(
                drupal,
                hugo,
                Target("/methods", "methods"),
            ),
            [],
        )

    def test_typographic_punctuation_is_semantically_equivalent(self):
        drupal = parse_snapshot(
            SOURCE_DRUPAL.replace(
                "An annotation.",
                "\"An annotation\" - it's concise...",
            ),
            "/example",
            "source",
        )
        hugo = parse_snapshot(
            SOURCE_DRUPAL.replace(
                "An annotation.",
                "\u201cAn annotation\u201d \u2014 it\u2019s concise\u2026",
            ),
            "/example",
            "source",
        )
        self.assertEqual(
            compare_snapshots(
                drupal,
                hugo,
                Target("/example", "source"),
            ),
            [],
        )

    def test_inline_markup_preserves_adjacent_punctuation(self):
        drupal = parse_snapshot(
            SOURCE_DRUPAL.replace(
                "<p>A citation.</p>",
                "<p>Statistics (http://example.org), 1998.</p>",
            ),
            "/example",
            "source",
        )
        hugo = parse_snapshot(
            SOURCE_DRUPAL.replace(
                "<p>A citation.</p>",
                '<p>Statistics (<a href="http://example.org">http://example.org</a>), 1998.</p>',
            ),
            "/example",
            "source",
        )
        self.assertEqual(
            compare_snapshots(
                drupal,
                hugo,
                Target("/example", "source"),
            ),
            [],
        )

    def test_generated_ordered_list_markers_match_literal_numbered_lines(self):
        drupal = SOURCE_DRUPAL.replace(
            "<p>Transcribed text.</p>",
            "<p>1. First item.<br>2. Second item.</p>",
        )
        hugo = SOURCE_DRUPAL.replace(
            "<p>Transcribed text.</p>",
            "<ol><li>First item.</li><li>Second item.</li></ol>",
        )
        self.assertEqual(
            compare_snapshots(
                parse_snapshot(drupal, "/example", "source"),
                parse_snapshot(hugo, "/example", "source"),
                Target("/example", "source"),
            ),
            [],
        )

    def test_review_reports_missing_target_url(self):
        drupal = parse_snapshot(REVIEW_DRUPAL, "/review", "review")
        hugo = parse_snapshot(REVIEW_HUGO_EMPTY_URL, "/review", "review")
        findings = compare_snapshots(
            drupal,
            hugo,
            Target("/review", "review"),
        )
        self.assertTrue(
            any(
                finding.classification == "migration_loss"
                and finding.field == "reviewed_url"
                for finding in findings
            )
        )

    def test_cited_youtube_link_is_not_treated_as_an_embed(self):
        html = SOURCE_DRUPAL.replace(
            "An annotation.",
            'An annotation. <a href="https://www.youtube.com/watch?v=reference">Reference</a>',
        )
        snapshot = parse_snapshot(html, "/example", "source")
        self.assertEqual(snapshot.youtube_ids, [])

    def test_source_reports_changed_image_alt_text(self):
        hugo_html = SOURCE_DRUPAL.replace('alt="Source"', 'alt="Example Source"')
        drupal = parse_snapshot(SOURCE_DRUPAL, "/example", "source")
        hugo = parse_snapshot(hugo_html, "/example", "source")
        findings = compare_snapshots(
            drupal,
            hugo,
            Target("/example", "source", "image"),
        )
        self.assertTrue(
            any(
                finding.classification == "migration_loss"
                and finding.field == "main_image_alt"
                and finding.drupal == ["Source"]
                for finding in findings
            )
        )

    def test_empty_drupal_source_section_is_an_upstream_gap(self):
        drupal_html = SOURCE_DRUPAL.replace(
            "<p>Translated text.</p>",
            "",
        )
        hugo_html = SOURCE_HUGO_MISSING_TRANSLATION
        findings = compare_snapshots(
            parse_snapshot(drupal_html, "/example", "source"),
            parse_snapshot(hugo_html, "/example", "source"),
            Target("/example", "source", "text"),
        )
        self.assertFalse(
            any(
                finding.classification == "migration_loss"
                and finding.field == "section_names"
                and "Translation" in finding.drupal
                for finding in findings
            )
        )
        self.assertTrue(
            any(
                finding.classification == "upstream_gap"
                and finding.field == "empty_source_sections"
                and finding.drupal == ["Translation"]
                for finding in findings
            )
        )

    def test_empty_drupal_audio_link_is_an_upstream_gap(self):
        drupal_html = SOURCE_DRUPAL.replace(
            '<div class="image-wrap"><img src="/sites/default/files/source.jpg" alt="Source"></div>',
            '<div class="audio-wrap"><a href="">Download Audio</a></div>',
        )
        hugo_html = SOURCE_HUGO_MISSING_TRANSLATION.replace(
            '<div class="image-wrap"><img src="/images/source.jpg" alt="Example Source"></div>',
            '<div class="source-media-unavailable">Audio unavailable</div>',
        )
        findings = compare_snapshots(
            parse_snapshot(drupal_html, "/example", "source"),
            parse_snapshot(hugo_html, "/example", "source"),
            Target("/example", "source", "audio"),
        )
        self.assertFalse(
            any(
                finding.classification == "migration_loss"
                and finding.field == "audio_links"
                for finding in findings
            )
        )
        self.assertTrue(
            any(
                finding.classification == "upstream_gap"
                and finding.field == "media"
                for finding in findings
            )
        )

    def test_validated_video_replacement_is_not_a_migration_loss(self):
        drupal_html = SOURCE_DRUPAL.replace(
            '<div class="image-wrap"><img src="/sites/default/files/source.jpg" alt="Source"></div>',
            '<iframe src="https://www.youtube.com/embed/old-id"></iframe>',
        )
        hugo_html = SOURCE_HUGO_MISSING_TRANSLATION.replace(
            '<div class="image-wrap"><img src="/images/source.jpg" alt="Example Source"></div>',
            '<div data-replaces-youtube-id="old-id">'
            '<iframe src="https://www.youtube.com/embed/new-id"></iframe></div>',
        )
        findings = compare_snapshots(
            parse_snapshot(drupal_html, "/example", "source"),
            parse_snapshot(hugo_html, "/example", "source"),
            Target("/example", "source", "video"),
        )
        self.assertFalse(
            any(
                finding.classification == "migration_loss"
                and finding.field == "youtube_ids"
                for finding in findings
            )
        )
        self.assertTrue(
            any(
                finding.classification == "editorial_improvement"
                and finding.field == "youtube_ids"
                for finding in findings
            )
        )


class CsvDiscoveryTests(unittest.TestCase):
    def test_csv_dev_urls_resolve_to_local_content_metadata(self):
        root = Path(self.id().replace(".", "-"))
        content = root / "content"
        sources = content / "sources"
        sources.mkdir(parents=True)
        (sources / "example.md").write_text(
            "---\n"
            "title: Example\n"
            "url: /example\n"
            'source_type: "Text"\n'
            "---\n",
            encoding="utf-8",
        )
        csv_path = root / "review.csv"
        csv_path.write_text(
            "Content Category Name,URL,Status,Notes\n"
            "Sources,https://whc.dev.example/example/,Needs Work,Missing text\n",
            encoding="utf-8",
        )
        try:
            targets = discover_csv_targets(csv_path, content)
            self.assertEqual(
                targets,
                [Target("/example", "source", "text", "Missing text")],
            )
        finally:
            for path in sorted(root.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                else:
                    path.rmdir()
            root.rmdir()


if __name__ == "__main__":
    unittest.main()
