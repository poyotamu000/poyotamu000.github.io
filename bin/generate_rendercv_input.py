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


def parse_bib_strings(content: str) -> dict[str, str]:
    strings: dict[str, str] = {}
    for match in re.finditer(r"@string\s*\{\s*([^=\s]+)\s*=\s*(.+?)\}\s*", content, flags=re.IGNORECASE | re.DOTALL):
        key = clean_text(match.group(1)).lower()
        raw_val = match.group(2).strip().rstrip(",")
        if raw_val.startswith('"') and raw_val.endswith('"'):
            val = raw_val[1:-1]
        elif raw_val.startswith("{") and raw_val.endswith("}"):
            val = raw_val[1:-1]
        else:
            val = raw_val
        strings[key] = clean_text(val)
    return strings


def resolve_bib_value(value: str, strings: dict[str, str]) -> str:
    val = clean_text(value)
    if not val:
        return ""

    # Resolve simple token or token concatenation (token # token).
    parts = [p.strip() for p in val.split("#")]
    resolved_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        token = part.strip('"').strip().lower()
        resolved_parts.append(strings.get(token, part.strip('"').strip()))

    return clean_text(" ".join(resolved_parts))


def format_author_name(name: str) -> str:
    value = clean_text(name)
    if not value:
        return ""
    if "," in value:
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if len(parts) >= 2:
            return f"{parts[1]} {parts[0]}"
    return value


def format_authors(author_field: str) -> str:
    raw = clean_text(author_field)
    if not raw:
        return ""

    # BibTeX authors can appear as:
    # 1) "Last, First and Last, First"
    # 2) "First Last, First Last, ... and First Last"
    # Handle mixed comma + and notation first.
    if " and " in raw:
        and_split = [p.strip() for p in raw.split(" and ") if p.strip()]
        # If any chunk already contains multiple commas, the field is likely
        # comma-separated names plus a trailing "and last author".
        if any(part.count(",") > 1 for part in and_split):
            normalized = raw.replace(" and ", ",")
            names = [format_author_name(p.strip()) for p in normalized.split(",")]
        else:
            names = [format_author_name(p) for p in and_split]
    else:
        names = [format_author_name(p) for p in raw.split(",")]
    names = [n for n in names if n]

    if not names:
        return ""
    return ", ".join(names)


def to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def format_link(url: str | None) -> str:
    if not url:
        return ""
    return f" ([link]({url}))"


def build_awards_section(awards: list[dict]) -> list[dict]:
    bullets: list[dict] = []
    for item in awards:
        title = to_text(item.get("title", ""))
        awarder = to_text(item.get("awarder", ""))
        date = to_text(item.get("date", ""))
        url = to_text(item.get("url", ""))

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
        title = to_text(item.get("title", ""))
        awarder = to_text(item.get("awarder", ""))
        start = to_text(item.get("start_date", ""))
        end = to_text(item.get("end_date", ""))

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
        title = to_text(item.get("title", ""))
        date = to_text(item.get("date", ""))
        url = to_text(item.get("url", ""))

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


def build_publications_by_group(bib_path: Path) -> dict[str, list[dict]]:
    content = bib_path.read_text(encoding="utf-8")
    raw_entries = split_bib_entries(content)
    string_map = parse_bib_strings(content)

    grouped: dict[str, list[dict]] = {k: [] for k, _ in PUBLICATION_GROUPS}

    for raw in raw_entries:
        pubtype = clean_text(extract_field(raw, "pubtype")).lower()
        if pubtype not in grouped:
            continue

        title = resolve_bib_value(extract_field(raw, "title"), string_map)
        year = resolve_bib_value(extract_field(raw, "year"), string_map)
        doi = resolve_bib_value(extract_field(raw, "doi"), string_map)
        url = resolve_bib_value(extract_field(raw, "url"), string_map)
        authors = format_authors(resolve_bib_value(extract_field(raw, "author"), string_map))

        venue = resolve_bib_value(extract_field(raw, "journal"), string_map) or resolve_bib_value(
            extract_field(raw, "booktitle"), string_map
        )
        volume = resolve_bib_value(extract_field(raw, "volume"), string_map)
        number = resolve_bib_value(extract_field(raw, "number"), string_map)
        pages = resolve_bib_value(extract_field(raw, "pages"), string_map)

        link = ""
        if doi:
            doi_url = doi if doi.startswith("http") else f"https://doi.org/{doi}"
            link = f" ([doi]({doi_url}))"
        elif url:
            link = f" ([link]({url}))"

        venue_parts: list[str] = []
        if venue:
            venue_parts.append(venue)
        if volume:
            venue_parts.append(f"vol. {volume}")
        if number:
            venue_parts.append(f"no. {number}")
        if pages:
            venue_parts.append(f"pp. {pages.replace('--', '-')}")
        venue_text = ", ".join(venue_parts)

        header_parts: list[str] = []
        if authors:
            header_parts.append(authors)
        if title:
            header_parts.append(f'"{title}"')

        detail_parts: list[str] = []
        if venue_text:
            detail_parts.append(venue_text)
        if year:
            detail_parts.append(year)
        details = ", ".join(detail_parts)
        if link:
            details = f"{details}{link}" if details else link

        line = ", ".join(header_parts)
        if details:
            # Two-line layout improves readability and reduces page-break crowding.
            line = f"{line}  \n{details}" if line else details
        if title:
            grouped[pubtype].append({"year": year, "line": line})

    grouped_bullets: dict[str, list[dict]] = {}
    for key, heading in PUBLICATION_GROUPS:
        records = grouped.get(key, [])
        def sort_key(item: dict) -> tuple[int, str]:
            try:
                return (-int(item.get("year", "0") or 0), item.get("line", ""))
            except ValueError:
                return (0, item.get("line", ""))

        records.sort(key=sort_key)
        bullets: list[dict] = []
        for idx, rec in enumerate(records, start=1):
            bullets.append({"bullet": f"{idx}. {rec['line']}"})
        if not bullets:
            bullets = [{"bullet": "No publications listed yet."}]
        grouped_bullets[heading] = bullets

    return grouped_bullets


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

    # Remove any legacy publication section names, then add categorized sections.
    for key in ["Publications", "Selected Publications"]:
        sections.pop(key, None)

    publications_by_group = build_publications_by_group(Path(args.bib))
    for _, heading in PUBLICATION_GROUPS:
        sections[heading] = publications_by_group.get(heading, [{"bullet": "No publications listed yet."}])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(generated, f, allow_unicode=True, sort_keys=False, width=1000)


if __name__ == "__main__":
    main()
