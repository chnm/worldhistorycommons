"""
Preserve Text, Transcription, and Translation sections from Drupal sources.

The updater is idempotent: existing sections with the same semantic label are
replaced, missing sections are appended in Drupal order, and unrelated/local-
only sections are preserved.

Usage:
    cd scraper
    uv run python scrape_source_text.py --report ../utils/content_parity.json
    uv run python scrape_source_text.py --url /alma-ata-declaration
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify as md


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://worldhistorycommons.org"
CONTENT_DIR = PROJECT_ROOT / "content" / "sources"
DEFAULT_REPORT = PROJECT_ROOT / "utils" / "content_parity.json"
SECTION_LABELS = ("Text", "Transcription", "Translation")
SECTION_LABEL_LOOKUP = {label.lower(): label for label in SECTION_LABELS}
SOURCE_SECTION_RE = re.compile(
    r"(?ms)^##[ \t]+(Text|Transcription|Translation)[ \t]*\n"
    r".*?(?=^##[ \t]+|\Z)"
)
FRONT_MATTER_RE = re.compile(r"\A(---\n.*?\n---\n)(.*)\Z", re.DOTALL)

SESSION = requests.Session()
SESSION.headers.update(
    {"User-Agent": "WHC-Hugo-Migration/1.0 (RRCHNM; content migration)"}
)


@dataclass(frozen=True)
class SourceSection:
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


def html_to_markdown(element) -> str:
    if element is None:
        return ""
    fragment = BeautifulSoup(str(element), "html.parser")
    for inline in fragment.find_all(
        ["a", "abbr", "b", "cite", "code", "em", "i", "s", "small", "span",
         "strong", "sub", "sup", "u"]
    ):
        text = inline.get_text()
        if text and not text.strip():
            inline.replace_with(NavigableString(text))
    text = md(str(fragment), heading_style="atx", strip=["img"])
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def protect_source_text_markdown(text: str) -> str:
    """Keep literal source-document notation from becoming Markdown syntax."""
    text = re.sub(r"[ \t]{2,}\n", "<br>\n", text)
    text = re.sub(
        r"(?m)^([ \t]*)(\d+)([.)])([ \t]+)",
        r"\1\2\\\3\4",
        text,
    )
    text = re.sub(
        r"(?m)^([ \t]*)(-{3,})([ \t]*)$",
        r"\1\\\2\3",
        text,
    )
    return text.replace("``", r"\`\`")


def get_annotation(soup: BeautifulSoup) -> str:
    for box in soup.select("div.box-border"):
        heading = box.select_one("h2.box-border--title")
        if heading and heading.get_text(" ", strip=True).lower() == "annotation":
            return html_to_markdown(heading.find_next_sibling("div"))
    return ""


def get_source_citation(soup: BeautifulSoup) -> str:
    return html_to_markdown(soup.select_one("div.content-meta"))


def get_credits(soup: BeautifulSoup) -> str:
    for detail in soup.select("div.content-details details"):
        heading = detail.select_one("summary h3")
        if heading and heading.get_text(" ", strip=True).lower() == "credits":
            return html_to_markdown(detail.select_one("div.well--data"))
    return ""


def get_source_sections(soup: BeautifulSoup) -> list[SourceSection]:
    """Extract distinct source-text sections in their Drupal order."""
    sections: list[SourceSection] = []
    seen: set[str] = set()
    for detail in soup.select("div.content-details details"):
        summary = detail.select_one("summary h3")
        if summary is None:
            continue
        raw_label = summary.get_text(" ", strip=True)
        label = SECTION_LABEL_LOOKUP.get(raw_label.lower())
        if label is None or label in seen:
            continue
        well = detail.select_one("div.well--data")
        content = protect_source_text_markdown(html_to_markdown(well))
        if content:
            sections.append(SourceSection(label, content))
            seen.add(label)
    return sections


def format_section(section: SourceSection) -> str:
    return f"## {section.label}\n\n{section.content.strip()}\n"


def merge_source_sections(
    markdown: str,
    remote_sections: list[SourceSection],
) -> str:
    """Merge Drupal sections into a Hugo source without duplicating labels."""
    remote_by_label = {section.label: section for section in remote_sections}
    merged_labels: set[str] = set()

    def replace_existing(match: re.Match[str]) -> str:
        label = SECTION_LABEL_LOOKUP[match.group(1).lower()]
        remote = remote_by_label.get(label)
        if remote is None:
            return match.group(0)
        merged_labels.add(label)
        return format_section(remote) + "\n"

    updated = SOURCE_SECTION_RE.sub(replace_existing, markdown)
    missing = [
        section for section in remote_sections if section.label not in merged_labels
    ]
    if missing:
        updated = updated.rstrip() + "\n\n"
        updated += "\n\n".join(format_section(section).rstrip() for section in missing)
    return updated.rstrip() + "\n"


def merge_annotation(markdown: str, annotation: str) -> str:
    """Replace only the body content preceding the first level-two section."""
    match = FRONT_MATTER_RE.match(markdown)
    if match is None:
        raise ValueError("Source Markdown is missing YAML front matter")
    front_matter, body = match.groups()
    first_section = re.search(r"(?m)^##[ \t]+", body)
    suffix = body[first_section.start():].strip() if first_section else ""
    pieces = [front_matter.rstrip(), annotation.strip()]
    if suffix:
        pieces.append(suffix)
    return "\n\n".join(pieces).rstrip() + "\n"


def merge_front_matter_field(markdown: str, field_name: str, value: str) -> str:
    """Replace one scalar front-matter field without parsing unrelated YAML."""
    match = FRONT_MATTER_RE.match(markdown)
    if match is None:
        raise ValueError("Source Markdown is missing YAML front matter")
    front_matter, body = match.groups()
    lines = front_matter.rstrip().splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith(f"{field_name}:")
        ),
        None,
    )
    if start is None:
        raise ValueError(f"Source front matter is missing {field_name}")
    end = start + 1
    while end < len(lines) and (
        lines[end].startswith((" ", "\t")) or not lines[end].strip()
    ):
        end += 1
    replacement = (
        [f"{field_name}: |"]
        + [f"  {line}" if line else "" for line in value.strip().splitlines()]
        if value.strip()
        else [f'{field_name}: ""']
    )
    lines[start:end] = replacement
    return "\n".join(lines) + "\n" + body


def front_matter_url(markdown: str) -> str:
    match = re.search(r"^url:[ \t]*(.+)$", markdown, re.MULTILINE)
    return normalize_path(match.group(1).strip().strip("\"'")) if match else ""


def source_files_by_path(content_dir: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for filepath in sorted(content_dir.glob("*.md")):
        if filepath.name == "_index.md":
            continue
        path = front_matter_url(filepath.read_text(encoding="utf-8"))
        if path:
            files[path] = filepath
    return files


def report_paths(report_path: Path, fields: set[str]) -> set[str]:
    """Select source pages with missing or differing source-text sections."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    selected: set[str] = set()
    for page in report.get("pages", []):
        if page.get("kind") != "source":
            continue
        for finding in page.get("findings", []):
            field = finding.get("field", "")
            if (
                "source_sections" in fields
                and (field == "section_names" or field in {
                "sections.Text",
                "sections.Transcription",
                "sections.Translation",
                })
            ) or (
                "annotation" in fields and field == "annotation"
            ) or (
                "source_citation" in fields and field == "source_citation"
            ) or (
                "credits" in fields and field == "sections.Credits"
            ):
                selected.add(normalize_path(page["path"]))
                break
    return selected


