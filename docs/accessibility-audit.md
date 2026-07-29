# Accessibility Audit

Audit date: July 29, 2026

Target: WCAG 2.2 Level AA

## Scope

The final migration review covered the home page, section listings, Sources,
Teaching, Methods, Website Reviews, standalone pages, citations, taxonomy
links, filters, related-source galleries, images, audio, video, disclosures,
external links, desktop layouts, and mobile reflow.

Representative rendered pages included:

- `/`
- `/primary-sources/`, `/teaching/`, `/method/`, `/website-reviews/`
- `/search/`
- `/4-august-decrees/`
- `/long-teaching-module-caribbean-seafaring-archaic-age-2000-400-bc/`
- `/analyzing-maps/`
- `/abolition-slavery-project/`
- `/about/`
- `/community-college-video-guides/`

## Automated Results

Run the repeatable static audit with:

```bash
just a11y-audit
```

The command builds Hugo without Pagefind and scans every generated HTML file.
It checks document language and titles, main landmarks, page-level headings,
heading order, duplicate IDs, image alternatives, iframe titles, disclosure
summaries, audio controls, form labels, and accessible button/link names.
Machine-readable reports are written to:

- `utils/accessibility_audit.json`
- `utils/accessibility_audit.csv`

The initial whole-build scan reported 753 violations across 559 generated
files, primarily duplicate IDs and skipped heading levels inherited from
rendered summaries and migrated heading markup. After remediation, the clean
whole-build scan reports zero violations. Four automated-audit fixtures are
included in the scraper test suite.

## Manual and Rendered-Page Results

| Area | Result |
| --- | --- |
| Landmarks and headings | One main landmark and one `h1` on every representative page; navigation landmarks are named. |
| Keyboard entry and focus | A first-focus skip link targets the focusable main landmark. Interactive elements receive a high-contrast three-pixel focus indicator. |
| Navigation and disclosures | Main/footer navigation is named; native `details`/`summary` controls retain keyboard semantics and visible focus. |
| Filters | Controls have explicit labels and a named form. Apply/reset use native buttons. Result counts and pages are announced through a polite status region. |
| Filter pagination | Native buttons replace placeholder links; the current page is exposed with `aria-current`; page changes return focus to the results region. |
| Search shell | Header search has a programmatic label and native keyboard submission; the search page has a main heading and landmark. See the Pagefind exception below. |
| Link purpose | Homepage tiles, related-source cards, review targets, taxonomies, citations, and footer links expose meaningful accessible names. External links do not unexpectedly open a new context. |
| Images | Every rendered image has an `alt` attribute. Redundant listing/gallery thumbnails use empty alternatives; review screenshots and primary-source media expose text alternatives. |
| Media | Source audio exposes native controls and download links. Source videos and all 20 community-college guide embeds have titles; guide videos have adjacent transcript links. |
| Contrast | Normal blue link text was darkened to `#2d6f96` (5.49:1 on white). Header navigation uses `#1b1b1b` on `#4f90b8` (4.93:1). Gold labels use dark text (10.22:1). |
| Motion | A `prefers-reduced-motion` rule minimizes animation, transition, and smooth-scrolling duration. |
| Reflow | Home, listings, Sources, Teaching, Reviews, About, and video guides were checked at 320 CSS px; no representative page requires horizontal scrolling. |
| Desktop | Representative templates were checked at the default 1265–1280 CSS px viewport with no unintended horizontal overflow. |

## Remediation Completed

- Added a skip link and focusable main target.
- Added missing home and special-page `h1` elements.
- Corrected review and migrated-content heading hierarchies.
- Prevented taxonomy summaries from duplicating content heading IDs.
- Added consistent visible-focus styles and keyboard-visible homepage tiles.
- Corrected common text, control, and brand-color contrast failures.
- Added accessible filter status announcements and button-based pagination.
- Corrected mobile header, gallery, long-URL, citation, and review reflow.
- Added meaningful titles and lazy loading to 20 YouTube guide embeds.
- Added review screenshot alternatives and corrected decorative thumbnail use.

## Justified Exceptions and Follow-ups

1. [Issue #12](https://github.com/chnm/worldhistorycommons/issues/12)
   tracks editorial review of primary-source image descriptions. The source
   template provides valid title-based fallback text, but 874 of 1,960 source
   records do not yet have a subject-written `image_alt` value. Historical
   descriptions require content expertise and should not be generated
   mechanically.
2. [Issue #13](https://github.com/chnm/worldhistorycommons/issues/13)
   tracks the populated Pagefind interface. Pagefind was explicitly excluded
   from this pass. The search shell was reviewed, but live-result announcements,
   result focus behavior, and populated mobile states must be tested when the
   index returns to the active workflow.
