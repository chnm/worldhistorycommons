"""
Scrape the "Text" details section from primary source pages.
This contains the actual primary source text/transcription (lyrics, documents, etc.)
that appears as a collapsible section below the annotation.

Usage:
    cd scraper && uv run python scrape_source_text.py
"""

import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

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


def html_to_markdown(element) -> str:
    if element is None:
        return ""
    text = md(str(element), heading_style="atx", strip=["img"])
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_source_text(soup: BeautifulSoup) -> str | None:
    """Extract the Text details section content."""
    for detail in soup.select("div.content-details details"):
        summary = detail.select_one("summary h3")
        if summary and summary.get_text(strip=True) == "Text":
            well = detail.select_one("div.well--data")
            if well:
                return html_to_markdown(well)
    return None


def update_markdown(filepath: Path, source_text: str) -> bool:
    """Append the source text as a section in the markdown body."""
    content = filepath.read_text()

    # Don't add if already present
    if "## Text" in content:
        return False

    # Append before end of file
    content = content.rstrip() + "\n\n## Text\n\n" + source_text + "\n"
    filepath.write_text(content)
    return True


def main():
    print("Scanning source files for pages that may have Text sections...")

    # We need to check all source pages — can't easily tell from front matter alone
    # which ones have a Text section. Focus on Text and Audio source types as most likely.
    candidates = []
    for md_file in sorted(CONTENT_DIR.glob("*.md")):
        if md_file.name == "_index.md":
            continue

        content = md_file.read_text()

        # Skip if already has ## Text
        if "## Text" in content:
            continue

        url_match = re.search(r"^url: (.+)$", content, re.MULTILINE)
        if url_match:
            candidates.append((md_file, url_match.group(1).strip()))

    print(f"Checking {len(candidates)} source pages...")

    updated = 0
    checked = 0
    for md_file, url_path in candidates:
        checked += 1
        full_url = f"{BASE_URL}{url_path}"

        if checked % 100 == 0:
            print(f"  Progress: {checked}/{len(candidates)} checked, {updated} updated")

        try:
            soup = fetch(full_url)
        except Exception as e:
            print(f"  ERROR {url_path}: {e}")
            continue

        source_text = get_source_text(soup)
        if source_text:
            if update_markdown(md_file, source_text):
                updated += 1
                print(f"  Found Text: {md_file.name}")

    print(f"\nChecked {checked} pages, updated {updated} files")


if __name__ == "__main__":
    main()
