"""
URL verification: crawl the live Drupal site and compare against Hugo's sitemap.

Usage:
    cd /path/to/whc
    hugo  # build first
    uv run python scraper/verify_urls.py

Outputs:
    - drupal_urls.txt: all content URLs found on the live site
    - hugo_urls.txt: all content URLs from the Hugo build
    - missing_in_hugo.txt: URLs on Drupal but not in Hugo
    - extra_in_hugo.txt: URLs in Hugo but not on Drupal
"""

import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://worldhistorycommons.org"
OUTPUT_DIR = Path(__file__).parent.parent
HUGO_PUBLIC = OUTPUT_DIR / "public"
DELAY = 0.5  # faster since we're just crawling, not parsing

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "WHC-Hugo-Migration/1.0 (RRCHNM; URL verification)"
})

# Known non-content paths to skip (Drupal system paths, assets, etc.)
SKIP_PREFIXES = (
    "/sites/",
    "/themes/",
    "/core/",
    "/modules/",
    "/user/",
    "/admin/",
    "/search/",
    "/filter/",
    "/node/",
    "/taxonomy/",
    "/region/",
    "/subject/",
    "/time-period/",
)

SKIP_EXTENSIONS = (
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".ico", ".pdf", ".xml", ".json", ".ttf", ".woff", ".eot",
)


def normalize_path(path: str) -> str:
    """Normalize a URL path for comparison."""
    path = urlparse(path).path
    path = path.rstrip("/")
    if not path:
        path = "/"
    return path


def crawl_drupal() -> set[str]:
    """Spider the live Drupal site and collect all internal content URLs."""
    print("Crawling live Drupal site...")
    visited = set()
    to_visit = {"/"}
    content_urls = set()

    # Also seed with the listing pages to make sure we find everything
    for seed in ["/primary-sources", "/teaching", "/method", "/website-reviews", "/about"]:
        to_visit.add(seed)

    while to_visit:
        path = to_visit.pop()
        normalized = normalize_path(path)

        if normalized in visited:
            continue
        visited.add(normalized)

        # Skip non-content paths
        if any(normalized.startswith(p) for p in SKIP_PREFIXES):
            continue
        if any(normalized.endswith(ext) for ext in SKIP_EXTENSIONS):
            continue

        url = f"{BASE_URL}{normalized}"
        try:
            time.sleep(DELAY)
            resp = SESSION.get(url, timeout=30)
            if resp.status_code == 200:
                content_urls.add(normalized)
                print(f"  [{len(content_urls)} found, {len(to_visit)} queued] {normalized}")

                # Parse for more links
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]

                    # Handle relative URLs
                    if href.startswith("/"):
                        link_path = normalize_path(href)
                    elif href.startswith(BASE_URL):
                        link_path = normalize_path(href.replace(BASE_URL, ""))
                    else:
                        continue  # external link

                    # Skip fragments and query strings for comparison
                    link_path = link_path.split("?")[0].split("#")[0]
                    link_path = normalize_path(link_path)

                    if link_path not in visited:
                        if not any(link_path.startswith(p) for p in SKIP_PREFIXES):
                            if not any(link_path.endswith(ext) for ext in SKIP_EXTENSIONS):
                                to_visit.add(link_path)
            elif resp.status_code == 404:
                pass  # dead link on the site itself
            else:
                print(f"  WARNING: {resp.status_code} for {url}")
        except Exception as e:
            print(f"  ERROR: {url}: {e}")

    print(f"  Crawl complete: {len(content_urls)} URLs found")
    return content_urls


def collect_hugo_urls() -> set[str]:
    """Collect all URLs from Hugo's built public/ directory."""
    print("Collecting Hugo URLs from public/ directory...")

    if not HUGO_PUBLIC.exists():
        print("  ERROR: public/ directory not found. Run 'hugo' first.")
        return set()

    urls = set()
    for index_file in HUGO_PUBLIC.rglob("index.html"):
        # Convert file path to URL path
        rel = index_file.parent.relative_to(HUGO_PUBLIC)
        path = "/" + str(rel)
        if path == "/.":
            path = "/"
        path = normalize_path(path)
        urls.add(path)

    print(f"  Found {len(urls)} Hugo URLs")
    return urls


