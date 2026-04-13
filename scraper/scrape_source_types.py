"""
Scrape the source type (Audio, Image, Object, Text, Video) for each primary source
by using the Drupal type filter on the listing page.

For each type, crawl /primary-sources?field_type_value=<type> and collect all URLs,
then update the corresponding markdown files with a source_type field.

Usage:
    cd scraper && uv run python scrape_source_types.py
"""

import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://worldhistorycommons.org"
CONTENT_DIR = Path(__file__).parent.parent / "content" / "sources"
DELAY = 1

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "WHC-Hugo-Migration/1.0 (RRCHNM; content migration)"
})

# Drupal filter values: param_value -> display label
SOURCE_TYPES = {
    "aud": "Audio",
    "img": "Image",
    "obj": "Object",
    "txt": "Text",
    "vid": "Video",
}


def fetch(url: str) -> BeautifulSoup:
    time.sleep(DELAY)
    print(f"  GET {url}")
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def get_total_pages(soup: BeautifulSoup) -> int:
    last_link = soup.select_one("li.pager__item--last a")
    if last_link:
        href = last_link.get("href", "")
        match = re.search(r"page=(\d+)", href)
        if match:
            return int(match.group(1)) + 1
    return 1


def collect_urls_for_type(source_type: str) -> list[str]:
    """Collect all source URLs for a given type filter."""
    urls = []
    first_url = f"{BASE_URL}/primary-sources?field_type_value={source_type}"
    soup = fetch(first_url)
    total_pages = get_total_pages(soup)
    print(f"  {source_type}: {total_pages} page(s)")

    for page_num in range(total_pages):
        if page_num > 0:
            soup = fetch(f"{first_url}&page={page_num}")

        for row in soup.select("div.vdh > div.views-row"):
            link = row.select_one("h2 a")
            if link and link.get("href"):
                urls.append(link["href"])

    print(f"  {source_type}: {len(urls)} sources found")
    return urls


def update_markdown(url_path: str, source_type: str) -> bool:
    """Add source_type to front matter of the corresponding markdown file."""
    slug = url_path.strip("/").split("/")[-1]
    filepath = CONTENT_DIR / f"{slug}.md"

    if not filepath.exists():
        return False

    content = filepath.read_text()
    parts = content.split("---", 2)
    if len(parts) < 3:
        return False

    fm = parts[1]

    # Skip if already has source_type
    if "source_type:" in fm:
        return False

    # Add source_type after the type: line
    fm = fm.replace("\nurl:", f'\nsource_type: "{source_type}"\nurl:')

    filepath.write_text("---" + fm + "---" + parts[2])
    return True


def main():
    print("Scraping source types from Drupal filters...")

    type_map = {}  # url -> display label

    for param_val, label in SOURCE_TYPES.items():
        print(f"\nCollecting {label} ({param_val}) sources...")
        urls = collect_urls_for_type(param_val)
        for url in urls:
            type_map[url] = label

    print(f"\nTotal sources with types: {len(type_map)}")

    # Update markdown files
    updated = 0
    for url_path, source_type in type_map.items():
        if update_markdown(url_path, source_type):
            updated += 1

    print(f"Updated {updated} markdown files")


if __name__ == "__main__":
    main()
