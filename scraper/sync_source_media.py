"""
Synchronize source image metadata and downloadable audio from Drupal.

By default, only pages with source-media findings in the parity audit are
requested. Pass --all to inspect every local source page.

Usage:
    cd scraper
    uv run python sync_source_media.py
    uv run python sync_source_media.py --all
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://worldhistorycommons.org"
ROOT_DIR = Path(__file__).parent.parent
CONTENT_DIR = ROOT_DIR / "content" / "sources"
STATIC_DIR = ROOT_DIR / "static"
DEFAULT_AUDIT = ROOT_DIR / "utils" / "content_parity.json"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "WHC-Hugo-Migration/1.0 (RRCHNM; content migration)"
})

MEDIA_FIELDS = {"image_alt", "additional_images", "audio_files"}


def yaml_string(value: str) -> str:
    """Return a JSON string, which is also a valid YAML quoted scalar."""
    return json.dumps(value, ensure_ascii=False)


def split_front_matter(text: str) -> tuple[list[str], str]:
    if not text.startswith("---\n"):
        raise ValueError("Markdown file has no YAML front matter")
    front_matter, body = text[4:].split("\n---\n", 1)
    return front_matter.splitlines(), body


def scalar_value(lines: list[str], field: str) -> str:
    prefix = f"{field}:"
    for line in lines:
        if line.startswith(prefix):
            value = line[len(prefix):].strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                return json.loads(value)
            return value
    return ""


def replace_media_fields(
    text: str,
    *,
    image: str,
    image_alt: str,
    additional_images: list[dict[str, str]],
    audio_files: list[dict[str, str]],
    media_unavailable: dict[str, str] | None = None,
) -> str:
    """Replace only media fields while preserving all other front matter."""
    lines, body = split_front_matter(text)
    cleaned = []
    skipping = False
    for line in lines:
        top_level = bool(line) and not line[0].isspace()
        if top_level:
            field = line.split(":", 1)[0]
            skipping = field in MEDIA_FIELDS
        if not skipping:
            cleaned.append(line)

    image_index = next(
        (index for index, line in enumerate(cleaned) if line.startswith("image:")),
        len(cleaned),
    )
    if image_index == len(cleaned) and image:
        cleaned.append(f"image: {image}")
    elif image:
        cleaned[image_index] = f"image: {image}"

    insert_at = min(image_index + 1, len(cleaned))
    media_lines = []
    if image_alt:
        media_lines.append(f"image_alt: {yaml_string(image_alt)}")
    if additional_images:
        media_lines.append("additional_images:")
        for item in additional_images:
            media_lines.extend([
                f"  - src: {yaml_string(item['src'])}",
                f"    alt: {yaml_string(item.get('alt', ''))}",
            ])
    if audio_files:
        media_lines.append("audio_files:")
        for item in audio_files:
            media_lines.extend([
                f"  - src: {yaml_string(item['src'])}",
                f"    label: {yaml_string(item.get('label', 'Download audio'))}",
            ])
    if (
        media_unavailable
        and not any(line.startswith("media_unavailable:") for line in cleaned)
    ):
        media_lines.extend([
            "media_unavailable:",
            f"  type: {media_unavailable['type']}",
            f"  message: {yaml_string(media_unavailable['message'])}",
        ])
    cleaned[insert_at:insert_at] = media_lines
    return "---\n" + "\n".join(cleaned) + "\n---\n" + body


def audit_paths(audit_path: Path) -> list[str]:
    data = json.loads(audit_path.read_text())
    fields = {"main_images", "main_image_alt", "audio_links", "youtube_ids"}
    return sorted({
        page["path"]
        for page in data["pages"]
        if page.get("kind") == "source"
        and any(
            (
                finding.get("classification") == "migration_loss"
                and finding.get("field") in fields
            )
            or (
                finding.get("classification") == "upstream_gap"
                and finding.get("field") == "media"
            )
            for finding in page.get("findings", [])
        )
    })


def local_sources() -> dict[str, Path]:
    sources = {}
    for path in CONTENT_DIR.glob("*.md"):
        if path.name == "_index.md":
            continue
        lines, _ = split_front_matter(path.read_text())
        url = scalar_value(lines, "url")
        if url:
            sources[url] = path
    return sources


def safe_filename(url: str) -> str:
    filename = unquote(Path(urlparse(url).path).name)
    return re.sub(r"[^\w.\-]", "_", filename) or "media"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    response = SESSION.get(urljoin(BASE_URL, url), timeout=45)
    response.raise_for_status()
    destination.write_bytes(response.content)


def image_items(
    soup: BeautifulSoup,
    node_id: str,
    current_image: str,
) -> list[dict[str, str]]:
    images = []
    for index, image in enumerate(soup.select("div.two-cols div.image-wrap img")):
        source = image.get("src", "")
        if not source:
            continue
        if index == 0 and current_image:
            local_path = current_image
        else:
            filename = safe_filename(source)
            relative = Path("source-media") / node_id / filename
            download(source, STATIC_DIR / "images" / relative)
            local_path = "/images/" + relative.as_posix()
        images.append({"src": local_path, "alt": image.get("alt", "").strip()})
    return images


def audio_items(soup: BeautifulSoup, node_id: str) -> tuple[list[dict[str, str]], bool]:
    urls = [
        item.get("src", "")
        for item in soup.select("div.audio-wrap audio source[src], div.audio-wrap audio[src]")
    ]
    urls.extend(
        item.get("href", "")
        for item in soup.select("div.audio-wrap a[href]")
    )
    seen = set()
    items = []
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        filename = safe_filename(url)
        relative = Path("source-media") / node_id / filename
        download(url, STATIC_DIR / "audio" / relative)
        items.append({
            "src": "/audio/" + relative.as_posix(),
            "label": "Download audio",
        })
    has_empty_control = bool(
        soup.select_one("div.audio-wrap a")
        and not soup.select_one("div.audio-wrap a[href]:not([href=''])")
    )
    return items, has_empty_control


def sync_path(url_path: str, markdown_path: Path) -> tuple[bool, bool]:
    response = SESSION.get(urljoin(BASE_URL, url_path), timeout=45)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    original = markdown_path.read_text()
    lines, _ = split_front_matter(original)
    current_image = scalar_value(lines, "image")
    node_id = scalar_value(lines, "drupal_node_id") or markdown_path.stem
    source_type = scalar_value(lines, "source_type").lower()
    images = image_items(soup, node_id, current_image)
    audio_files, empty_audio = audio_items(soup, node_id)
    has_youtube = bool(soup.select_one("iframe[src*='youtube.com/embed']"))
    media_unavailable = None
    if (
        source_type in {"audio", "image", "video"}
        and not images
        and not audio_files
        and not has_youtube
    ):
        media_unavailable = {
            "type": source_type,
            "message": (
                f"The original site does not provide {source_type} media "
                "for this source."
            ),
        }

    updated = replace_media_fields(
        original,
        image=images[0]["src"] if images else current_image,
        image_alt=images[0]["alt"] if images else "",
        additional_images=images[1:],
        audio_files=audio_files,
        media_unavailable=media_unavailable,
    )
    changed = updated != original
    if changed:
        markdown_path.write_text(updated)
    return changed, empty_audio


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="inspect all source pages")
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--delay", type=float, default=0.1)
    args = parser.parse_args()

    sources = local_sources()
    paths = sorted(sources) if args.all else audit_paths(args.audit)
    missing_local = [path for path in paths if path not in sources]
    if missing_local:
        raise SystemExit(f"No local source file for: {', '.join(missing_local)}")

    changed = 0
    errors = []
    empty_audio = []
    for index, url_path in enumerate(paths, 1):
        print(f"[{index}/{len(paths)}] {url_path}")
        try:
            did_change, has_empty_audio = sync_path(url_path, sources[url_path])
            changed += int(did_change)
            if has_empty_audio:
                empty_audio.append(url_path)
        except Exception as error:
            errors.append((url_path, str(error)))
            print(f"  ERROR: {error}")
        time.sleep(args.delay)

    print(f"\nUpdated {changed} of {len(paths)} source files")
    if empty_audio:
        print("Drupal audio controls without a media URL:")
        for path in empty_audio:
            print(f"  {path}")
    if errors:
        print("Errors:")
        for path, error in errors:
            print(f"  {path}: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
