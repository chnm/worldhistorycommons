# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Serve Commands

```bash
just build          # Hugo build + Pagefind search index (required combo)
just serve          # Dev server at localhost:1313 (live reload)
just dev            # Build + index + serve
just rebuild        # Fix YAML + build + index
just verify-urls    # Build then compare URLs against live Drupal site
```

Always run `just build` (not bare `hugo`) — Pagefind search index must be rebuilt after Hugo.

Scraper commands (one-time migration tools, run from `scraper/` via `uv run`):
```bash
just scrape         # Full site scrape (~1 hour, ~2500 pages)
just fix-yaml       # Fix YAML front matter escaping issues
```

## Architecture

Static site migrated from Drupal 10 (worldhistorycommons.org). Hugo generates HTML, Pagefind indexes it for search, all interactivity is client-side JS.

### Content Sections & URL Mapping

Hugo section directories don't match the public URLs (preserved from Drupal):

| Hugo directory | Public URL | Listing URL |
|---------------|------------|-------------|
| `content/sources/` | `/{slug}` | `/primary-sources/` |
| `content/teaching/` | `/{slug}` | `/teaching/` |
| `content/methods/` | `/{slug}` | `/method/` (singular) |
| `content/reviews/` | `/{slug}` | `/website-reviews/` |
| `content/pages/` | `/{slug}` | N/A |

Each content file has `url:` in front matter to preserve the original Drupal path. **URL stability is critical** — educators link to these in lesson plans.

### Template Architecture

- `themes/whc/layouts/_default/list.html` — Default listing with filters (region, time period, subject). Hybrid: Hugo-rendered HTML by default, JS takes over when filters are applied.
- `themes/whc/layouts/sources/list.html` — Sources listing, adds Type filter (Audio/Image/Object/Text/Video).
- `themes/whc/layouts/sources/single.html` — Two-column: image/YouTube (left) + annotation box (right). Splits markdown on `"\n## Text\n"` to separate annotation from transcription.
- `themes/whc/layouts/teaching/single.html` and `methods/single.html` — Splits markdown on `"\n## "` into collapsible `<details>` sections. Related source tile grid from YAML `related_sources` field.
- `themes/whc/layouts/reviews/single.html` — Two-column with sidebar (image + pull quote).
- `themes/whc/layouts/_default/home.html` — Randomized gallery from JSON pool, filtered to exclude placeholder images.

### Key Gotchas

- **`type` is reserved in Hugo** — use `doc_type` for content type metadata. Using `type` breaks layout lookup.
- **Template `split` on `"## "` matches `"### "` too** — always split on `"\n## "` to match only h2 headings.
- **`jsonify` produces quoted strings** — use `{{ $data | jsonify | safeJS }}` to embed JSON in script tags. Don't double-wrap.
- **Listing pages embed full JSON** for client-side filtering. The sources page has ~1,960 items inline.
- **Placeholder images** (patterns: `Icons-*`, `View_Document_Image*`, `ViewDocumentImage*`, `Text_Image*`) are filtered out of the homepage gallery but shown in listings.

### Content Model (Front Matter)

**Sources**: `doc_type`, `drupal_node_id`, `source_type` (Audio/Image/Object/Text/Video), `url`, `image`, `youtube_id`, `regions[]`, `subjects[]`, `time_periods[]`, `source_citation`, `credits`, `how_to_cite`

**Teaching/Methods**: `doc_type`, `drupal_node_id`, `url`, `image`, `authors[]`, `regions[]`, `subjects[]`, `time_periods[]`, `related_sources[]` (each: link, image, alt), `how_to_cite`. Body uses `## ` headings for sections (Overview, Essay, Primary Sources, Credits, etc.).

**Reviews**: `doc_type`, `drupal_node_id`, `url`, `image`, `website_authors`, `reviewer`, `reviewed_url`, `pull_quote`, `how_to_cite`, `regions[]`, `subjects[]`, `time_periods[]`

### Sort Order

Listing pages sort by `drupal_node_id` descending (newest first). New content without a node ID sorts to the top by `date`.

## Conventions

- Use `uv` for Python (never pip)
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `content:`
- CSS is in `themes/whc/static/css/whc.css` (minified single file, append new styles at end)
- Colors: `#4f90b8` (blue), `#fdbd06` (gold), `#1b1b1b` (text), `#edf4f7` (light blue)
- Font: DIN / DIN-Bold
- YAML multiline strings: use block scalars (`|`)
- Always quote YAML strings containing special characters
