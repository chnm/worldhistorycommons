"""
Scrape the 31 standalone pages missing from the main scrape.

Usage:
    cd scraper && uv run python scrape_pages.py
"""

import os
import re
import time
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

BASE_URL = "https://worldhistorycommons.org"
CONTENT_DIR = Path(__file__).parent.parent / "content"
PAGES_DIR = CONTENT_DIR / "pages"
DELAY = 1

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "WHC-Hugo-Migration/1.0 (RRCHNM; content migration)"
})

MISSING_URLS = [
    "/about",
    "/advisory-board",
    "/beyond-survey-courses-transcript",
    "/community-college-video-guides",
    "/contributing-sites",
    "/creative-commons-and-adapting-resources-transcript",
    "/diagram-url",
    "/engaging-students-primary-sources-transcript",
    "/finding-secondary-sources-transcript",
    "/finding-sources-world-history-projects-transcript",
    "/finding-specific-sources",
    "/global-perspectives-students-transcript",
    "/guide-using-world-history-commons",
    "/integrating-world-history-commons-your-lms-transcript",
    "/long-teaching-module-do%C3%B1a-marina-cort%C3%A9s-translator",
    "/making-connections-using-thematic-approach-transcript",
    "/navigating-find-primary-sources-transcript",
    "/organizing-learning-materials-2-transcript",
    "/organizing-learning-materials-transcript",
    "/project-team",
    "/region-and-time-period-breakdown",
    "/supplementing-courses-free-resources",
    "/supplementing-world-history-textbooks",
    "/teaching-gender-health-and-reproduction-latin-america-1980-2000",
    "/teaching-world-history-material-objects-transcript",
    "/teaching-world-history-through-revolutions-transcript",
    "/women-and-gender-world-history-syllabus-transcript",
    "/women-islamic-world-transcript",
    "/world-history-commons-introductory-video-transcript",
    "/page-pentaglot-manchu-glossary",
    "/page-qing-veritable-records",
]


def already_exists(url_path: str) -> bool:
    """Check if this page was already scraped into another section."""
    slug = url_path.strip("/").split("/")[-1]
    slug = unquote(slug)
    for section in ["sources", "teaching", "methods", "reviews"]:
        if (CONTENT_DIR / section / f"{slug}.md").exists():
            return True
    return False


def html_to_markdown(element) -> str:
    if element is None:
        return ""
    text = md(str(element), heading_style="atx", strip=["img"])
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def yaml_escape(s: str) -> str:
    if not s:
        return '""'
    s = s.replace("\\", "\\\\")
    if "\n" in s:
        indented = s.replace("\n", "\n  ")
        return f"|\n  {indented}"
    if any(c in s for c in ':{}[]&*?|->!%@`#,"\'\\'):
        s = s.replace('"', '\\"')
        return f'"{s}"'
    return f'"{s}"'


def scrape_page(url_path: str):
    slug = unquote(url_path.strip("/").split("/")[-1])

    if already_exists(url_path):
        print(f"  SKIP (already exists): {url_path}")
        return

    full_url = f"{BASE_URL}{url_path}"
    print(f"  GET {full_url}")
    time.sleep(DELAY)

    try:
        resp = SESSION.get(full_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    # Title
    title_el = soup.select_one("div.content-header h1") or soup.select_one("h1") or soup.select_one("title")
    if title_el:
        title = title_el.get_text(strip=True)
        # Strip " | World History Commons" suffix from <title>
        title = re.sub(r"\s*\|\s*World History Commons$", "", title)
    else:
        title = slug.replace("-", " ").title()

    # Body content
    content_block = soup.select_one("#block-whc-content")
    if content_block:
        # Remove the title if it's inside the content block to avoid duplication
        for h1 in content_block.find_all("h1"):
            h1.decompose()
        for label in content_block.select("div.content-header--label"):
            label.decompose()
        body = html_to_markdown(content_block)
    else:
        body = ""

    # Write the file
    filepath = PAGES_DIR / f"{slug}.md"
    filepath.write_text(f"""---
title: {yaml_escape(title)}
url: {url_path}
---

{body}
""")
    print(f"  Wrote: {filepath}")


def main():
    PAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Write section index
    (PAGES_DIR / "_index.md").write_text("""---
title: "Pages"
---
""")

    print(f"Scraping {len(MISSING_URLS)} standalone pages...")
    for url_path in MISSING_URLS:
        scrape_page(url_path)

    print("\nDone!")


if __name__ == "__main__":
    main()
