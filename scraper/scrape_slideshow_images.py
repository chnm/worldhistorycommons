"""
Re-scrape teaching and methods detail pages to extract slideshow images
for the Primary Sources sections, then update the markdown files.

Usage:
    cd scraper && uv run python scrape_slideshow_images.py
"""

import re
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

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


def fetch(url: str) -> BeautifulSoup:
    time.sleep(DELAY)
    print(f"  GET {url}")
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def download_image(src: str) -> str | None:
    if not src:
        return None

    full_url = urljoin(BASE_URL, src)
    parsed = urlparse(full_url)
    filename = unquote(Path(parsed.path).name)
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


def get_slideshow_images(soup: BeautifulSoup) -> dict[str, str]:
    """Extract title -> image_path mapping from slideshow slides."""
    images = {}
    for slide in soup.select("div.slideshow-slide"):
        title_el = slide.select_one("h4.slideshow-slide--title")
        img_link = slide.select_one("a.slideshow-slide--img img")

        if title_el and img_link and img_link.get("src"):
            title = title_el.get_text(strip=True)
            image_path = download_image(img_link["src"])
            if image_path:
                images[title] = image_path

    return images


def update_markdown(filepath: Path, slide_images: dict[str, str]) -> bool:
    """Add images to ### headings in the Primary Sources section."""
    content = filepath.read_text()

    changed = False
    for title, image_path in slide_images.items():
        # Look for ### [Title](link) pattern and add image after it
        # The title in markdown may have slightly different formatting
        # so search for a pattern that includes the title text
        escaped_title = re.escape(title)
        pattern = rf"(### \[{escaped_title}\]\([^)]+\)\n\n)"
        replacement = rf"\1![{title}]({image_path})\n\n"

        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            content = new_content
            changed = True

    if changed:
        filepath.write_text(content)

    return changed


def process_section(section: str):
    """Process all pages in a section."""
    section_dir = CONTENT_DIR / section
    if not section_dir.exists():
        return

    print(f"\nProcessing {section}...")
    updated = 0

    for md_file in sorted(section_dir.glob("*.md")):
        if md_file.name == "_index.md":
            continue

        # Read the file to get the URL
        content = md_file.read_text()
        url_match = re.search(r"^url: (.+)$", content, re.MULTILINE)
        if not url_match:
            continue

        # Only process files that have a Primary Sources section
        if "## Primary Sources" not in content:
            continue

        # Check if images are already added
        if re.search(r"!\[.*\]\(/images/", content):
            continue

        url_path = url_match.group(1).strip()
        full_url = f"{BASE_URL}{url_path}"

        try:
            soup = fetch(full_url)
        except Exception as e:
            print(f"    ERROR fetching {full_url}: {e}")
            continue

        slide_images = get_slideshow_images(soup)
        if slide_images:
            if update_markdown(md_file, slide_images):
                updated += 1
                print(f"    Updated: {md_file.name} ({len(slide_images)} images)")

    print(f"  Updated {updated} files in {section}")


def main():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    process_section("teaching")
    process_section("methods")
    print("\nDone!")


if __name__ == "__main__":
    main()
