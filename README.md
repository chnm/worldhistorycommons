# World History Commons

[World History Commons](https://worldhistorycommons.org/) is a free, open-access digital resource for exploring global history. It provides curated primary source documents, teaching modules, methodological guides, and website reviews for educators, students, and history enthusiasts worldwide.

Maintained by the [Roy Rosenzweig Center for History and New Media](https://rrchnm.org/) (RRCHNM) at George Mason University, in partnership with the [World History Association](https://www.thewha.org/). Funded by the National Endowment for the Humanities (NEH) and the American Council of Learned Societies (ACLS).

## Content

- **Primary Sources** (~1,960) — Annotated documents, images, audio, and video spanning all world regions and time periods
- **Teaching Modules** (~149) — Ready-to-use lessons with essays, primary sources, and discussion questions
- **Methods** (~48) — Guides for analyzing different types of primary sources
- **Website Reviews** (~335) — Reviews of world history digital resources

## Tech Stack

- [Hugo](https://gohugo.io/) (static site generator)
- [Pagefind](https://pagefind.app/) (client-side search)
- Plain CSS and vanilla JavaScript

## Getting Started

### Prerequisites

- Hugo v0.128.0+ extended (`brew install hugo`)
- Node.js (for Pagefind via npx)
- [just](https://github.com/casey/just) (`brew install just`) — optional but recommended

### Build & Serve

```bash
just build    # Hugo build + Pagefind search index
just serve    # Dev server at localhost:1313
just dev      # Build + index + serve
```

## Drupal-to-Hugo Parity Audit

The semantic parity auditor compares the four migrated content sections
(primary sources, teaching modules, methods, and website reviews) against the
live Drupal site. It reads rendered Hugo pages from `public/` and does not
modify content.

```bash
# Audit every migrated page (runs Hugo first)
just parity-audit

# Audit only one or more sections
just parity-audit --section sources --section teaching

# Audit specific canonical URLs
just parity-audit --url /suffrage-atelier-postcard-1909/

# Audit the pages in the team review spreadsheet
just parity-audit-reviewed

# Continue an interrupted run using completed pages in the JSON report
just parity-audit --resume

# Return a nonzero exit code for migration/rendering differences or fetch errors
just parity-audit --fail-on-difference
```

Requests are rate-limited to one every 0.5 seconds by default. Use `--delay`
to change the interval and `--timeout` to change the per-page timeout. Reports
are written to `utils/content_parity.json` and `utils/content_parity.csv`;
both include the canonical page URL, field or section, Drupal and Hugo values,
classification, and any note imported from the review CSV.

Interpret classifications as follows:

- `migration_loss`: Drupal content is missing from Hugo.
- `rendering_mismatch`: both pages render, but their semantic content differs.
- `upstream_gap`: the Drupal page itself lacks content or cannot be checked.
- `editorial_improvement`: Hugo intentionally supplies a validated improvement.

Treat migration losses and rendering mismatches as work to resolve. Upstream
gaps and editorial improvements should remain in the report as the explanation
for an intentional difference. Run the network-free fixtures with
`just parity-audit-test`.

## License

Content is licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