def map_drupal_to_hugo(drupal_path: str) -> str:
    """Map Drupal URL patterns to Hugo equivalents."""
    # Drupal listing paths map to Hugo section paths
    mapping = {
        "/primary-sources": "/sources",
        "/method": "/methods",
        "/website-reviews": "/reviews",
        "/teaching": "/teaching",
    }

    for drupal_prefix, hugo_prefix in mapping.items():
        if drupal_path == drupal_prefix:
            return hugo_prefix

    return drupal_path


def main():
    # Step 1: Crawl Drupal
    drupal_urls = crawl_drupal()

    # Step 2: Collect Hugo URLs
    hugo_urls = collect_hugo_urls()

    # Step 3: Normalize and map
    # Map Drupal URLs to expected Hugo equivalents
    drupal_mapped = set()
    drupal_mapping = {}  # mapped -> original
    for url in drupal_urls:
        mapped = map_drupal_to_hugo(url)
        drupal_mapped.add(mapped)
        drupal_mapping[mapped] = url

    # Hugo generates taxonomy pages and other extras — filter to content only
    # Remove Hugo-generated taxonomy/pagination pages for fair comparison
    hugo_content = set()
    hugo_extra = set()
    for url in hugo_urls:
        if any(url.startswith(p) for p in ["/regions", "/subjects", "/time_periods",
                                            "/tags", "/categories", "/page"]):
            hugo_extra.add(url)
        else:
            hugo_content.add(url)

    # Step 4: Compare
    missing_in_hugo = drupal_mapped - hugo_content
    extra_in_hugo = hugo_content - drupal_mapped

    # Step 5: Write results
    with open(OUTPUT_DIR / "drupal_urls.txt", "w") as f:
        for url in sorted(drupal_urls):
            f.write(url + "\n")

    with open(OUTPUT_DIR / "hugo_urls.txt", "w") as f:
        for url in sorted(hugo_urls):
            f.write(url + "\n")

    with open(OUTPUT_DIR / "missing_in_hugo.txt", "w") as f:
        for url in sorted(missing_in_hugo):
            original = drupal_mapping.get(url, url)
            f.write(f"{url}  (drupal: {original})\n")

    with open(OUTPUT_DIR / "extra_in_hugo.txt", "w") as f:
        for url in sorted(extra_in_hugo):
            f.write(url + "\n")

    # Step 6: Report
    print(f"\n{'='*60}")
    print("URL Verification Report")
    print(f"{'='*60}")
    print(f"Drupal content URLs:     {len(drupal_urls)}")
    print(f"Hugo content URLs:       {len(hugo_content)}")
    print(f"Hugo taxonomy/extra:     {len(hugo_extra)}")
    print(f"Missing in Hugo:         {len(missing_in_hugo)}")
    print(f"Extra in Hugo:           {len(extra_in_hugo)}")
    print()

    if missing_in_hugo:
        print("MISSING IN HUGO (first 20):")
        for url in sorted(missing_in_hugo)[:20]:
            original = drupal_mapping.get(url, url)
            print(f"  {original}")
        if len(missing_in_hugo) > 20:
            print(f"  ... and {len(missing_in_hugo) - 20} more (see missing_in_hugo.txt)")

    if extra_in_hugo:
        print("\nEXTRA IN HUGO (first 20):")
        for url in sorted(extra_in_hugo)[:20]:
            print(f"  {url}")
        if len(extra_in_hugo) > 20:
            print(f"  ... and {len(extra_in_hugo) - 20} more (see extra_in_hugo.txt)")

    if not missing_in_hugo:
        print("All Drupal content URLs are present in Hugo!")

    print(f"\nFull results written to:")
    print(f"  drupal_urls.txt")
    print(f"  hugo_urls.txt")
    print(f"  missing_in_hugo.txt")
    print(f"  extra_in_hugo.txt")


if __name__ == "__main__":
    main()
