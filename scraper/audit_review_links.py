"""
Audit external links in Website Review front matter and Markdown bodies.

The audit is deliberately conservative: redirects and access restrictions are
reported separately, while only repeated 404/410 responses are classified as
dead links.

Usage:
    cd scraper
    uv run python audit_review_links.py
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTENT_DIR = PROJECT_ROOT / "content" / "reviews"
DEFAULT_REPORT = PROJECT_ROOT / "review_link_audit.csv"
DEFAULT_CACHE = PROJECT_ROOT / "review_link_audit_cache.json"

REVIEWED_URL_RE = re.compile(
    r'^reviewed_url:\s*(?:"([^"]*)"|\'([^\']*)\'|(.+?))\s*$',
    re.MULTILINE,
)
MARKDOWN_LINK_START_RE = re.compile(r"(?<!!)\[[^\]]*]\((https?://)")
HTML_LINK_RE = re.compile(r"""<a\b[^>]*\bhref=["'](https?://[^"']+)["']""", re.I)


@dataclass(frozen=True)
class LinkReference:
    source_file: str
    context: str
    url: str


@dataclass
class LinkResult:
    url: str
    classification: str
    status_code: int | None = None
    final_url: str = ""
    detail: str = ""
    checked_at: str = ""
    attempts: int = 0


class HostRateLimiter:
    def __init__(self, delay: float):
        self.delay = max(0.0, delay)
        self.last_request: dict[str, float] = {}
        self.lock = threading.Lock()

    def wait(self, url: str) -> None:
        host = urlparse(url).netloc.lower()
        with self.lock:
            now = time.monotonic()
            scheduled = max(now, self.last_request.get(host, 0.0) + self.delay)
            self.last_request[host] = scheduled
        if scheduled > now:
            time.sleep(scheduled - now)


def split_front_matter(markdown: str) -> tuple[str, str]:
    if not markdown.startswith("---"):
        return "", markdown
    parts = markdown.split("---", 2)
    if len(parts) != 3:
        return "", markdown
    return parts[1], parts[2]


def decode_url_entities(url: str) -> str:
    """Decode encoded ampersands without treating URL text as named HTML entities."""
    return (
        url.replace("&amp;", "&")
        .replace("&#38;", "&")
        .replace("&#x26;", "&")
        .replace("&#X26;", "&")
    )


def extract_markdown_urls(markdown: str) -> list[str]:
    """Extract Markdown destinations while preserving balanced URL parentheses."""
    urls: list[str] = []
    for match in MARKDOWN_LINK_START_RE.finditer(markdown):
        start = match.start(1)
        depth = 0
        escaped = False
        for index in range(start, len(markdown)):
            character = markdown[index]
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
            elif character == "(":
                depth += 1
            elif character == ")":
                if depth == 0:
                    urls.append(markdown[start:index])
                    break
                depth -= 1
            elif character.isspace():
                break
    return urls


def extract_reviewed_url(front_matter: str) -> str:
    match = REVIEWED_URL_RE.search(front_matter)
    if not match:
        return ""
    value = next((group for group in match.groups() if group is not None), "")
    return decode_url_entities(value.strip())


def extract_link_references(content_dir: Path) -> list[LinkReference]:
    references: set[LinkReference] = set()
    for path in sorted(content_dir.glob("*.md")):
        if path.name == "_index.md":
            continue
        front_matter, body = split_front_matter(path.read_text())
        reviewed_url = extract_reviewed_url(front_matter)
        if reviewed_url.startswith(("http://", "https://")):
            references.add(LinkReference(path.name, "reviewed_url", reviewed_url))

        body_urls = extract_markdown_urls(body)
        body_urls.extend(HTML_LINK_RE.findall(body))
        for url in body_urls:
            references.add(
                LinkReference(path.name, "body", decode_url_entities(url.strip()))
            )
    return sorted(
        references,
        key=lambda ref: (ref.url, ref.source_file, ref.context),
    )


def classify_response(response: requests.Response) -> str:
    status = response.status_code
    if 200 <= status < 300:
        return "redirect" if response.history else "ok"
    if status == 402:
        return "paywall"
    if status in {401, 403, 407, 451}:
        return "access_restricted"
    if status in {404, 410}:
        return "dead"
    if status in {408, 425, 429} or 500 <= status < 600:
        return "transient_failure"
    if 300 <= status < 400:
        return "redirect_error"
    if 400 <= status < 500:
        return "client_error"
    return "unexpected_status"


def check_url(
    url: str,
    session: requests.Session,
    limiter: HostRateLimiter,
    timeout: float,
    retries: int,
) -> LinkResult:
    attempts = max(1, retries + 1)
    last_result: LinkResult | None = None
    for attempt in range(1, attempts + 1):
        limiter.wait(url)
        checked_at = datetime.now(UTC).isoformat()
        try:
            with session.get(
                url,
                allow_redirects=True,
                stream=True,
                timeout=timeout,
            ) as response:
                classification = classify_response(response)
                last_result = LinkResult(
                    url=url,
                    classification=classification,
                    status_code=response.status_code,
                    final_url=response.url,
                    checked_at=checked_at,
                    attempts=attempt,
                )
        except requests.exceptions.SSLError as error:
            last_result = LinkResult(
                url=url,
                classification="tls_error",
                detail=str(error),
                checked_at=checked_at,
                attempts=attempt,
            )
        except requests.exceptions.TooManyRedirects as error:
            last_result = LinkResult(
                url=url,
                classification="redirect_error",
                detail=str(error),
                checked_at=checked_at,
                attempts=attempt,
            )
        except requests.RequestException as error:
            last_result = LinkResult(
                url=url,
                classification="transient_failure",
                detail=str(error),
                checked_at=checked_at,
                attempts=attempt,
            )

        if last_result.classification not in {"dead", "transient_failure"}:
            return last_result
        if attempt < attempts:
            time.sleep(min(2 ** (attempt - 1), 4))

    assert last_result is not None
    return last_result


def load_cache(path: Path, max_age_hours: float) -> dict[str, LinkResult]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
    cached: dict[str, LinkResult] = {}
    for url, data in raw.items():
        try:
            checked_at = datetime.fromisoformat(data["checked_at"])
            if checked_at >= cutoff:
                cached[url] = LinkResult(**data)
        except (KeyError, TypeError, ValueError):
            continue
    return cached


def save_cache(path: Path, results: dict[str, LinkResult]) -> None:
    data = {url: asdict(result) for url, result in sorted(results.items())}
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_report(
    path: Path,
    references: list[LinkReference],
    results: dict[str, LinkResult],
) -> None:
    fieldnames = [
        "source_file",
        "context",
        "url",
        "classification",
        "status_code",
        "final_url",
        "attempts",
        "checked_at",
        "detail",
    ]
    with path.open("w", newline="") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=fieldnames)
        writer.writeheader()
        for reference in references:
            result = results[reference.url]
            writer.writerow(
                {
                    "source_file": reference.source_file,
                    "context": reference.context,
                    **asdict(result),
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-dir", type=Path, default=DEFAULT_CONTENT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--cache-max-age", type=float, default=168)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--fail-on-dead", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    references = extract_link_references(args.content_dir)
    urls = sorted({reference.url for reference in references})
    if args.limit:
        urls = urls[: args.limit]
        references = [reference for reference in references if reference.url in urls]

    cache = {} if args.refresh else load_cache(args.cache, args.cache_max_age)
    limiter = HostRateLimiter(args.delay)
    results: dict[str, LinkResult] = {}
    thread_state = threading.local()

    def session_for_thread() -> requests.Session:
        if not hasattr(thread_state, "session"):
            thread_state.session = requests.Session()
            thread_state.session.headers.update(
                {
                    "User-Agent": (
                        "WHC-Hugo-Link-Audit/1.0 "
                        "(RRCHNM; https://worldhistorycommons.org/)"
                    )
                }
            )
        return thread_state.session

    def audit_url(url: str) -> tuple[LinkResult, str]:
        if url in cache:
            return cache[url], "cache"
        result = check_url(
            url,
            session_for_thread(),
            limiter,
            args.timeout,
            args.retries,
        )
        return result, "live"

    print(f"Checking {len(urls)} unique URLs from {len(references)} references...")
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(audit_url, url): url for url in urls}
        for index, future in enumerate(as_completed(futures), start=1):
            url = futures[future]
            result, source = future.result()
            if source == "live":
                cache[url] = result
            results[url] = result
            status = result.status_code if result.status_code is not None else "-"
            print(
                f"[{index:>3}/{len(urls)}] {result.classification:<18} "
                f"{status!s:<3} {source:<5} {url}"
            )
            if index % 50 == 0:
                save_cache(args.cache, cache)

    save_cache(args.cache, cache)
    write_report(args.output, references, results)

    counts: dict[str, int] = {}
    for result in results.values():
        counts[result.classification] = counts.get(result.classification, 0) + 1
    print("\nClassification summary:")
    for classification, count in sorted(counts.items()):
        print(f"  {classification:<18} {count}")
    print(f"\nReport: {args.output}")
    print(f"Cache:  {args.cache}")

    if args.fail_on_dead and counts.get("dead", 0):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