def update_markdown(
    filepath: Path,
    remote_sections: list[SourceSection],
    *,
    annotation: str | None = None,
    metadata: dict[str, str] | None = None,
    dry_run: bool = False,
) -> bool:
    content = filepath.read_text(encoding="utf-8")
    updated = merge_source_sections(content, remote_sections)
    if annotation is not None:
        updated = merge_annotation(updated, annotation)
    for field_name, value in (metadata or {}).items():
        updated = merge_front_matter_field(updated, field_name, value)
    if updated == content:
        return False
    if not dry_run:
        filepath.write_text(updated, encoding="utf-8")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preserve Drupal Text, Transcription, and Translation sections."
    )
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--content-dir", type=Path, default=CONTENT_DIR)
    parser.add_argument(
        "--report",
        type=Path,
        help="Only check source-section discrepancies in a parity JSON report.",
    )
    parser.add_argument(
        "--field",
        action="append",
        choices=("source_sections", "annotation", "source_citation", "credits"),
        help="Content to synchronize (repeatable; defaults to source_sections).",
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="Only update this source URL/path (repeatable).",
    )
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fields = set(args.field or ["source_sections"])
    files = source_files_by_path(args.content_dir)

    selected = set(files)
    if args.report:
        selected &= report_paths(args.report, fields)
    if args.url:
        selected &= {normalize_path(value) for value in args.url}

    missing_local = sorted(
        ({normalize_path(value) for value in args.url} if args.url else set())
        - set(files)
    )
    for path in missing_local:
        print(f"ERROR no local source file for {path}")

    candidates = [(path, files[path]) for path in sorted(selected)]
    print(f"Checking {len(candidates)} source page(s)...")

    updated_count = 0
    error_count = len(missing_local)
    section_counts = {label: 0 for label in SECTION_LABELS}
    for index, (path, filepath) in enumerate(candidates, start=1):
        try:
            soup = fetch(
                f"{args.base_url.rstrip('/')}{path}",
                args.delay if index > 1 else 0,
            )
        except requests.RequestException as exc:
            error_count += 1
            print(f"ERROR {path}: {exc}")
            continue

        sections = (
            get_source_sections(soup) if "source_sections" in fields else []
        )
        annotation = get_annotation(soup) if "annotation" in fields else None
        metadata = {}
        if "source_citation" in fields:
            metadata["source_citation"] = get_source_citation(soup)
        if "credits" in fields:
            metadata["credits"] = get_credits(soup)
        changed = update_markdown(
            filepath,
            sections,
            annotation=annotation,
            metadata=metadata,
            dry_run=args.dry_run,
        )
        if changed:
            updated_count += 1
            for section in sections:
                section_counts[section.label] += 1
            action = "Would update" if args.dry_run else "Updated"
            labels = ", ".join(section.label for section in sections) or "none"
            print(f"[{index}/{len(candidates)}] {action} {path}: {labels}")

    print("\nSource section migration summary")
    print(f"  Checked:       {len(candidates)}")
    print(f"  Updated:       {updated_count}")
    print(f"  Text:          {section_counts['Text']}")
    print(f"  Transcription: {section_counts['Transcription']}")
    print(f"  Translation:   {section_counts['Translation']}")
    print(f"  Errors:        {error_count}")
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
