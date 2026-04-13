"""
Scraper for worldhistorycommons.org → Hugo markdown files.

Usage:
    cd scraper && uv run python scrape.py

Output goes to ../content/{sources,teaching,methods,reviews}/
Images go to ../static/images/
"""

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

BASE_URL = "https://worldhistorycommons.org"
OUTPUT_DIR = Path(__file__).parent.parent / "content"
STATIC_DIR = Path(__file__).parent.parent / "static" / "images"
DELAY = 1  # seconds between requests (be polite)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "WHC-Hugo-Migration/1.0 (RRCHNM; content migration)"
})

# Section configs: (listing_path, hugo_section, content_type_class)
SECTIONS = [
    ("/primary-sources", "sources", "node-source_page"),
    ("/teaching", "teaching", "node-teaching"),
    ("/method", "methods", "node-methods"),
    ("/website-reviews", "reviews", "node-review"),
]


def fetch(url: str) -> BeautifulSoup:
    """Fetch a URL and return parsed soup. Respects delay."""
    time.sleep(DELAY)
    print(f"  GET {url}")
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def get_total_pages(soup: BeautifulSoup) -> int:
    """Extract total page count from pager."""
    last_link = soup.select_one("li.pager__item--last a")
    if last_link:
        href = last_link.get("href", "")
        match = re.search(r"page=(\d+)", href)
        if match:
            return int(match.group(1)) + 1  # 0-indexed
    return 1


def collect_urls(listing_path: str) -> list[str]:
    """Crawl all pages of a listing and collect detail page URLs."""
    urls = []
    first_url = f"{BASE_URL}{listing_path}"
    soup = fetch(first_url)
    total_pages = get_total_pages(soup)
    print(f"  Found {total_pages} pages for {listing_path}")

    for page_num in range(total_pages):
        if page_num > 0:
            soup = fetch(f"{first_url}?page={page_num}")

        for row in soup.select("div.vdh > div.views-row"):
            link = row.select_one("h2 a")
            if link and link.get("href"):
                urls.append(link["href"])

    print(f"  Collected {len(urls)} URLs from {listing_path}")
    return urls


def slugify(path: str) -> str:
    """Convert a URL path to a filename slug."""
    slug = path.strip("/").split("/")[-1]
    return slug or "index"


def download_image(src: str) -> str | None:
    """Download an image and return the Hugo-relative path, or None on failure."""
    if not src:
        return None

    full_url = urljoin(BASE_URL, src)
    # Derive a clean filename from the URL
    parsed = urlparse(full_url)
    # Strip Drupal image style paths to get original filename
    path_parts = parsed.path
    # e.g., /sites/default/files/styles/medium/public/2025-11/file.jpg → file.jpg
    # or /sites/default/files/2025-11/file.jpg → file.jpg
    filename = unquote(Path(path_parts).name)
    # Sanitize
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


def html_to_markdown(element) -> str:
    """Convert a BeautifulSoup element to clean markdown."""
    if element is None:
        return ""
    html = str(element)
    text = md(html, heading_style="atx", strip=["img"])
    # Clean up excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_tags(soup: BeautifulSoup) -> dict:
    """Extract region, subject, and time period tags."""
    tags = {"regions": [], "subjects": [], "time_periods": []}
    for a in soup.select("div.tags a"):
        href = a.get("href", "")
        name = a.get_text(strip=True)
        if href.startswith("/region/"):
            tags["regions"].append(name)
        elif href.startswith("/subject/"):
            tags["subjects"].append(name)
        elif href.startswith("/time-period/"):
            tags["time_periods"].append(name)
    return tags


def extract_node_id(soup: BeautifulSoup) -> str | None:
    """Extract Drupal node ID from settings JSON."""
    script = soup.select_one('script[data-drupal-selector="drupal-settings-json"]')
    if script and script.string:
        try:
            data = json.loads(script.string)
            path = data.get("path", {}).get("currentPath", "")
            if path.startswith("node/"):
                return path.split("/")[1]
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def yaml_list(items: list[str], indent: str = "") -> str:
    """Format a list for YAML front matter."""
    if not items:
        return "[]"
    lines = [f'\n{indent}  - "{item}"' for item in items]
    return "".join(lines)


