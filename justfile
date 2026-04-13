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

# Scrape listing thumbnails for teaching, methods, and reviews
scrape-thumbnails:
    cd scraper && uv run python scrape_thumbnails.py

# Fix YAML front matter escaping issues
fix-yaml:
    cd scraper && uv run python fix_yaml.py
    cd scraper && uv run python fix_yaml2.py

# Verify URLs against the live Drupal site
verify-urls:
    hugo
    cd scraper && uv run python verify_urls.py

# Full rebuild: fix yaml, build, and index
rebuild: fix-yaml build
