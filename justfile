# Build the Hugo site and index with Pagefind
build:
    hugo
    npx pagefind --site public

# Run the development server
serve:
    hugo server -D

# Build and serve locally
dev:
    hugo
    npx pagefind --site public
    hugo server -D

# Run the full scrape from worldhistorycommons.org (takes ~1 hour)
scrape:
    cd scraper && uv run python scrape.py

# Scrape the standalone pages not in the main content sections
scrape-pages:
    cd scraper && uv run python scrape_pages.py

# Scrape source type metadata (Audio, Image, Text, Video)
scrape-types:
    cd scraper && uv run python scrape_source_types.py

# Preserve Drupal Text, Transcription, and Translation source sections
scrape-source-sections *args:
    cd scraper && uv run python scrape_source_text.py {{args}}

# Scrape listing thumbnails for teaching, methods, and reviews
scrape-thumbnails:
    cd scraper && uv run python scrape_thumbnails.py

# Fix YAML front matter escaping issues
fix-yaml:
    cd scraper && uv run python fix_yaml.py
    cd scraper && uv run python fix_yaml2.py

# --- Legacy-URL redirect pipeline (Drupal /node/{id} -> Hugo slug -> Caddy) ---

# Build the legacy->native map from the Hugo manifest (public/redirects.json)
redirects-build:
    uv run utils/redirect_mapper.py build

# Merge any discovered old URLs (utils/old_urls.csv) + apply the parent-section fallback
redirects-reconcile:
    uv run utils/redirect_mapper.py reconcile

# Generate static/redirects.caddy from the map (Hugo then copies it to public/redirects.caddy)
redirects-generate:
    uv run utils/redirect_mapper.py generate

# Regenerate the whole map + Caddy snippet (requires a prior `just build`)
redirects: redirects-build redirects-reconcile redirects-generate

# Verify redirects against a running target (301 -> native 200, no loops)
redirects-verify target="http://localhost:8080" *args:
    uv run utils/redirect_mapper.py verify --target {{target}} {{args}}

# Cross-check the live Drupal site: /node/{id} should resolve to our recorded slug
redirects-crosscheck old_site="https://worldhistorycommons.org" *args:
    uv run utils/redirect_mapper.py crosscheck --old-site {{old_site}} {{args}}

# Parity: confirm each legacy URL resolves on the live OLD site AND its target on the NEW site
redirects-parity old_site="https://worldhistorycommons.org" target="http://localhost:8080" *args:
    uv run utils/redirect_mapper.py parity --old-site {{old_site}} --target {{target}} {{args}}

# Docker build (Hugo + Pagefind + Caddy serving with redirects)
docker-build tag="worldhistorycommons:latest":
    docker build -t {{tag}} .

# Docker run (serves on port 8080)
docker-run tag="worldhistorycommons:latest":
    docker run -p 8080:80 {{tag}}

# Verify URLs against the live Drupal site
verify-urls:
    hugo
    cd scraper && uv run python verify_urls.py

# Compare rendered Hugo content with the live Drupal site.
parity-audit *args:
    hugo
    cd scraper && uv run python audit_parity.py {{args}}

# Run the semantic parity audit against the team review CSV.
parity-audit-reviewed *args:
    hugo
    cd scraper && uv run python audit_parity.py --input-csv "../WHC Review - Category Review.csv" {{args}}

# Unit tests for the semantic parity and section migration tooling (no network).
parity-audit-test:
    cd scraper && uv run python -m unittest discover -s tests -p 'test_*.py'

# Rate-limited external-link audit for Website Reviews.
review-link-audit *args:
    cd scraper && uv run python audit_review_links.py {{args}}

# Full rebuild: fix yaml, build, and index
rebuild: fix-yaml build