def yaml_escape(s: str) -> str:
    """Escape a string for YAML front matter."""
    if not s:
        return '""'
    # Replace backslashes first to avoid double-escaping
    s = s.replace("\\", "\\\\")
    # For multiline strings, use YAML block scalar
    if "\n" in s:
        indented = s.replace("\n", "\n  ")
        return f"|\n  {indented}"
    # If it contains special chars, quote it
    if any(c in s for c in ":{}[]&*?|->!%@`#,\"'"):
        s = s.replace('"', '\\"')
        return f'"{s}"'
    return f'"{s}"'


def parse_source(soup: BeautifulSoup, url_path: str) -> dict:
    """Parse a primary source detail page."""
    title = soup.select_one("div.content-header h1")
    title_text = title.get_text(strip=True) if title else "Untitled"

    # Main image
    img = soup.select_one("div.image-wrap img")
    image_path = None
    if img and img.get("src"):
        image_path = download_image(img["src"])

    # Annotation
    annotation = ""
    for box in soup.select("div.box-border"):
        h2 = box.select_one("h2.box-border--title")
        if h2 and "Annotation" in h2.get_text():
            content_div = h2.find_next_sibling("div")
            if content_div:
                annotation = html_to_markdown(content_div)
            break

    # Source citation
    citation_meta = soup.select_one("div.content-meta")
    citation = html_to_markdown(citation_meta) if citation_meta else ""

    # Credits
    credits = ""
    for detail in soup.select("div.content-details details"):
        summary = detail.select_one("summary h3")
        if summary and "Credits" in summary.get_text():
            well = detail.select_one("div.well--data")
            if well:
                credits = html_to_markdown(well)
            break

    # How to cite
    cite_span = soup.select_one("div.citation span")
    how_to_cite = cite_span.get_text(strip=True) if cite_span else ""

    tags = extract_tags(soup)
    node_id = extract_node_id(soup)

    return {
        "title": title_text,
        "type": "source",
        "image": image_path,
        "annotation": annotation,
        "citation": citation,
        "credits": credits,
        "how_to_cite": how_to_cite,
        "tags": tags,
        "node_id": node_id,
        "url_path": url_path,
    }


def parse_teaching_or_methods(soup: BeautifulSoup, url_path: str, content_type: str) -> dict:
    """Parse a teaching or methods detail page."""
    title = soup.select_one("div.content-header h1")
    title_text = title.get_text(strip=True) if title else "Untitled"

    # Author(s)
    author_div = soup.select_one("div.content-header--author")
    authors = []
    if author_div:
        for div in author_div.find_all("div", recursive=False):
            name = div.get_text(strip=True)
            if name:
                authors.append(name)

    # Overview
    overview = ""
    for box in soup.select("div.box-border"):
        h2 = box.select_one("h2.box-border--title")
        if h2 and "Overview" in h2.get_text():
            content_div = h2.find_next_sibling("div")
            if content_div:
                overview = html_to_markdown(content_div)
            break

    # Expandable sections (Essay, DBQ, Discussion Questions, Bibliography, Credits)
    sections = {}
    for detail in soup.select("div.content-details details"):
        summary = detail.select_one("summary h3")
        if not summary:
            continue
        section_name = summary.get_text(strip=True)
        well = detail.select_one("div.well--data")
        if well:
            # Handle slideshow separately
            if section_name == "Primary Sources":
                slides = []
                for slide in well.select("div.slideshow-slide"):
                    slide_title_el = slide.select_one("h4.slideshow-slide--title")
                    slide_link = slide.select_one("a.slideshow-slide--img")
                    slide_text = slide.select_one("div.slideshow-slide--text")
                    slides.append({
                        "title": slide_title_el.get_text(strip=True) if slide_title_el else "",
                        "link": slide_link["href"] if slide_link and slide_link.get("href") else "",
                        "annotation": html_to_markdown(slide_text) if slide_text else "",
                    })
                sections["primary_sources"] = slides
            else:
                sections[section_name.lower().replace(" ", "_")] = html_to_markdown(well)

    tags = extract_tags(soup)
    node_id = extract_node_id(soup)

    hugo_type = "teaching" if content_type == "node-teaching" else "methods"

    return {
        "title": title_text,
        "type": hugo_type,
        "authors": authors,
        "overview": overview,
        "sections": sections,
        "tags": tags,
        "node_id": node_id,
        "url_path": url_path,
    }


