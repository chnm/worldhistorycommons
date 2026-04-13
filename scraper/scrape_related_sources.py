"""
Scrape the related source tiles (box-tile images) from teaching and methods
detail pages and add them as YAML front matter.

Usage:
    cd scraper && uv run python scrape_related_sources.py
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


def yaml_escape(s: str) -> str:
    if not s:
        return '""'
    s = s.strip()
    if any(c in s for c in ':{}[]&*?|->!%@`#,"\'\\'):
        s = s.replace('"', '\\"')
        return f'"{s}"'
    return f'"{s}"'


def get_related_sources(soup: BeautifulSoup) -> list[dict]:
    """Extract related source tiles from the first box-tile in two-cols."""
    two_cols = soup.select_one("div.two-cols")
    if not two_cols:
        return []

    box_tile = two_cols.select_one("div.box-tile")
    if not box_tile:
        return []

    sources = []
    for link in box_tile.select("a"):
        href = link.get("href", "")
        img = link.select_one("img")
        if not href or not img:
            continue

        img_src = img.get("src", "")
        alt = img.get("alt", "").strip()

        image_path = download_image(img_src)
        if image_path:
            sources.append({
                "link": href,
                "image": image_path,
                "alt": alt,
            })

    return sources


def update_markdown(filepath: Path, related: list[dict]) -> bool:
    """Add related_sources to front matter."""
    content = filepath.read_text()
    parts = content.split("---", 2)
    if len(parts) < 3:
        return False

    fm = parts[1]
    if "related_sources:" in fm:
        return False

    # Build YAML block
    yaml_block = "\nrelated_sources:"
    for src in related:
        yaml_block += f"\n  - link: {yaml_escape(src['link'])}"
        yaml_block += f"\n    image: {yaml_escape(src['image'])}"
        yaml_block += f"\n    alt: {yaml_escape(src['alt'])}"

    # Insert before the closing of front matter (before regions/subjects or end)
    fm = fm.rstrip() + yaml_block + "\n"

    filepath.write_text("---" + fm + "---" + parts[2])
    return True


def process_section(section: str):
    section_dir = CONTENT_DIR / section
    if not section_dir.exists():
        return

    print(f"\nProcessing {section}...")
    updated = 0

    for md_file in sorted(section_dir.glob("*.md")):
        if md_file.name == "_index.md":
            continue

        content = md_file.read_text()
        url_match = re.search(r"^url: (.+)$", content, re.MULTILINE)
        if not url_match:
            continue

        # Skip if already has related_sources
        if "related_sources:" in content:
            continue

        url_path = url_match.group(1).strip()
        full_url = f"{BASE_URL}{url_path}"

        try:
            soup = fetch(full_url)
        except Exception as e:
            print(f"    ERROR: {e}")
            continue

        related = get_related_sources(soup)
        if related:
            if update_markdown(md_file, related):
                updated += 1
                print(f"    Updated: {md_file.name} ({len(related)} sources)")
        else:
            print(f"    No related sources: {md_file.name}")

    print(f"  Updated {updated} files in {section}")


def main():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    process_section("teaching")
    process_section("methods")
    print("\nDone!")


if __name__ == "__main__":
    main()
