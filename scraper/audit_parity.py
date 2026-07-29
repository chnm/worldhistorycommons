"""
Compare rendered pages on the live Drupal site with a local Hugo build.

The audit is intentionally read-only. It compares semantic page components
rather than raw HTML so that template markup differences do not obscure lost
content.

Examples:
    hugo
    cd scraper
    uv run python audit_parity.py --limit 10
    uv run python audit_parity.py \
        --input-csv "../WHC Review - Category Review.csv"
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTENT_DIR = PROJECT_ROOT / "content"
DEFAULT_PUBLIC_DIR = PROJECT_ROOT / "public"
DEFAULT_JSON_REPORT = PROJECT_ROOT / "utils" / "content_parity.json"
DEFAULT_CSV_REPORT = PROJECT_ROOT / "utils" / "content_parity.csv"
DEFAULT_BASE_URL = "https://worldhistorycommons.org"
USER_AGENT = "WHC-Hugo-Migration/1.0 (RRCHNM; semantic parity audit)"

SECTION_KIND = {
    "sources": "source",
    "teaching": "teaching",
    "methods": "methods",
    "reviews": "review",
}
CSV_CATEGORY_KIND = {
    "sources": "source",
    "source": "source",
    "teaching": "teaching",
    "methods": "methods",
    "method": "methods",
    "review": "review",
    "reviews": "review",
}
SECTION_LABEL_KIND = {
    "primary source": "source",
    "teaching": "teaching",
    "methods": "methods",
    "website review": "review",
}
SOURCE_TEXT_SECTIONS = {"text", "transcription", "translation"}


@dataclass(frozen=True)
class Target:
    path: str
    kind: str
    source_type: str = ""
    notes: str = ""


@dataclass
class Snapshot:
    path: str
    kind: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    annotation: str = ""
    overview: str = ""
    body: str = ""
    source_citation: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    tags: dict[str, list[str]] = field(default_factory=dict)
    main_images: list[str] = field(default_factory=list)
    related_links: list[str] = field(default_factory=list)
    related_image_count: int = 0
    related_image_alts: list[str] = field(default_factory=list)
    youtube_ids: list[str] = field(default_factory=list)
    replaced_youtube_ids: list[str] = field(default_factory=list)
    unavailable_youtube_ids: list[str] = field(default_factory=list)
    audio_links: list[str] = field(default_factory=list)
    reviewed_url: str = ""
    reviewer: str = ""
    pull_quote: str = ""
    how_to_cite: str = ""


@dataclass
class Finding:
    classification: str
    field: str
    detail: str
    drupal: object = ""
    hugo: object = ""


def normalize_path(value: str) -> str:
    path = urlparse(value).path.rstrip("/")
    return path or "/"


def normalize_space(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.translate(
        str.maketrans(
            {
                "\u2018": "'",
                "\u2019": "'",
                "\u201c": '"',
                "\u201d": '"',
                "\u2013": "-",
                "\u2014": "-",
                "\u2026": "...",
            }
        )
    )
    value = normalize_space(value)
    value = re.sub(
        r"\[accessed [^\]]+\]",
        "[accessed DATE]",
        value,
        flags=re.IGNORECASE,
    )
    return value


BLOCK_ELEMENTS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "dd",
    "details",
    "div",
    "dl",
    "dt",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "section",
    "summary",
    "table",
    "td",
    "th",
    "tr",
    "ul",
}


def list_marker(element: Tag) -> str:
    """Return the visible marker browsers generate for a list item."""
    parent = element.parent
    if not isinstance(parent, Tag):
        return ""
    if parent.name == "ul":
        return "- "
    if parent.name != "ol":
        return ""

    siblings = [
        child
        for child in parent.children
        if isinstance(child, Tag) and child.name == "li"
    ]
    try:
        position = siblings.index(element)
    except ValueError:  # pragma: no cover - defensive DOM handling
        position = 0
    try:
        start = int(parent.get("start", 1))
    except (TypeError, ValueError):
        start = 1
    try:
        value = int(element.get("value", start + position))
    except (TypeError, ValueError):
        value = start + position
    return f"{value}. "


def semantic_fragments(node: Tag | NavigableString) -> list[str]:
    """Extract visible text without adding spaces around inline elements."""
    if isinstance(node, NavigableString):
        return [str(node)]
    if node.name in {"script", "style", "template"}:
        return []
    if node.name == "br":
        # html.parser can incorrectly nest following text beneath legacy
        # self-closing <br /> tags. Browsers treat br as void but still render
        # that following text, so preserve any parser-created children.
        fragments = [" "]
        for child in node.children:
            if isinstance(child, (Tag, NavigableString)):
                fragments.extend(semantic_fragments(child))
        return fragments
    if node.name == "hr":
        return [" "]

    block = node.name in BLOCK_ELEMENTS
    fragments = [" "] if block else []
    if node.name == "li":
        fragments.append(list_marker(node))
    for child in node.children:
        if isinstance(child, (Tag, NavigableString)):
            fragments.extend(semantic_fragments(child))
    if block:
        fragments.append(" ")
    return fragments


def element_text(element: Tag | None) -> str:
    if element is None:
        return ""
    return normalize_text("".join(semantic_fragments(element)))


def normalize_url(value: str, *, base_url: str = DEFAULT_BASE_URL) -> str:
    if not value:
        return ""
    absolute = urljoin(base_url, value.strip())
    parsed = urlparse(absolute)
    path = parsed.path.rstrip("/") or "/"
    if parsed.netloc == urlparse(base_url).netloc:
        return path
    return parsed._replace(path=path, fragment="").geturl()


def media_identity(value: str) -> str:
    """Return a stable, human-readable identity for a media URL."""
    if not value:
        return ""
    decoded = value
    for _ in range(3):
        decoded = unquote(decoded)
    parsed = urlparse(decoded)
    return Path(parsed.path).name or parsed.path


def youtube_id(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value)
    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/")
    if "youtube" in parsed.netloc:
        if "/embed/" in parsed.path:
            return parsed.path.split("/embed/", 1)[1].split("/", 1)[0]
        query_match = re.search(r"(?:^|&)v=([^&]+)", parsed.query)
        if query_match:
            return query_match.group(1)
    return ""


def section_map(soup: BeautifulSoup) -> dict[str, str]:
    sections: dict[str, str] = {}
    for detail in soup.select("div.content-details details"):
        heading = element_text(detail.select_one("summary h3"))
        if not heading:
            continue
        content = detail.select_one("div.well--data")
        value = element_text(content)
        if heading in sections and value:
            sections[heading] = normalize_text(f"{sections[heading]} {value}")
        else:
            sections[heading] = value
    return sections


def tag_map(soup: BeautifulSoup) -> dict[str, list[str]]:
    tags = {"regions": [], "subjects": [], "time_periods": []}
    for link in soup.select("div.tags a[href]"):
        href = link.get("href", "")
        name = element_text(link)
        if "/region/" in href or "/regions/" in href:
            tags["regions"].append(name)
        elif "/subject/" in href or "/subjects/" in href:
            tags["subjects"].append(name)
        elif "/time-period/" in href or "/time_periods/" in href:
            tags["time_periods"].append(name)
    return {key: sorted(set(values)) for key, values in tags.items()}


def content_kind(soup: BeautifulSoup, fallback: str = "") -> str:
    label = element_text(soup.select_one(".content-header--label")).lower()
    return SECTION_LABEL_KIND.get(label, fallback)


def header_authors(soup: BeautifulSoup) -> list[str]:
    container = soup.select_one(".content-header--author")
    if container is None:
        return []
    direct = [
        element_text(child)
        for child in container.find_all("div", recursive=False)
        if element_text(child)
    ]
    return direct or ([element_text(container)] if element_text(container) else [])


def source_snapshot(soup: BeautifulSoup, path: str) -> Snapshot:
    snapshot = Snapshot(
        path=path,
        kind="source",
        title=element_text(soup.select_one(".content-header h1") or soup.select_one("h1")),
        tags=tag_map(soup),
        sections=section_map(soup),
    )

    for box in soup.select("div.box-border"):
        if element_text(box.select_one("h2.box-border--title")).lower() == "annotation":
            heading = box.select_one("h2.box-border--title")
            snapshot.annotation = element_text(heading.find_next_sibling("div") if heading else None)
            break

    snapshot.source_citation = element_text(soup.select_one("div.content-meta"))
    snapshot.main_images = [
        element_text(image) or image.get("alt", "").strip()
        for image in soup.select("div.two-cols div.image-wrap img")
    ]

    for frame in soup.select("iframe[src]"):
        video_id = youtube_id(frame.get("src", ""))
        if video_id:
            snapshot.youtube_ids.append(video_id)
    for media in soup.select("[data-replaces-youtube-id]"):
        video_id = media.get("data-replaces-youtube-id", "").strip()
        if video_id:
            snapshot.replaced_youtube_ids.append(video_id)
    for link in soup.select(".source-media-unavailable a[href]"):
        video_id = youtube_id(link.get("href", ""))
        if video_id:
            snapshot.unavailable_youtube_ids.append(video_id)
    for link in soup.select("a[href]"):
        href = link.get("href", "")
        if href and (
            re.search(r"\.(?:mp3|m4a|ogg|wav)(?:$|\?)", href, re.IGNORECASE)
            or "download audio" in element_text(link).lower()
        ):
            snapshot.audio_links.append(media_identity(href))
    for audio in soup.select("audio"):
        source = audio.get("src", "")
        if not source:
            nested = audio.select_one("source[src]")
            source = nested.get("src", "") if nested else ""
        snapshot.audio_links.append(media_identity(source) or "embedded audio")

    snapshot.youtube_ids = sorted(set(filter(None, snapshot.youtube_ids)))
    snapshot.replaced_youtube_ids = sorted(
        set(filter(None, snapshot.replaced_youtube_ids))
    )
    snapshot.unavailable_youtube_ids = sorted(
        set(filter(None, snapshot.unavailable_youtube_ids))
    )
    snapshot.audio_links = sorted(set(filter(None, snapshot.audio_links)))
    snapshot.how_to_cite = citation_text(soup)
    return snapshot


def teaching_snapshot(soup: BeautifulSoup, path: str, kind: str) -> Snapshot:
    snapshot = Snapshot(
        path=path,
        kind=kind,
        title=element_text(soup.select_one(".content-header h1") or soup.select_one("h1")),
        authors=header_authors(soup),
        tags=tag_map(soup),
        sections=section_map(soup),
    )
    for box in soup.select("div.box-border"):
        if element_text(box.select_one("h2.box-border--title")).lower() == "overview":
            heading = box.select_one("h2.box-border--title")
            snapshot.overview = element_text(heading.find_next_sibling("div") if heading else None)
            break

    gallery = soup.select_one("div.two-cols div.box-tile")
    if gallery:
        snapshot.related_links = sorted(
            {
                normalize_url(link.get("href", ""))
                for link in gallery.select("a[href]")
                if link.get("href")
            }
        )
        related_images = gallery.select("img")
        snapshot.related_image_count = len(related_images)
        snapshot.related_image_alts = [
            normalize_text(image.get("alt", "")) for image in related_images
        ]
    snapshot.how_to_cite = citation_text(soup)
    return snapshot


def review_snapshot(soup: BeautifulSoup, path: str) -> Snapshot:
    header = soup.select_one("a.review-header") or soup.select_one(".review-header")
    credit_link = soup.select_one("div.credit div.link a[href]")
    header_url = header.get("href", "") if header else ""
    reviewed_url = credit_link.get("href", "") if credit_link else header_url

    return Snapshot(
        path=path,
        kind="review",
        title=element_text(
            soup.select_one("a.review-header h1")
            or soup.select_one(".review-header h1")
            or soup.select_one("h1")
        ),
        authors=header_authors(soup),
        body=element_text(soup.select_one("div.review-well")),
        tags=tag_map(soup),
        main_images=[
            element_text(image) or image.get("alt", "").strip()
            for image in soup.select("div.pull-quote--sidebar img")
        ],
        reviewed_url=normalize_url(reviewed_url),
        reviewer=element_text(soup.select_one("div.credit div.text")),
        pull_quote=element_text(soup.select_one("div.pull-quote--sidebar div.quote")),
        how_to_cite=citation_text(soup),
    )


def citation_text(soup: BeautifulSoup) -> str:
    candidates = soup.select("div.citation")
    for candidate in reversed(candidates):
        if candidate.select_one("div.credit"):
            continue
        value = element_text(candidate)
        if value:
            return value
    return ""


def parse_snapshot(html: str, path: str, expected_kind: str = "") -> Snapshot:
    soup = BeautifulSoup(html, "html.parser")
    kind = content_kind(soup, expected_kind)
    if kind == "source":
        return source_snapshot(soup, path)
    if kind in {"teaching", "methods"}:
        return teaching_snapshot(soup, path, kind)
    if kind == "review":
        return review_snapshot(soup, path)
    return Snapshot(
        path=path,
        kind=kind or expected_kind or "unknown",
        title=element_text(soup.select_one("h1")),
        body=element_text(soup.select_one("main")),
        tags=tag_map(soup),
    )


def front_matter_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", text, re.MULTILINE)
    return match.group(1).strip().strip("\"'") if match else ""


def discover_content_targets(
    content_dir: Path,
    sections: Iterable[str] | None = None,
) -> list[Target]:
    selected = list(sections or SECTION_KIND)
    targets: dict[str, Target] = {}
    for section in selected:
        kind = SECTION_KIND[section]
        for filepath in sorted((content_dir / section).glob("*.md")):
            if filepath.name == "_index.md":
                continue
            text = filepath.read_text(encoding="utf-8")
            path = normalize_path(front_matter_value(text, "url"))
            if path == "/" and not front_matter_value(text, "url"):
                continue
            targets[path] = Target(
                path=path,
                kind=kind,
                source_type=front_matter_value(text, "source_type").lower(),
            )
    return sorted(targets.values(), key=lambda target: target.path)


def discover_csv_targets(csv_path: Path, content_dir: Path) -> list[Target]:
    content_targets = {
        target.path: target for target in discover_content_targets(content_dir)
    }
    targets: dict[str, Target] = {}
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            raw_url = row.get("URL") or row.get("url") or ""
            if not raw_url:
                continue
            path = normalize_path(raw_url)
            category = (
                row.get("Content Category Name")
                or row.get("Category")
                or row.get("category")
                or ""
            ).strip().lower()
            local = content_targets.get(path)
            targets[path] = Target(
                path=path,
                kind=CSV_CATEGORY_KIND.get(category, local.kind if local else ""),
                source_type=local.source_type if local else "",
                notes=(row.get("Notes") or row.get("notes") or "").strip(),
            )
    return sorted(targets.values(), key=lambda target: target.path)


def local_html_path(public_dir: Path, path: str) -> Path:
    relative = path.strip("/")
    if not relative:
        return public_dir / "index.html"
    directory_index = public_dir / relative / "index.html"
    if directory_index.exists():
        return directory_index
    return public_dir / f"{relative}.html"


def add_scalar_finding(
    findings: list[Finding],
    field_name: str,
    drupal: str,
    hugo: str,
) -> None:
    drupal = normalize_text(drupal)
    hugo = normalize_text(hugo)
    if drupal == hugo:
        return
    if drupal and not hugo:
        classification = "migration_loss"
        detail = "Present in Drupal but absent from Hugo"
    elif hugo and not drupal:
        classification = "rendering_mismatch"
        detail = "Present in Hugo but absent from Drupal"
    else:
        classification = "rendering_mismatch"
        detail = "Drupal and Hugo values differ"
    findings.append(Finding(classification, field_name, detail, drupal, hugo))


def add_collection_findings(
    findings: list[Finding],
    field_name: str,
    drupal: Iterable[str],
    hugo: Iterable[str],
) -> None:
    drupal_counter = Counter(filter(None, drupal))
    hugo_counter = Counter(filter(None, hugo))
    missing = list((drupal_counter - hugo_counter).elements())
    extra = list((hugo_counter - drupal_counter).elements())
    if missing:
        findings.append(
            Finding(
                "migration_loss",
                field_name,
                "Items present in Drupal are absent from Hugo",
                sorted(missing),
                "",
            )
        )
    if extra:
        findings.append(
            Finding(
                "rendering_mismatch",
                field_name,
                "Items present in Hugo are absent from Drupal",
                "",
                sorted(extra),
            )
        )


def compare_snapshots(
    drupal: Snapshot,
    hugo: Snapshot,
    target: Target,
) -> list[Finding]:
    findings: list[Finding] = []
    add_scalar_finding(findings, "kind", drupal.kind, hugo.kind)
    add_scalar_finding(findings, "title", drupal.title, hugo.title)
    for tag_kind in ("regions", "subjects", "time_periods"):
        add_collection_findings(
            findings,
            f"tags.{tag_kind}",
            drupal.tags.get(tag_kind, []),
            hugo.tags.get(tag_kind, []),
        )

    if target.kind == "source":
        add_scalar_finding(findings, "annotation", drupal.annotation, hugo.annotation)
        add_scalar_finding(
            findings,
            "source_citation",
            drupal.source_citation,
            hugo.source_citation,
        )
        add_collection_findings(
            findings,
            "main_images",
            ["image"] * len(drupal.main_images),
            ["image"] * len(hugo.main_images),
        )
        if len(drupal.main_images) == len(hugo.main_images):
            add_collection_findings(
                findings,
                "main_image_alt",
                drupal.main_images,
                hugo.main_images,
            )
        remote_youtube = set(drupal.youtube_ids)
        replacement_ids = remote_youtube.intersection(hugo.replaced_youtube_ids)
        unavailable_ids = remote_youtube.intersection(
            hugo.unavailable_youtube_ids
        )
        remaining_remote = sorted(
            remote_youtube - replacement_ids - unavailable_ids
        )
        remaining_hugo = [] if replacement_ids else hugo.youtube_ids
        add_collection_findings(
            findings, "youtube_ids", remaining_remote, remaining_hugo
        )
        if replacement_ids:
            findings.append(
                Finding(
                    "editorial_improvement",
                    "youtube_ids",
                    "Unavailable Drupal video was replaced with a validated equivalent",
                    sorted(replacement_ids),
                    hugo.youtube_ids,
                )
            )
        if unavailable_ids:
            findings.append(
                Finding(
                    "upstream_gap",
                    "youtube_ids",
                    "Drupal video is unavailable and has no confirmed replacement",
                    sorted(unavailable_ids),
                    "",
                )
            )
        add_collection_findings(
            findings,
            "audio_links",
            ["audio"] * len(drupal.audio_links),
            ["audio"] * len(hugo.audio_links),
        )
    elif target.kind in {"teaching", "methods"}:
        add_collection_findings(findings, "authors", drupal.authors, hugo.authors)
        add_scalar_finding(findings, "overview", drupal.overview, hugo.overview)
        add_collection_findings(
            findings,
            "related_links",
            drupal.related_links,
            hugo.related_links,
        )
        add_collection_findings(
            findings,
            "related_images",
            ["image"] * drupal.related_image_count,
            ["image"] * hugo.related_image_count,
        )
        if drupal.related_image_count == hugo.related_image_count:
            add_collection_findings(
                findings,
                "related_image_alt",
                drupal.related_image_alts,
                hugo.related_image_alts,
            )
    elif target.kind == "review":
        add_collection_findings(findings, "authors", drupal.authors, hugo.authors)
        add_scalar_finding(findings, "body", drupal.body, hugo.body)
        if drupal.reviewed_url:
            add_scalar_finding(
                findings, "reviewed_url", drupal.reviewed_url, hugo.reviewed_url
            )
        add_scalar_finding(findings, "reviewer", drupal.reviewer, hugo.reviewer)
        add_scalar_finding(findings, "pull_quote", drupal.pull_quote, hugo.pull_quote)
        add_collection_findings(
            findings,
            "sidebar_image",
            ["image"] * len(drupal.main_images),
            ["image"] * len(hugo.main_images),
        )
        if len(drupal.main_images) == len(hugo.main_images):
            add_collection_findings(
                findings,
                "sidebar_image_alt",
                drupal.main_images,
                hugo.main_images,
            )

    drupal_sections = {normalize_space(key): value for key, value in drupal.sections.items()}
    hugo_sections = {normalize_space(key): value for key, value in hugo.sections.items()}
    drupal_populated_sections = {
        key: value for key, value in drupal_sections.items() if normalize_text(value)
    }
    hugo_populated_sections = {
        key: value for key, value in hugo_sections.items() if normalize_text(value)
    }
    add_collection_findings(
        findings,
        "section_names",
        drupal_populated_sections,
        hugo_populated_sections,
    )
    for section_name in sorted(
        drupal_populated_sections.keys() & hugo_populated_sections.keys()
    ):
        add_scalar_finding(
            findings,
            f"sections.{section_name}",
            drupal_populated_sections[section_name],
            hugo_populated_sections[section_name],
        )
    add_scalar_finding(
        findings, "how_to_cite", drupal.how_to_cite, hugo.how_to_cite
    )

    drupal_text_sections = {
        key.lower()
        for key in drupal_populated_sections
        if key.lower() in SOURCE_TEXT_SECTIONS
    }
    empty_drupal_source_sections = sorted(
        key
        for key, value in drupal_sections.items()
        if key.lower() in SOURCE_TEXT_SECTIONS and not normalize_text(value)
    )
    if target.kind == "source" and empty_drupal_source_sections:
        findings.append(
            Finding(
                "upstream_gap",
                "empty_source_sections",
                "Drupal renders source-section headings without content",
                empty_drupal_source_sections,
                "",
            )
        )
    if (
        target.kind == "source"
        and target.source_type == "text"
        and not drupal_text_sections
    ):
        findings.append(
            Finding(
                "upstream_gap",
                "source_text",
                "Text source has no Text, Transcription, or Translation section in Drupal",
                "",
                "",
            )
        )
    if (
        target.kind == "source"
        and target.source_type in {"image", "audio", "video"}
    ):
        has_remote_media = bool(
            drupal.main_images or drupal.youtube_ids or drupal.audio_links
        )
        if not has_remote_media:
            findings.append(
                Finding(
                    "upstream_gap",
                    "media",
                    f"{target.source_type.title()} source has no corresponding media in Drupal",
                    "",
                    "",
                )
            )
    if target.kind == "review" and not drupal.reviewed_url:
        findings.append(
            Finding(
                "upstream_gap",
                "reviewed_url",
                "Website Review has no target URL in Drupal",
                "",
                hugo.reviewed_url,
            )
        )
    return findings


def report_page(
    target: Target,
    base_url: str,
    public_dir: Path,
    session: requests.Session,
    timeout: float,
) -> dict:
    page = {
        "path": target.path,
        "kind": target.kind,
        "source_type": target.source_type,
        "notes": target.notes,
        "status": "checked",
        "findings": [],
    }
    local_path = local_html_path(public_dir, target.path)
    if not local_path.exists():
        page["status"] = "local_error"
        page["findings"] = [
            asdict(
                Finding(
                    "migration_loss",
                    "page",
                    f"Rendered Hugo page not found at {local_path}",
                    "page",
                    "",
                )
            )
        ]
        return page

    try:
        local_snapshot = parse_snapshot(
            local_path.read_text(encoding="utf-8"),
            target.path,
            target.kind,
        )
    except Exception as exc:  # pragma: no cover - defensive report path
        page["status"] = "local_error"
        page["error"] = str(exc)
        return page

    url = urljoin(base_url.rstrip("/") + "/", target.path.lstrip("/"))
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        page["status"] = "remote_error"
        page["error"] = str(exc)
        return page

    remote_snapshot = parse_snapshot(response.text, target.path, target.kind)
    page["findings"] = [
        asdict(finding)
        for finding in compare_snapshots(remote_snapshot, local_snapshot, target)
    ]
    return page


def report_summary(pages: list[dict]) -> dict:
    counts = Counter()
    for page in pages:
        if page.get("status") != "checked":
            counts[page.get("status", "error")] += 1
        for finding in page.get("findings", []):
            counts[finding["classification"]] += 1
    return {
        "pages": len(pages),
        "checked": sum(page.get("status") == "checked" for page in pages),
        "remote_errors": counts["remote_error"],
        "local_errors": counts["local_error"],
        "migration_losses": counts["migration_loss"],
        "rendering_mismatches": counts["rendering_mismatch"],
        "upstream_gaps": counts["upstream_gap"],
        "editorial_improvements": counts["editorial_improvement"],
    }


def write_json_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def csv_value(value: object) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value or "")


def write_csv_report(path: Path, pages: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "path",
        "kind",
        "status",
        "classification",
        "field",
        "detail",
        "drupal",
        "hugo",
        "review_notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for page in pages:
            findings = page.get("findings", [])
            if not findings:
                writer.writerow(
                    {
                        "path": page["path"],
                        "kind": page["kind"],
                        "status": page["status"],
                        "review_notes": page.get("notes", ""),
                    }
                )
                continue
            for finding in findings:
                writer.writerow(
                    {
                        "path": page["path"],
                        "kind": page["kind"],
                        "status": page["status"],
                        "classification": finding.get("classification", ""),
                        "field": finding.get("field", ""),
                        "detail": finding.get("detail", ""),
                        "drupal": csv_value(finding.get("drupal", "")),
                        "hugo": csv_value(finding.get("hugo", "")),
                        "review_notes": page.get("notes", ""),
                    }
                )


def load_resumed_pages(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        page["path"]: page
        for page in report.get("pages", [])
        if page.get("status") == "checked"
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare live Drupal pages with rendered Hugo pages."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--content-dir", type=Path, default=DEFAULT_CONTENT_DIR)
    parser.add_argument("--public-dir", type=Path, default=DEFAULT_PUBLIC_DIR)
    parser.add_argument("--input-csv", type=Path)
    parser.add_argument(
        "--section",
        action="append",
        choices=sorted(SECTION_KIND),
        help="Audit one or more content sections (repeatable).",
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="Audit a specific URL or path (repeatable).",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV_REPORT)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--fail-on-difference", action="store_true")
    return parser


def select_targets(args: argparse.Namespace) -> list[Target]:
    if args.input_csv:
        targets = discover_csv_targets(args.input_csv, args.content_dir)
    else:
        targets = discover_content_targets(args.content_dir, args.section)

    by_path = {target.path: target for target in targets}
    if args.url:
        requested: list[Target] = []
        for value in args.url:
            path = normalize_path(value)
            requested.append(by_path.get(path, Target(path, "")))
        targets = requested
    if args.limit is not None:
        targets = targets[: args.limit]
    return targets


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    targets = select_targets(args)
    if not targets:
        print("No audit targets found.", file=sys.stderr)
        return 2
    if not args.public_dir.exists():
        print(
            f"Rendered Hugo directory not found: {args.public_dir}. Run hugo first.",
            file=sys.stderr,
        )
        return 2

    resumed = load_resumed_pages(args.output_json) if args.resume else {}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    pages: list[dict] = []

    print(f"Auditing {len(targets)} page(s) against {args.base_url}")
    for index, target in enumerate(targets, start=1):
        if target.path in resumed:
            pages.append(resumed[target.path])
            print(f"[{index}/{len(targets)}] resume {target.path}")
            continue
        print(f"[{index}/{len(targets)}] {target.path}")
        page = report_page(
            target,
            args.base_url,
            args.public_dir,
            session,
            args.timeout,
        )
        pages.append(page)
        if index < len(targets) and args.delay > 0:
            time.sleep(args.delay)

    report = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": args.base_url,
        "summary": report_summary(pages),
        "pages": pages,
    }
    write_json_report(args.output_json, report)
    write_csv_report(args.output_csv, pages)

    summary = report["summary"]
    print("\nSemantic parity summary")
    print(f"  Pages:                 {summary['pages']}")
    print(f"  Checked:               {summary['checked']}")
    print(f"  Migration losses:      {summary['migration_losses']}")
    print(f"  Rendering mismatches:  {summary['rendering_mismatches']}")
    print(f"  Upstream gaps:         {summary['upstream_gaps']}")
    print(f"  Remote errors:         {summary['remote_errors']}")
    print(f"  Local errors:          {summary['local_errors']}")
    print(f"  JSON: {args.output_json}")
    print(f"  CSV:  {args.output_csv}")

    blocking = (
        summary["migration_losses"]
        + summary["rendering_mismatches"]
        + summary["remote_errors"]
        + summary["local_errors"]
    )
    return 1 if args.fail_on_difference and blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
