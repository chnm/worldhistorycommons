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

## License

Content is licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