def parse_review(soup: BeautifulSoup, url_path: str) -> dict:
    """Parse a website review detail page."""
    title = soup.select_one("a.review-header h1") or soup.select_one("div.content-header h1")
    title_text = title.get_text(strip=True) if title else "Untitled"

    # Website author(s)
    author_div = soup.select_one("a.review-header div.content-header--author") or soup.select_one(
        "div.content-header--author"
    )
    website_authors = author_div.get_text(strip=True) if author_div else ""

    # Reviewed URL
    reviewed_url = ""
    link_div = soup.select_one("div.credit div.link a")
    if link_div and link_div.get("href"):
        reviewed_url = link_div["href"]

    # Reviewer
    reviewer = ""
    credit_text = soup.select_one("div.credit div.text")
    if credit_text:
        reviewer = credit_text.get_text(strip=True)

    # Body
    body_div = soup.select_one("div.review-well")
    body = html_to_markdown(body_div) if body_div else ""

    # Pull quote
    pull_quote_div = soup.select_one("div.pull-quote--sidebar div.quote")
    pull_quote = pull_quote_div.get_text(strip=True) if pull_quote_div else ""

    # How to cite
    cite_span = soup.select_one("div.citation span")
    how_to_cite = cite_span.get_text(strip=True) if cite_span else ""

    tags = extract_tags(soup)
    node_id = extract_node_id(soup)

    return {
        "title": title_text,
        "type": "review",
        "website_authors": website_authors,
        "reviewer": reviewer,
        "reviewed_url": reviewed_url,
        "body": body,
        "pull_quote": pull_quote,
        "how_to_cite": how_to_cite,
        "tags": tags,
        "node_id": node_id,
        "url_path": url_path,
    }


def write_source_hugo(data: dict, section_dir: Path):
    """Write a primary source as Hugo markdown."""
    slug = slugify(data["url_path"])
    filepath = section_dir / f"{slug}.md"

    tags = data["tags"]
    fm = f"""---
title: {yaml_escape(data['title'])}
type: source
drupal_node_id: {data.get('node_id', '')}
url: {data['url_path']}
image: {data.get('image') or ''}
regions: {yaml_list(tags['regions'])}
subjects: {yaml_list(tags['subjects'])}
time_periods: {yaml_list(tags['time_periods'])}
source_citation: {yaml_escape(data.get('citation', ''))}
credits: {yaml_escape(data.get('credits', ''))}
how_to_cite: {yaml_escape(data.get('how_to_cite', ''))}
---

{data.get('annotation', '')}
"""
    filepath.write_text(fm)


def write_teaching_hugo(data: dict, section_dir: Path):
    """Write a teaching/methods page as Hugo markdown."""
    slug = slugify(data["url_path"])
    filepath = section_dir / f"{slug}.md"

    tags = data["tags"]
    authors_yaml = yaml_list(data.get("authors", []))
    sections = data.get("sections", {})

    fm = f"""---
title: {yaml_escape(data['title'])}
type: {data['type']}
drupal_node_id: {data.get('node_id', '')}
url: {data['url_path']}
authors: {authors_yaml}
regions: {yaml_list(tags['regions'])}
subjects: {yaml_list(tags['subjects'])}
time_periods: {yaml_list(tags['time_periods'])}
---

## Overview

{data.get('overview', '')}
"""

    # Add remaining sections
    for key, value in sections.items():
        if key == "primary_sources" and isinstance(value, list):
            fm += "\n## Primary Sources\n\n"
            for slide in value:
                fm += f"### [{slide['title']}]({slide['link']})\n\n"
                if slide.get("annotation"):
                    fm += f"{slide['annotation']}\n\n"
        elif key == "credits":
            fm += f"\n## Credits\n\n{value}\n"
        else:
            heading = key.replace("_", " ").title()
            fm += f"\n## {heading}\n\n{value}\n"

    filepath.write_text(fm)


