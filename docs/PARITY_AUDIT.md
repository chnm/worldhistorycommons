# Drupal-to-Hugo Semantic Parity Audit

The migration is complete only when every meaningful component rendered by
Drupal is represented by Hugo, or the difference is explicitly classified as
an upstream content gap. A page being merely usable is not sufficient.

`scraper/audit_parity.py` compares the live Drupal page with the corresponding
rendered page in `public/`. It compares semantic components rather than raw
HTML, so harmless differences in template markup do not overwhelm the report.
Unicode-equivalent text and straight/curly quotes, apostrophes, dashes, and
ellipses are normalized before comparison.

## What the audit compares

- page type, title, authors, and taxonomy;
- source annotation, citation, images, video, and audio;
- distinct `Text`, `Transcription`, and `Translation` sections;
- Teaching and Methods overview, sections, and related-source galleries;
- Website Review body, target URL, reviewer, pull quote, and image;
- credits and citation text represented as rendered details.

Generated findings use these classifications:

- `migration_loss`: Drupal contains a component that Hugo does not.
- `rendering_mismatch`: both sites render the component differently, or Hugo
  contains something Drupal does not.
- `upstream_gap`: Drupal itself lacks content expected for the page type.
- `editorial_improvement`: reserved for separately reviewed enhancements that
  go beyond migration parity; the auditor does not infer these automatically.

## Run the audit

Build Hugo before invoking the script:

```bash
hugo
cd scraper
uv run python audit_parity.py --limit 10
```

The `just` recipe performs the Hugo build:

```bash
just parity-audit --limit 10
```

To check the team review CSV:

```bash
just parity-audit-reviewed
```

To target particular pages or sections:

```bash
just parity-audit --url /alma-ata-declaration
just parity-audit --section sources --section reviews
```

Useful controls:

- `--delay 0.5` sets the pause between live-site requests.
- `--limit N` checks only the first `N` selected targets.
- `--resume` reuses successfully checked pages from the existing JSON report.
- `--fail-on-difference` returns a non-zero exit code when migration losses,
  rendering mismatches, or request/build errors are present.
- `--output-json` and `--output-csv` override the generated report paths.

Reports default to `utils/content_parity.json` and
`utils/content_parity.csv`. They are working audit artifacts and are ignored by
Git. Promote confirmed discrepancies into tracked issues or content fixes.

## Interpreting results

The auditor is deliberately conservative. A text mismatch may be typographic,
or it may expose dropped content. Review each finding against the rendered
pages before changing content.

An `upstream_gap` is not migration permission to invent material. Track new
translations, replacement media, and link modernization separately as
editorial improvements after one-to-one migration is established.

## Tests

```bash
just parity-audit-test
```

The tests use local HTML fixtures and never contact the live site.
