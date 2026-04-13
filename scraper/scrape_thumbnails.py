"""
Scrape listing thumbnails for Teaching, Methods, and Reviews pages.
These thumbnails are only visible on the Drupal listing pages, not on detail pages.

Usage:
    cd scraper && uv run python scrape_thumbnails.py
"""

import re
import time
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://worldhistorycommons.org"
CONTENT_DIR = Path(__file__).parent.parent / "content"
STATIC_DIR = Path(__file__).parent.parent / "static" / "images"
DELAY = 1

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "WHC-Hugo-Migration/1.0 (RRCHNM; content migration)"
})

SECTIONS = [
    ("/teaching", "teaching"),
    ("/method", "methods"),
    ("/website-reviews", "reviews"),
]


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


def download_image(src: str) -> str | None:
    if not src:
        return None

    from urllib.parse import urljoin, urlparse

    full_url = urljoin(BASE_URL, src)
    parsed = urlparse(full_url)
    filename = unquote(Path(parsed.path).name)
    # Strip query string artifacts from filename
    filename = re.sub(r"[^\w.\-]", "_", filename)

    dest = STATIC_DIR / filename
    if dest.exists():
        return f"/images/{filename}"

    try:
        time.sleep(0.5)
        resp = SESSION.get(full_url, timeout=30)
        resp.raise_for_status()
        STATIC_DIR.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return f"/images/{filename}"
    except Exception as e:
        print(f"    WARNING: Failed to download {full_url}: {e}")
        return None


def update_markdown(section: str, slug: str, image_path: str) -> bool:
    filepath = CONTENT_DIR / section / f"{slug}.md"
    if not filepath.exists():
        return False

    content = filepath.read_text()
    parts = content.split("---", 2)
    if len(parts) < 3:
        return False

    fm = parts[1]
    if "\nimage:" in fm or "\nthumbnail:" in fm:
        return False

    # Add image after the url: line
    fm = fm.replace("\nauthors:", f"\nimage: {image_path}\nauthors:")
    # For reviews (no authors line), add after url:
    if image_path not in fm:
        fm = fm.replace("\nwebsite_authors:", f"\nimage: {image_path}\nwebsite_authors:")
    # Fallback: add after url line
    if image_path not in fm:
        fm = re.sub(r"\nurl: ([^\n]+)", rf"\nurl: \1\nimage: {image_path}", fm)

    filepath.write_text("---" + fm + "---" + parts[2])
    return True


def process_section(listing_path: str, section: str):
    print(f"\nProcessing {section} ({listing_path})")

    first_url = f"{BASE_URL}{listing_path}"
    soup = fetch(first_url)
    total_pages = get_total_pages(soup)
    print(f"  {total_pages} page(s)")

    updated = 0

    for page_num in range(total_pages):
        if page_num > 0:
            soup = fetch(f"{first_url}?page={page_num}")

        for row in soup.select("div.vdh > div.views-row"):
            link = row.select_one("h2 a")
            if not link or not link.get("href"):
                continue

            slug = link["href"].strip("/").split("/")[-1]
            img = row.select_one("img")

            if img and img.get("src"):
                image_path = download_image(img["src"])
                if image_path:
                    if update_markdown(section, slug, image_path):
                        updated += 1

    print(f"  Updated {updated} files in {section}")


def main():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    for listing_path, section in SECTIONS:
        process_section(listing_path, section)

    print("\nDone!")


if __name__ == "__main__":
    main()
