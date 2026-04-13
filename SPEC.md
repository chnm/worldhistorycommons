# SPEC.md

> For technical implementation details, architecture, and developer documentation, see [AGENTS.md](./AGENTS.md).

---

## Table of Contents

- [Overview](#overview)
- [Users & Roles](#users--roles)
- [Business Rules](#business-rules)
- [Features](#features)
- [User Flows](#user-flows)
  - [Flow 1: Browsing Primary Sources](#flow-1-browsing-primary-sources)
  - [Flow 2: Using a Teaching Module](#flow-2-using-a-teaching-module)
  - [Flow 3: Searching for Content](#flow-3-searching-for-content)
- [Out of Scope](#out-of-scope)
- [Open Questions](#open-questions)

---

## Overview

World History Commons (WHC) is a free, open-access digital resource for exploring global history. It provides curated primary source documents, teaching modules, methodological guides, and website reviews for educators, students, and history enthusiasts worldwide.

**Core value proposition:** A single, reliable destination for world history primary sources with scholarly annotations, teaching context, and pedagogical tools — all freely available under CC BY-NC 4.0.

**Target audience:**
- K-12 and college educators teaching world history
- Students researching world history topics
- General public interested in global historical perspectives

**Primary goals:**
- Preserve and provide access to ~2,500 annotated primary sources spanning all world regions and time periods
- Support educators with teaching modules that contextualize sources
- Offer methodological guides for analyzing different types of primary sources
- Maintain stable URLs so educators' lesson plans and syllabi don't break

**Success metrics:**
- All existing Drupal URLs continue to resolve (zero link breakage)
- Site loads faster than the Drupal version
- Content remains discoverable via search engines
- Educators can filter and find relevant sources by region, time period, subject, and type

**Organizational context:** Maintained by the Roy Rosenzweig Center for History and New Media (RRCHNM) at George Mason University, in partnership with the World History Association. Funded by the National Endowment for the Humanities (NEH) and the American Council of Learned Societies (ACLS).

---

## Users & Roles

This is a public, read-only website. There are no authenticated users or admin roles in the Hugo version. Content is managed via markdown files in the git repository.

### Site Visitor (Public)
- Unauthenticated access to all content
- Can: browse all sections, filter listings, search, read all content pages
- Cannot: create, edit, or delete content
- Typical personas: History teacher preparing a lesson plan, student researching a topic, general reader exploring world history

### Content Editor (Developer/Contributor)
- Edits markdown files in the git repository
- Can: add new content, edit existing content, modify templates and styles
- Workflow: edit files → commit → push → build → deploy
- Typical persona: RRCHNM staff, WHC project team member

---

## Business Rules

### Content Organization

- Content is organized into four sections: **Sources** (primary source documents), **Teaching** (teaching modules), **Methods** (methodological approaches), and **Reviews** (website reviews), plus standalone **Pages**
- Each content item belongs to exactly one section
- Content can be tagged with multiple **regions**, **subjects**, and **time periods**
- Primary sources have a **type** classification: Audio, Image, Object, Text, or Video

### URL Stability

- All content must preserve its original Drupal URL path
- Section listing URLs must match the original Drupal paths:
  - Sources: `/primary-sources/`
  - Teaching: `/teaching/`
  - Methods: `/method/` (singular, matching Drupal)
  - Reviews: `/website-reviews/`
- New content should use URL-friendly slugs consistent with existing conventions

### Taxonomy

- **Regions:** Africa, Asia, Europe, Middle East, North/Central America, Oceania, South America, Southeast Asia, etc.
- **Subjects:** Archaeology, Children, Culture, Government, Imperial/Colonial, Religion, Trade, War, etc.
- **Time Periods:** Ancient (before 500 CE), Medieval (500 CE - 1450 CE), Early Modern (1450 CE - 1800 CE), Modern (1800 CE - 1950 CE), Contemporary (1950 CE - present)
- **Source Types (Sources only):** Audio, Image, Object, Text, Video

### Listing Sort Order

- Legacy content (migrated from Drupal): sorted by Drupal node ID descending (newest first)
- New content (no Drupal node ID): sorted to the top by date descending
- New content always appears before legacy content

### Citations

- Every content page includes a "How to Cite" block
- The access date in citations is generated dynamically (today's date via JavaScript)
- Citation format: `"Title," in World History Commons, [URL] [accessed Month Day, Year]`

### Licensing

- All content is licensed under CC BY-NC 4.0

---

## Features

### Feature: Browse Primary Sources

**Description:**
Paginated listing of ~1,960 primary source documents with filtering by region, time period, subject, and source type.

**User Value:**
Educators can quickly find relevant primary sources for their curriculum by narrowing down from nearly 2,000 items.

**Functionality:**
- Display 20 items per page with thumbnail, title, and first-sentence excerpt
- Filter by region, time period, subject (shared across all sections), and type (Sources only: Audio, Image, Object, Text, Video)
- Pagination: Hugo-native static pages by default; JS-powered pagination when filters are active
- Apply button executes filter; Reset button returns to unfiltered Hugo-rendered view

**Edge Cases:**
- No filter results: empty list displayed
- Sources without images: thumbnail column rendered but empty
- Placeholder images (Icons-Document, etc.): shown in listings, excluded from homepage gallery

---

### Feature: Primary Source Detail Page

**Description:**
Individual source page with two-column layout: media (image or YouTube video) on left, annotation on right, plus metadata below.

**User Value:**
Provides the annotated primary source with full scholarly context, citation information, and the source text when available.

**Functionality:**
- Two-column layout: image or YouTube embed (left), annotation box (right)
- Source citation block (centered)
- Collapsible "Text" section containing the primary source transcription (when available; ~885 sources have this)
- Collapsible "Credits" section (expanded by default)
- "How to Cite" block with dynamic access date
- Tags: clickable region, subject, and time period tags

---

### Feature: Teaching & Methods Modules

**Description:**
Educational modules that bundle primary sources with essays, discussion questions, and bibliographies.

**User Value:**
Provides ready-to-use teaching resources that contextualize primary sources within broader historical themes.

**Functionality:**
- Header with title and author(s)
- Two-column layout: related source tile grid (left), overview box (right)
- Related source tiles link to individual primary source pages
- Collapsible sections: Essay, Primary Sources (with inline images and annotations), Document Based Question, Discussion Questions, Bibliography, Credits
- "How to Cite" block and taxonomy tags

---

### Feature: Website Reviews

**Description:**
Reviews of world history websites and digital resources, with a sidebar layout.

**User Value:**
Helps educators discover quality external websites and evaluate their usefulness.

**Functionality:**
- Bordered header linking to the reviewed website, showing title and site authors
- Review body text (main column)
- Sidebar: screenshot/image of the reviewed site, pull quote
- Reviewer credit with link to reviewed URL
- "How to Cite" block and taxonomy tags

---

### Feature: Homepage Gallery

**Description:**
Randomized mosaic grid of 15 featured content items on the homepage.

**User Value:**
Provides a visually engaging entry point that showcases different content on each visit, encouraging exploration.

**Functionality:**
- Pool of ~1,038 content items with real images (placeholder icons excluded)
- 15 items randomly selected on each page load via JavaScript
- Mosaic CSS grid layout: some tiles span 2x2 for visual variety
- Hover overlay shows title and "Learn More" link
- Responsive: adapts grid to screen size (6 columns → 4 columns on mobile)

---

### Feature: Search

**Description:**
Full-text search powered by Pagefind, accessible from the header search box.

**User Value:**
Quick keyword search across all 2,500+ content pages.

**Functionality:**
- Search input in site header (styled to match original Drupal site)
- Submits to `/search/?q=term` via GET
- Search results page uses Pagefind UI with auto-populated query from URL
- Index rebuilt on each site build (`npx pagefind --site public`)

---

### Feature: Listing Filters

**Description:**
Sidebar filter dropdowns on all four section listing pages.

**User Value:**
Narrow down content by region, time period, subject, and (for sources) media type.

**Functionality:**
- Filter dropdowns auto-populated from actual content taxonomy data
- Hybrid approach: default view is Hugo-rendered static HTML; JS overlays filtered results when a filter is applied
- Apply button: filters content client-side from embedded JSON data
- Reset button: reloads the page to restore Hugo-rendered default view
- Filter state is not persisted in URL (resets on page reload)

---

## User Flows

### Flow 1: Browsing Primary Sources

**Goal:** Find a primary source relevant to a lesson on Early Modern trade in Asia

**Starting Point:** Homepage or direct navigation

**Steps:**
1. User clicks "Sources" in the navigation → lands on `/primary-sources/`
2. Sees paginated listing of ~1,960 sources (20 per page)
3. Selects "Asia" from Region filter
4. Selects "Early Modern (1450 CE - 1800 CE)" from Time Period filter
5. Selects "Trade" from Subject filter
6. Clicks "Apply" → listing filters to matching sources with JS pagination
7. Browses filtered results, clicks a title
8. Lands on source detail page with image/video, annotation, and metadata
9. Reads annotation, expands "Text" section if available
10. Copies citation from "How to Cite" block for lesson plan

**Success Outcome:** User finds and cites a relevant primary source within 2-3 minutes.

**Alternative Paths:**
- User searches via header search box instead of browsing
- User clicks a tag on a source page to find related content
- User clicks "Reset" to clear filters and browse the full listing

---

### Flow 2: Using a Teaching Module

**Goal:** Find a ready-to-use teaching module for a world history class

**Starting Point:** Navigation → "Teaching"

**Steps:**
1. User clicks "Teaching" → lands on `/teaching/`
2. Optionally filters by region/time period/subject
3. Clicks a module title → lands on teaching detail page
4. Reads the Overview in the right column
5. Clicks related source thumbnails in the left column to preview linked sources
6. Expands "Essay" section for background reading
7. Expands "Primary Sources" section to see annotated sources with images
8. Expands "Document Based Question" for classroom discussion prompts
9. Uses linked primary sources in their lesson

**Success Outcome:** Educator has a complete teaching module with background, sources, and discussion questions.

---

### Flow 3: Searching for Content

**Goal:** Find content related to a specific topic (e.g., "Silk Road")

**Starting Point:** Any page on the site

**Steps:**
1. User types "Silk Road" in the header search box
2. Presses Enter → navigated to `/search/?q=Silk+Road`
3. Pagefind displays matching results with excerpts
4. User clicks a result → lands on the content page

**Success Outcome:** User finds relevant content across all sections via keyword search.

---

## Out of Scope

### Explicitly Excluded in Static Migration
- **User accounts / authentication**: No login, no user-generated content. Content is managed via git.
- **Server-side search**: Search is client-side via Pagefind. No Elasticsearch/Solr.
- **Comments or discussions**: Not part of the static site.
- **Content editing UI**: Content is edited as markdown files, not through a web interface.
- **Drupal admin features**: No content moderation, workflows, or CMS features.

### Future Enhancements
- **Advanced search**: Faceted search combining multiple filters with search keywords
- **Persistent filter state**: URL-encoded filter parameters for shareable filtered views
- **Related content suggestions**: "You might also like" based on shared tags
- **RSS feeds**: Per-section or per-taxonomy RSS feeds for subscribers
- **Multilingual support**: The site is English-only currently
- **Print-optimized stylesheets**: For educators printing source documents

### Known Limitations
- **No real-time content updates**: Content changes require a git commit + site rebuild + deploy
- **Filter state resets on navigation**: Navigating away from a filtered listing loses the filter selection
- **Large page payloads on listings**: Source listing embeds ~1,960 items as JSON for client-side filtering (~large HTML file)
- **No offline support**: Fully online, no service worker or PWA features

---

## Open Questions

### Content Questions
- **Q:** Should placeholder images (Icons-Document, etc.) be replaced with a single shared placeholder, removed entirely, or kept as-is?
  - **Context:** ~762 sources have generic document/text placeholder images instead of real photographs
  - **Options:** Single shared icon, remove `image` field, keep current per-item placeholders
  - **Status:** Currently kept as-is; filtered out of homepage gallery only

- **Q:** Are there additional standalone pages on the Drupal site that weren't captured?
  - **Context:** URL verification found 31 missing pages which were subsequently scraped, but the spider-based comparison may have missed orphaned pages
  - **Status:** 31 pages added; may need manual review of Drupal admin page list

### Technical Questions
- **Q:** Where will the site be hosted?
  - **Context:** Static site can go anywhere: Netlify, Vercel, S3+CloudFront, GitHub Pages, institutional server
  - **Options:** Depends on RRCHNM infrastructure preferences and CI/CD needs
  - **Status:** To be determined

- **Q:** Should the build/deploy be automated via CI/CD?
  - **Context:** Currently manual (`just build`). Automated builds on git push would streamline content updates.
  - **Status:** To be determined based on hosting choice

- **Q:** Should the listing page JSON data be moved to a static JSON file loaded asynchronously instead of embedded inline?
  - **Context:** The primary sources listing page has a large inline JSON payload. Loading it asynchronously would improve initial page load.
  - **Options:** Keep inline (simpler), async fetch (better performance), Pagefind-based filtering (removes JSON entirely)
  - **Status:** Open

---

*Last Updated: 2026-04-13*
*This document is maintained for AI agent context and onboarding.*
