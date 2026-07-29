"""
Synchronize rendered Teaching and Methods content from Drupal.

This updater preserves the existing Hugo front matter and slideshow media while
replacing the rendered body sections and citation with their Drupal values.

Usage:
    cd scraper
    uv run python sync_teaching_content.py --report /tmp/parity.json
    uv run python sync_teaching_content.py --url /analyzing-personal-accounts-0
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify as md


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://worldhistorycommons.org"
CONTENT_DIRS = (
    PROJECT_ROOT / "content" / "teaching",
    PROJECT_ROOT / "content" / "methods",
)
STATIC_DIR = PROJECT_ROOT / "static" / "images"
FRONT_MATTER_RE = re.compile(r"\A(---\n.*?\n---\n)(.*)\Z", re.DOTALL)
PRIMARY_SECTION_RE = re.compile(
    r"(?ms)^##[ \t]+Primary Sources[ \t]*\n(.*?)(?=^##[ \t]+|\Z)"
)
PRIMARY_ENTRY_RE = re.compile(
    r"(?ms)^###[ \t]+\[(?P<title>.*?)\]\((?P<link>.*?)\)[ \t]*\n"
    r"(?P<body>.*?)(?=^###[ \t]+\[|\Z)"
)
IMAGE_RE = re.compile(r"!\[(?P<alt>.*?)\]\((?P<src>.*?)\)")

SESSION = requests.Session()
SESSION.headers.update(
    {"User-Agent": "WHC-Hugo-Migration/1.0 (RRCHNM; content migration)"}
)


@dataclass(frozen=True)
class ContentSection:
    label: str
    content: str


def normalize_path(value: str) -> str:
    path = urlparse(value).path.rstrip("/")
    return path or "/"


def fetch(url: str, delay: float) -> BeautifulSoup:
    if delay > 0:
        time.sleep(delay)
    response = SESSION.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def local_image_path(src: str, static_dir: Path = STATIC_DIR) -> tuple[str, Path]:
    filename = unquote(Path(urlparse(src).path).name)
    filename = re.sub(r"[^\w.\-]", "_", filename)
    return f"/images/{filename}", static_dir / filename


def localize_images(
    element,
    *,
    base_url: str = BASE_URL,
    static_dir: Path = STATIC_DIR,
    download_missing: bool = True,
) -> BeautifulSoup:
    """Clone an HTML fragment and rewrite its images to local Hugo paths."""
    fragment = BeautifulSoup(str(element), "html.parser")
    for image in fragment.find_all("img"):
        src = image.get("src", "")
        if not src:
            image.decompose()
            continue
        local_src, destination = local_image_path(src, static_dir)
        if not destination.exists() and download_missing:
            response = SESSION.get(urljoin(base_url, src), timeout=30)
            response.raise_for_status()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.content)
        if destination.exists():
            image["src"] = local_src
        else:
            image["src"] = urljoin(base_url, src)
    return fragment


def normalize_legacy_breaks(fragment: BeautifulSoup) -> None:
    """Move parser-nested children out of void br elements."""
    for line_break in reversed(fragment.find_all("br")):
        for child in reversed(list(line_break.contents)):
            line_break.insert_after(child.extract())


def unwrap_layout_tables(fragment: BeautifulSoup) -> None:
    """Flatten headerless legacy layout tables while retaining data tables."""
    for table in fragment.find_all("table"):
        if table.find("th") is not None:
            continue
        for container in table.find_all(
            ["caption", "colgroup", "col", "thead", "tbody", "tfoot", "tr", "td"]
        ):
            container.unwrap()
        table.unwrap()


def html_to_markdown(
    element,
    *,
    base_url: str = BASE_URL,
    static_dir: Path = STATIC_DIR,
    download_missing: bool = True,
) -> str:
    if element is None:
        return ""
    fragment = localize_images(
        element,
        base_url=base_url,
        static_dir=static_dir,
        download_missing=download_missing,
    )
    for hidden in fragment.find_all(["script", "style", "template"]):
        hidden.decompose()
    for link in fragment.find_all("a", href=True):
        if any(character in link["href"] for character in "<>"):
            del link["href"]
    normalize_legacy_breaks(fragment)
    unwrap_layout_tables(fragment)
    nested_headings: dict[str, str] = {}
    for index, heading in enumerate(fragment.find_all(["h1", "h2"])):
        placeholder = f"WHCNESTEDHEADINGTOKEN{index}X"
        nested_headings[placeholder] = str(heading)
        heading.replace_with(NavigableString(placeholder))
    for inline in fragment.find_all(
        ["a", "abbr", "b", "cite", "code", "em", "i", "s", "small", "span",
         "strong", "sub", "sup", "u"]
    ):
        text = inline.get_text()
        if text and not text.strip():
            inline.replace_with(NavigableString(text))
    text = md(str(fragment), heading_style="atx")
    # Drupal occasionally nests h1/h2 headings inside a collapsible section.
    # Preserve the original HTML (including inline emphasis) without making
    # Hugo treat them as new top-level Markdown sections.
    for placeholder, heading_html in nested_headings.items():
        text = text.replace(placeholder, heading_html)
    text = re.sub(r"[ \t]{2,}\n", "<br>\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def existing_primary_images(markdown: str) -> dict[str, str]:
    """Map each source link to its existing Hugo image Markdown."""
    section = PRIMARY_SECTION_RE.search(markdown)
    if section is None:
        return {}
    images: dict[str, str] = {}
    for entry in PRIMARY_ENTRY_RE.finditer(section.group(1)):
        image = IMAGE_RE.search(entry.group("body"))
        if image:
            images[normalize_path(entry.group("link"))] = image.group(0)
    return images


def primary_sources_markdown(
    well,
    existing_images: dict[str, str],
    *,
    base_url: str = BASE_URL,
    static_dir: Path = STATIC_DIR,
    download_missing: bool = True,
) -> str:
    entries: list[str] = []
    for slide in well.select("div.slideshow-slide"):
        title_element = slide.select_one("h4.slideshow-slide--title")
        link_element = slide.select_one("a.slideshow-slide--img")
        text_element = slide.select_one("div.slideshow-slide--text")
        title = title_element.get_text(" ", strip=True) if title_element else ""
        link = link_element.get("href", "") if link_element else ""
        pieces = [f"### [{title}]({link})"]

        image_markdown = existing_images.get(normalize_path(link))
        if image_markdown is None:
            image = slide.select_one("a.slideshow-slide--img img")
            if image:
                localized = localize_images(
                    image,
                    base_url=base_url,
                    static_dir=static_dir,
                    download_missing=download_missing,
                )
                image_markdown = md(str(localized), heading_style="atx").strip()
        if image_markdown:
            pieces.append(image_markdown)

        annotation = html_to_markdown(
            text_element,
            base_url=base_url,
            static_dir=static_dir,
            download_missing=download_missing,
        )
        pieces.append("#### Annotation")
        if annotation:
            pieces.append(annotation)
        entries.append("\n\n".join(pieces))
    return "\n\n".join(entries)


def get_overview(
    soup: BeautifulSoup,
    *,
    base_url: str = BASE_URL,
    static_dir: Path = STATIC_DIR,
    download_missing: bool = True,
) -> str:
    for box in soup.select("div.box-border"):
        heading = box.select_one("h2.box-border--title")
        if heading and heading.get_text(" ", strip=True).lower() == "overview":
            return html_to_markdown(
                heading.find_next_sibling("div"),
                base_url=base_url,
                static_dir=static_dir,
                download_missing=download_missing,
            )
    return ""


def get_sections(
    soup: BeautifulSoup,
    existing_images: dict[str, str],
    *,
    base_url: str = BASE_URL,
    static_dir: Path = STATIC_DIR,
    download_missing: bool = True,
) -> list[ContentSection]:
    sections: list[ContentSection] = []
    for detail in soup.select("div.content-details details"):
        heading = detail.select_one("summary h3")
        well = detail.select_one("div.well--data")
        if heading is None or well is None:
            continue
        label = heading.get_text(" ", strip=True)
        if label == "Primary Sources":
            content = primary_sources_markdown(
                well,
                existing_images,
                base_url=base_url,
                static_dir=static_dir,
                download_missing=download_missing,
            )
        else:
            content = html_to_markdown(
                well,
                base_url=base_url,
                static_dir=static_dir,
                download_missing=download_missing,
            )
        sections.append(ContentSection(label, content))
    return sections


def get_how_to_cite(soup: BeautifulSoup) -> str:
    citation = soup.select_one("div.citation span")
    return citation.get_text(" ", strip=True) if citation else ""


def format_body(overview: str, sections: list[ContentSection]) -> str:
    blocks = [f"## Overview\n\n{overview.strip()}"]
    blocks.extend(
        f"## {section.label}\n\n{section.content.strip()}"
        for section in sections
    )
    return "\n\n".join(blocks).rstrip() + "\n"


def merge_front_matter_field(markdown: str, field_name: str, value: str) -> str:
    """Add or replace a scalar/block field without parsing unrelated YAML."""
    match = FRONT_MATTER_RE.match(markdown)
    if match is None:
        raise ValueError("Markdown is missing YAML front matter")
    front_matter, body = match.groups()
    lines = front_matter.rstrip().splitlines()
    closing_index = len(lines) - 1
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith(f"{field_name}:")
        ),
        None,
    )
    end = start + 1 if start is not None else closing_index
    if start is not None:
        while end < closing_index and (
            lines[end].startswith((" ", "\t")) or not lines[end].strip()
        ):
            end += 1
    replacement = (
        [f"{field_name}: |"]
        + [f"  {line}" if line else "" for line in value.strip().splitlines()]
        if value.strip()
        else [f'{field_name}: ""']
    )
    if start is None:
        lines[closing_index:closing_index] = replacement
    else:
        lines[start:end] = replacement
    return "\n".join(lines) + "\n" + body


def replace_body(markdown: str, body: str) -> str:
    match = FRONT_MATTER_RE.match(markdown)
    if match is None:
        raise ValueError("Markdown is missing YAML front matter")
    return match.group(1).rstrip() + "\n\n" + body.rstrip() + "\n"


def update_markdown(
    filepath: Path,
    soup: BeautifulSoup,
    *,
    base_url: str = BASE_URL,
    static_dir: Path = STATIC_DIR,
    download_missing: bool = True,
    dry_run: bool = False,
) -> bool:
    current = filepath.read_text(encoding="utf-8")
    images = existing_primary_images(current)
    overview = get_overview(
        soup,
        base_url=base_url,
        static_dir=static_dir,
        download_missing=download_missing,
    )
    sections = get_sections(
        soup,
        images,
        base_url=base_url,
        static_dir=static_dir,
        download_missing=download_missing,
    )
    updated = replace_body(current, format_body(overview, sections))
    updated = merge_front_matter_field(
        updated, "how_to_cite", get_how_to_cite(soup)
    )
    if updated == current:
        return False
    if not dry_run:
        filepath.write_text(updated, encoding="utf-8")
    return True


def front_matter_url(markdown: str) -> str:
    match = re.search(r"^url:[ \t]*(.+)$", markdown, re.MULTILINE)
    return normalize_path(match.group(1).strip().strip("\"'")) if match else ""


def content_files_by_path(content_dirs: tuple[Path, ...]) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for content_dir in content_dirs:
        for filepath in sorted(content_dir.glob("*.md")):
            if filepath.name == "_index.md":
                continue
            path = front_matter_url(filepath.read_text(encoding="utf-8"))
            if path:
                files[path] = filepath
    return files


def report_paths(report_path: Path) -> set[str]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return {
        normalize_path(page["path"])
        for page in report.get("pages", [])
        if page.get("kind") in {"teaching", "methods"} and page.get("findings")
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize Drupal Teaching and Methods rendered content."
    )
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument(
        "--content-dir",
        type=Path,
        action="append",
        help="Teaching or Methods content directory (repeatable).",
    )
    parser.add_argument("--static-dir", type=Path, default=STATIC_DIR)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    content_dirs = tuple(args.content_dir or CONTENT_DIRS)
    files = content_files_by_path(content_dirs)
    selected = set(files)
    if args.report:
        selected &= report_paths(args.report)
    if args.url:
        selected &= {normalize_path(value) for value in args.url}

    requested = {normalize_path(value) for value in args.url}
    missing_local = sorted(requested - set(files))
    for path in missing_local:
        print(f"ERROR no local Teaching/Methods file for {path}")

    candidates = [(path, files[path]) for path in sorted(selected)]
    print(f"Checking {len(candidates)} Teaching/Methods page(s)...")
    updated_count = 0
    error_count = len(missing_local)
    for index, (path, filepath) in enumerate(candidates, start=1):
        try:
            soup = fetch(
                f"{args.base_url.rstrip('/')}{path}",
                args.delay if index > 1 else 0,
            )
            changed = update_markdown(
                filepath,
                soup,
                base_url=args.base_url,
                static_dir=args.static_dir,
                download_missing=not args.dry_run,
                dry_run=args.dry_run,
            )
        except (OSError, ValueError, requests.RequestException) as exc:
            error_count += 1
            print(f"ERROR {path}: {exc}")
            continue
        if changed:
            updated_count += 1
            action = "Would update" if args.dry_run else "Updated"
            print(f"[{index}/{len(candidates)}] {action} {path}")

    print("\nTeaching/Methods synchronization summary")
    print(f"  Checked: {len(candidates)}")
    print(f"  Updated: {updated_count}")
    print(f"  Errors:  {error_count}")
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
