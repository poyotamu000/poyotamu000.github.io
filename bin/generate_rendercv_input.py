#!/usr/bin/env python3
"""Generate a RenderCV-only YAML from canonical data sources.

This script keeps website-facing data files as the source of truth and injects
PDF-oriented sections for RenderCV generation:
- Awards: from _data/awards.yml
- Grants-in-Aid and Scholarship: from _data/grants.yml
- Media: from _data/media.yml
- Publications: from _bibliography/papers.bib grouped by pubtype
"""

from __future__ import annotations

import argparse
import copy
import re
from pathlib import Path

import yaml

PUBLICATION_GROUPS = [
    ("international_journal", "International Journal Papers"),
    ("international_conference", "International Conference Proceedings (Peer Reviewed)"),
    ("domestic_journal", "Domestic Journal Papers"),
    ("domestic_conference", "Domestic Conference Proceedings"),
]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def clean_text(value: str) -> str:
    text = value.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("{", "").replace("}", "")
    return text


def format_link(url: str | None) -> str:
    if not url:
        return ""
    return f" ([link]({url}))"


def build_awards_section(awards: list[dict]) -> list[dict]:
    bullets: list[dict] = []
    for item in awards:
        title = item.get("title", "").strip()
        awarder = item.get("awarder", "").strip()
        date = item.get("date", "").strip()
        url = item.get("url", "").strip()

        parts = [p for p in [date, title, awarder] if p]
        if not parts:
            continue
        bullet = " - ".join(parts[:2])
        if len(parts) == 3:
            bullet = f"{parts[0]} - {parts[1]}, {parts[2]}"
        bullet += format_link(url)
        bullets.append({"bullet": bullet})
    return bullets


def build_grants_section(grants: list[dict]) -> list[dict]:
    bullets: list[dict] = []
    for item in grants:
        title = item.get("title", "").strip()
        awarder = item.get("awarder", "").strip()
        start = item.get("start_date", "").strip()
        end = item.get("end_date", "").strip()

        period = ""
        if start and end:
            period = f"{start} to {end}"
        elif start:
            period = start
        elif end:
            period = end

        head = ""
        if period and title:
            head = f"{period} - {title}"
        elif title:
            head = title
        elif period:
            head = period

        if not head:
            continue

        if awarder:
            head = f"{head}, {awarder}"

        bullets.append({"bullet": head})
    return bullets


def build_media_section(media: list[dict]) -> list[dict]:
    bullets: list[dict] = []
    for item in media:
        title = item.get("title", "").strip()
        date = item.get("date", "").strip()
        url = item.get("url", "").strip()

        if not title and not date:
            continue

        bullet = f"{date} - {title}" if date and title else (title or date)
        bullet += format_link(url)
        bullets.append({"bullet": bullet})
    return bullets


def extract_field(entry: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}\s*=", entry, flags=re.IGNORECASE)
    if not match:
        return ""

    i = match.end()
    n = len(entry)
    while i < n and entry[i].isspace():
        i += 1
    if i >= n:
        return ""

    if entry[i] == "{":
        depth = 0
        start = i + 1
        i += 1
        while i < n:
            ch = entry[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                if depth == 0:
                    return entry[start:i].strip()
                depth -= 1
            i += 1
        return entry[start:].strip()

    if entry[i] == '"':
        start = i + 1
        i += 1
        while i < n:
            if entry[i] == '"' and entry[i - 1] != "\\":
                return entry[start:i].strip()
            i += 1
        return entry[start:].strip()

    start = i
    while i < n and entry[i] not in ",\n":
        i += 1
    return entry[start:i].strip()


def split_bib_entries(content: str) -> list[str]:
    entries: list[str] = []
    i = 0
    n = len(content)

    while i < n:
        if content[i] != "@":
            i += 1
            continue

        brace_idx = content.find("{", i)
        if brace_idx == -1:
            break

        depth = 1
        j = brace_idx + 1
        while j < n and depth > 0:
            if content[j] == "{":
                depth += 1
            elif content[j] == "}":
                depth -= 1
            j += 1

        entries.append(content[i:j])
        i = j

    return entries


def build_publications_section(bib_path: Path) -> list[dict]:
    content = bib_path.read_text(encoding="utf-8")
    raw_entries = split_bib_entries(content)

    grouped: dict[str, list[dict]] = {k: [] for k, _ in PUBLICATION_GROUPS}

    for raw in raw_entries:
        pubtype = clean_text(extract_field(raw, "pubtype")).lower()
        if pubtype not in grouped:
            continue

        title = clean_text(extract_field(raw, "title"))
        year = clean_text(extract_field(raw, "year"))
        doi = clean_text(extract_field(raw, "doi"))
        url = clean_text(extract_field(raw, "url"))

        link = ""
        if doi:
            doi_url = doi if doi.startswith("http") else f"https://doi.org/{doi}"
            link = f" ([doi]({doi_url}))"
        elif url:
            link = f" ([link]({url}))"

        line = f"{year} - {title}{link}" if year else f"{title}{link}"
        if title:
            grouped[pubtype].append({"year": year, "line": line})

    bullets: list[dict] = []
    for key, heading in PUBLICATION_GROUPS:
        records = grouped.get(key, [])
        if not records:
            continue

        def sort_key(item: dict) -> tuple[int, str]:
            try:
                return (-int(item.get("year", "0") or 0), item.get("line", ""))
            except ValueError:
                return (0, item.get("line", ""))

        records.sort(key=sort_key)
        bullets.append({"bullet": f"**{heading}**"})
        for rec in records:
            bullets.append({"bullet": rec["line"]})

    return bullets


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate RenderCV input YAML with synced sections")
    parser.add_argument("--input", required=True, help="Path to source cv.yml")
    parser.add_argument("--output", required=True, help="Path to generated cv.yml for RenderCV")
    parser.add_argument("--awards", default="_data/awards.yml")
    parser.add_argument("--grants", default="_data/grants.yml")
    parser.add_argument("--media", default="_data/media.yml")
    parser.add_argument("--bib", default="_bibliography/papers.bib")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    source = load_yaml(in_path)
    generated = copy.deepcopy(source)

    cv_root = generated.setdefault("cv", {})
    sections = cv_root.setdefault("sections", {})

    awards = load_yaml(Path(args.awards)).get("entries", [])
    grants = load_yaml(Path(args.grants)).get("entries", [])
    media = load_yaml(Path(args.media)).get("entries", [])

    sections["Awards"] = build_awards_section(awards)
    sections["Grants-in-Aid and Scholarship"] = build_grants_section(grants)
    sections["Media"] = build_media_section(media)
    sections["Publications"] = build_publications_section(Path(args.bib))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(generated, f, allow_unicode=True, sort_keys=False, width=1000)


if __name__ == "__main__":
    main()
