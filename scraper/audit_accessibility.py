"""Run repeatable static accessibility checks against rendered Hugo pages."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PUBLIC_DIR = PROJECT_ROOT / "public"
DEFAULT_JSON_REPORT = PROJECT_ROOT / "utils" / "accessibility_audit.json"
DEFAULT_CSV_REPORT = PROJECT_ROOT / "utils" / "accessibility_audit.csv"


@dataclass(frozen=True)
class Violation:
    rule: str
    detail: str
    element: str = ""


def element_excerpt(element: Tag) -> str:
    return " ".join(str(element).split())[:240]


def accessible_name(element: Tag, soup: BeautifulSoup) -> str:
    if label := element.get("aria-label", "").strip():
        return label
    labelled_by = element.get("aria-labelledby", "").split()
    if labelled_by:
        labels = [
            target.get_text(" ", strip=True)
            for item_id in labelled_by
            if (target := soup.find(id=item_id))
        ]
        if any(labels):
            return " ".join(labels)
    if element.name == "input" and element.get("value"):
        return element.get("value", "").strip()
    text = element.get_text(" ", strip=True)
    if text:
        return text
    return " ".join(
        image.get("alt", "").strip()
        for image in element.select("img[alt]")
        if image.get("alt", "").strip()
    )


def has_label(control: Tag, soup: BeautifulSoup) -> bool:
    if control.get("aria-label") or control.get("aria-labelledby"):
        return True
    if control.find_parent("label"):
        return True
    control_id = control.get("id")
    return bool(control_id and soup.select_one(f'label[for="{control_id}"]'))


def audit_html(html: str) -> list[Violation]:
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one('meta[http-equiv="refresh" i]'):
        return []

    violations: list[Violation] = []

    if not soup.html or not soup.html.get("lang", "").strip():
        violations.append(Violation("html-lang", "The html element needs a language."))

    titles = soup.select("head > title")
    if len(titles) != 1 or not titles[0].get_text(strip=True):
        violations.append(Violation("document-title", "The page needs one non-empty title."))

    mains = soup.select("main")
    if len(mains) != 1:
        violations.append(
            Violation("main-landmark", f"Expected one main landmark; found {len(mains)}.")
        )

    h1s = soup.select("h1")
    if len(h1s) != 1:
        violations.append(Violation("page-h1", f"Expected one h1; found {len(h1s)}."))

    ids = [element["id"] for element in soup.select("[id]") if element.get("id")]
    for duplicate in sorted(
        item_id for item_id, count in Counter(ids).items() if count > 1
    ):
        violations.append(
            Violation("duplicate-id", f'Duplicate id "{duplicate}".')
        )

    headings = soup.select("h1,h2,h3,h4,h5,h6")
    for previous, current in zip(headings, headings[1:]):
        previous_level = int(previous.name[1])
        current_level = int(current.name[1])
        if current_level > previous_level + 1:
            violations.append(
                Violation(
                    "heading-order",
                    f"Heading level jumps from h{previous_level} to h{current_level}.",
                    element_excerpt(current),
                )
            )

    for image in soup.select("img:not([alt])"):
        violations.append(
            Violation("image-alt", "Image is missing an alt attribute.", element_excerpt(image))
        )

    for frame in soup.select("iframe:not([title])"):
        violations.append(
            Violation(
                "iframe-title",
                "Iframe is missing a title attribute.",
                element_excerpt(frame),
            )
        )

    for details in soup.select("details"):
        if not details.find("summary", recursive=False):
            violations.append(
                Violation(
                    "details-summary",
                    "Details element has no direct summary.",
                    element_excerpt(details),
                )
            )

    for audio in soup.select("audio:not([controls])"):
        violations.append(
            Violation(
                "audio-controls",
                "Audio element does not expose controls.",
                element_excerpt(audio),
            )
        )

    for control in soup.select("input,select,textarea"):
        if control.get("type", "").lower() == "hidden":
            continue
        if control.name == "input" and control.get("type", "").lower() in {
            "button",
            "reset",
            "submit",
        }:
            if accessible_name(control, soup):
                continue
        if not has_label(control, soup):
            violations.append(
                Violation(
                    "form-label",
                    "Form control has no associated label.",
                    element_excerpt(control),
                )
            )

    for button in soup.select("button"):
        if not accessible_name(button, soup):
            violations.append(
                Violation(
                    "button-name",
                    "Button has no accessible name.",
                    element_excerpt(button),
                )
            )

    for link in soup.select("a[href]"):
        if not accessible_name(link, soup):
            violations.append(
                Violation(
                    "link-name",
                    "Link has no accessible name.",
                    element_excerpt(link),
                )
            )

    return violations


def page_url(public_dir: Path, html_path: Path) -> str:
    relative = html_path.relative_to(public_dir)
    if relative.name == "index.html":
        parent = relative.parent.as_posix()
        return "/" if parent == "." else f"/{parent}/"
    return f"/{relative.as_posix()}"


def audit_site(public_dir: Path) -> dict:
    pages = []
    for html_path in sorted(public_dir.rglob("*.html")):
        violations = audit_html(html_path.read_text(encoding="utf-8"))
        pages.append(
            {
                "path": page_url(public_dir, html_path),
                "violations": [asdict(violation) for violation in violations],
            }
        )
    counts = Counter(
        violation["rule"]
        for page in pages
        for violation in page["violations"]
    )
    return {
        "schema_version": 1,
        "summary": {
            "pages": len(pages),
            "pages_with_violations": sum(bool(page["violations"]) for page in pages),
            "violations": sum(counts.values()),
            "by_rule": dict(sorted(counts.items())),
        },
        "pages": pages,
    }


def write_reports(report: dict, json_path: Path, csv_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "rule", "detail", "element"],
        )
        writer.writeheader()
        for page in report["pages"]:
            for violation in page["violations"]:
                writer.writerow({"path": page["path"], **violation})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run static accessibility checks against rendered Hugo HTML."
    )
    parser.add_argument("--public-dir", type=Path, default=DEFAULT_PUBLIC_DIR)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV_REPORT)
    args = parser.parse_args(argv)

    if not args.public_dir.exists():
        parser.error(f"Rendered Hugo directory not found: {args.public_dir}")

    report = audit_site(args.public_dir)
    write_reports(report, args.output_json, args.output_csv)
    summary = report["summary"]
    print("Accessibility audit summary")
    print(f"  Pages:                 {summary['pages']}")
    print(f"  Pages with violations: {summary['pages_with_violations']}")
    print(f"  Violations:            {summary['violations']}")
    for rule, count in summary["by_rule"].items():
        print(f"    {rule}: {count}")
    print(f"  JSON: {args.output_json}")
    print(f"  CSV:  {args.output_csv}")
    return 1 if summary["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