def write_review_hugo(data: dict, section_dir: Path):
    """Write a website review as Hugo markdown."""
    slug = slugify(data["url_path"])
    filepath = section_dir / f"{slug}.md"

    tags = data["tags"]
    fm = f"""---
title: {yaml_escape(data['title'])}
type: review
drupal_node_id: {data.get('node_id', '')}
url: {data['url_path']}
website_authors: {yaml_escape(data.get('website_authors', ''))}
reviewer: {yaml_escape(data.get('reviewer', ''))}
reviewed_url: {yaml_escape(data.get('reviewed_url', ''))}
pull_quote: {yaml_escape(data.get('pull_quote', ''))}
how_to_cite: {yaml_escape(data.get('how_to_cite', ''))}
regions: {yaml_list(tags['regions'])}
subjects: {yaml_list(tags['subjects'])}
time_periods: {yaml_list(tags['time_periods'])}
---

{data.get('body', '')}
"""
    filepath.write_text(fm)


def process_section(listing_path: str, hugo_section: str, content_type: str):
    """Process an entire section: collect URLs, scrape, write Hugo files."""
    print(f"\n{'='*60}")
    print(f"Processing: {hugo_section} ({listing_path})")
    print(f"{'='*60}")

    section_dir = OUTPUT_DIR / hugo_section
    section_dir.mkdir(parents=True, exist_ok=True)

    # Collect all URLs from listing pages
    urls = collect_urls(listing_path)

    # Process each detail page
    for i, url_path in enumerate(urls):
        full_url = f"{BASE_URL}{url_path}"
        print(f"  [{i+1}/{len(urls)}] {url_path}")

        try:
            soup = fetch(full_url)
        except Exception as e:
            print(f"    ERROR fetching {full_url}: {e}")
            continue

        try:
            if content_type == "node-source_page":
                data = parse_source(soup, url_path)
                write_source_hugo(data, section_dir)
            elif content_type in ("node-teaching", "node-methods"):
                data = parse_teaching_or_methods(soup, url_path, content_type)
                write_teaching_hugo(data, section_dir)
            elif content_type == "node-review":
                data = parse_review(soup, url_path)
                write_review_hugo(data, section_dir)
        except Exception as e:
            print(f"    ERROR parsing {url_path}: {e}")
            continue

    print(f"  Done: wrote {len(urls)} files to {section_dir}")


def write_section_index_pages():
    """Write _index.md for each section."""
    indexes = {
        "sources": ("Primary Sources", "Browse primary source documents from world history."),
        "teaching": ("Teaching", "Teaching modules and resources for world history."),
        "methods": ("Methods", "Methodological approaches to world history."),
        "reviews": ("Website Reviews", "Reviews of world history websites and digital resources."),
    }
    for section, (title, description) in indexes.items():
        section_dir = OUTPUT_DIR / section
        section_dir.mkdir(parents=True, exist_ok=True)
        index_path = section_dir / "_index.md"
        index_path.write_text(f"""---
title: {yaml_escape(title)}
description: {yaml_escape(description)}
---
""")


def main():
    print("World History Commons → Hugo Scraper")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Images: {STATIC_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    write_section_index_pages()

    for listing_path, hugo_section, content_type in SECTIONS:
        process_section(listing_path, hugo_section, content_type)

    print(f"\n{'='*60}")
    print("DONE!")
    print(f"Content: {OUTPUT_DIR}")
    print(f"Images:  {STATIC_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
