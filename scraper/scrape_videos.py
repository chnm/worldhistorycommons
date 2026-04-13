"""
Scrape YouTube embed URLs from source pages that have video/audio embeds
instead of images. Adds youtube_id to front matter.

Usage:
    cd scraper && uv run python scrape_videos.py
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


def fetch(url: str) -> BeautifulSoup:
    time.sleep(DELAY)
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def main():
    print("Scanning source files for pages without images (likely video/audio)...")

    # Find sources that have no image or have a placeholder image
    candidates = []
    for md_file in sorted(CONTENT_DIR.glob("*.md")):
        if md_file.name == "_index.md":
            continue

        content = md_file.read_text()

        # Skip if already has youtube_id
        if "youtube_id:" in content:
            continue

        # Check if image is missing or is a placeholder
        image_match = re.search(r"^image: (.*)$", content, re.MULTILINE)
        if image_match:
            image_val = image_match.group(1).strip()
            # Skip pages with real images (not placeholders)
            if image_val and "Icons-" not in image_val and "View_Document" not in image_val and "ViewDocument" not in image_val and "Text_Image" not in image_val:
                continue

        url_match = re.search(r"^url: (.+)$", content, re.MULTILINE)
        if url_match:
            candidates.append((md_file, url_match.group(1).strip()))

    print(f"Found {len(candidates)} candidates to check for videos")

    updated = 0
    for md_file, url_path in candidates:
        full_url = f"{BASE_URL}{url_path}"
        print(f"  [{updated}] GET {full_url}")

        try:
            soup = fetch(full_url)
        except Exception as e:
            print(f"    ERROR: {e}")
            continue

        # Look for YouTube iframe
        iframe = soup.select_one("iframe[src*='youtube.com/embed']")
        if not iframe:
            continue

        src = iframe.get("src", "")
        # Extract video ID from embed URL
        match = re.search(r"youtube\.com/embed/([^?&]+)", src)
        if not match:
            continue

        youtube_id = match.group(1)
        print(f"    Found YouTube ID: {youtube_id}")

        # Update front matter
        content = md_file.read_text()
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue

        fm = parts[1]
        # Add youtube_id after the image line
        if "\nimage:" in fm:
            fm = re.sub(r"\nimage: [^\n]*", rf"\nimage: \nyoutube_id: {youtube_id}", fm)
        else:
            fm = fm.rstrip() + f"\nyoutube_id: {youtube_id}\n"

        md_file.write_text("---" + fm + "---" + parts[2])
        updated += 1

    print(f"\nUpdated {updated} files with YouTube IDs")


if __name__ == "__main__":
    main()
