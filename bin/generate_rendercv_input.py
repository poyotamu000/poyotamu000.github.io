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


ENGLISH_PUBLICATION_GROUP_KEYS = {
    "international_journal",
    "international_conference",
}


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
    if value.lower().startswith("and "):
        value = value[4:].strip()
    if not value:
        return ""
    if "," in value:
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if len(parts) >= 2:
            return f"{parts[1]} {parts[0]}"
    return value


def parse_authors(author_field: str) -> list[str]:
    raw = clean_text(author_field)
    if not raw:
        return []

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

    return names


def to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def strip_japanese_annotation(text: str) -> str:
    value = to_text(text)
    if not value:
        return ""
    # Remove patterns like:
    # - ", in Japanese ..."
    # - "(in Japanese, ...)"
    value = re.sub(r"\s*,\s*in\s+japanese\b.*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*\(\s*in\s+japanese\s*,\s*.*?\)", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s{2,}", " ", value).strip(" ,")
    return value


def format_link(url: str | None) -> str:
    if not url:
        return ""
    return f" ([link]({url}))"


def build_awards_section(awards: list[dict], profile: str) -> list[dict]:
    bullets: list[dict] = []
    for item in awards:
        title = to_text(item.get("title", ""))
        awarder = to_text(item.get("awarder", ""))
        date = to_text(item.get("date", ""))
        url = to_text(item.get("url", ""))

        if profile == "english":
            title = strip_japanese_annotation(title)
            awarder = strip_japanese_annotation(awarder)

        parts = [p for p in [date, title, awarder] if p]
        if not parts:
            continue
        bullet = " - ".join(parts[:2])
        if len(parts) == 3:
            bullet = f"{parts[0]} - {parts[1]}, {parts[2]}"
        bullet += format_link(url)
        bullets.append({"bullet": bullet})
    return bullets


def build_grants_section(grants: list[dict], profile: str) -> list[dict]:
    bullets: list[dict] = []
    for item in grants:
        title = to_text(item.get("title", ""))
        awarder = to_text(item.get("awarder", ""))
        if profile == "english":
            title = strip_japanese_annotation(title)
            awarder = strip_japanese_annotation(awarder)

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


def build_media_section(media: list[dict], profile: str) -> list[dict]:
    bullets: list[dict] = []
    for item in media:
        title = to_text(item.get("title", ""))
        date = to_text(item.get("date", ""))
        url = to_text(item.get("url", ""))

        if profile == "english":
            title = strip_japanese_annotation(title)

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


def build_publications_by_group(bib_path: Path, profile: str) -> dict[str, list[dict]]:
    content = bib_path.read_text(encoding="utf-8")
    raw_entries = split_bib_entries(content)
    string_map = parse_bib_strings(content)

    allowed_group_keys = {
        key for key, _ in PUBLICATION_GROUPS if profile != "english" or key in ENGLISH_PUBLICATION_GROUP_KEYS
    }
    grouped: dict[str, list[dict]] = {k: [] for k, _ in PUBLICATION_GROUPS if k in allowed_group_keys}

    for raw in raw_entries:
        pubtype = clean_text(extract_field(raw, "pubtype")).lower()
        if pubtype not in grouped:
            continue

        title = resolve_bib_value(extract_field(raw, "title"), string_map)
        year = resolve_bib_value(extract_field(raw, "year"), string_map)
        doi = resolve_bib_value(extract_field(raw, "doi"), string_map)
        url = resolve_bib_value(extract_field(raw, "url"), string_map)
        authors = parse_authors(resolve_bib_value(extract_field(raw, "author"), string_map))

        venue = resolve_bib_value(extract_field(raw, "journal"), string_map) or resolve_bib_value(
            extract_field(raw, "booktitle"), string_map
        )
        volume = resolve_bib_value(extract_field(raw, "volume"), string_map)
        number = resolve_bib_value(extract_field(raw, "number"), string_map)
        pages = resolve_bib_value(extract_field(raw, "pages"), string_map)

        venue_parts: list[str] = []
        if venue:
            venue_parts.append(venue)
        if volume:
            venue_parts.append(f"vol. {volume}")
        if number:
            venue_parts.append(f"no. {number}")
        if pages:
            formatted_pages = pages.replace("--", "-")
            if pubtype == "domestic_conference":
                venue_parts.append(formatted_pages)
            else:
                venue_parts.append(f"pp. {formatted_pages}")
        venue_text = ", ".join(venue_parts)

        if not title:
            continue

        entry: dict[str, object] = {
            "title": title,
            "authors": authors,
        }
        if venue_text:
            entry["journal"] = venue_text
        if year:
            entry["date"] = year
        if doi:
            entry["doi"] = doi if doi.startswith("http") else f"https://doi.org/{doi}"
        elif url:
            entry["url"] = url

        grouped[pubtype].append({"year": year, "entry": entry})

    grouped_entries: dict[str, list[dict]] = {}
    for key, heading in PUBLICATION_GROUPS:
        if key not in grouped:
            continue
        records = grouped.get(key, [])

        def sort_key(item: dict) -> tuple[int, str]:
            try:
                title = item.get("entry", {}).get("title", "") if isinstance(item.get("entry"), dict) else ""
                return (-int(item.get("year", "0") or 0), str(title))
            except ValueError:
                title = item.get("entry", {}).get("title", "") if isinstance(item.get("entry"), dict) else ""
                return (0, str(title))

        records.sort(key=sort_key)
        entries = [rec["entry"] for rec in records if isinstance(rec.get("entry"), dict)]
        if not entries:
            entries = [{"bullet": "No publications listed yet."}]
            grouped_entries[heading] = entries
            continue

        # Keep RenderCV's structured publication format for stable page breaks,
        # and append counts to headings so totals are immediately visible.
        grouped_entries[f"{heading} ({len(entries)})"] = entries

    return grouped_entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate RenderCV input YAML with synced sections")
    parser.add_argument("--input", required=True, help="Path to source cv.yml")
    parser.add_argument("--output", required=True, help="Path to generated cv.yml for RenderCV")
    parser.add_argument("--awards", default="_data/awards.yml")
    parser.add_argument("--grants", default="_data/grants.yml")
    parser.add_argument("--media", default="_data/media.yml")
    parser.add_argument("--bib", default="_bibliography/papers.bib")
    parser.add_argument(
        "--profile",
        choices=["english", "bilingual"],
        default="bilingual",
        help="Output profile for RenderCV input generation.",
    )
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

    sections["Awards"] = build_awards_section(awards, args.profile)
    sections["Grants-in-Aid and Scholarship"] = build_grants_section(grants, args.profile)
    sections["Media"] = build_media_section(media, args.profile)

    # Remove any legacy publication section names, then add categorized sections.
    for key in ["Publications", "Selected Publications"]:
        sections.pop(key, None)
    for _, heading in PUBLICATION_GROUPS:
        sections.pop(heading, None)

    publications_by_group = build_publications_by_group(Path(args.bib), args.profile)
    for key, heading in PUBLICATION_GROUPS:
        if args.profile == "english" and key not in ENGLISH_PUBLICATION_GROUP_KEYS:
            continue
        matched_heading = next((h for h in publications_by_group if h == heading or h.startswith(f"{heading} (")), heading)
        sections[matched_heading] = publications_by_group.get(matched_heading, [{"bullet": "No publications listed yet."}])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(generated, f, allow_unicode=True, sort_keys=False, width=1000)


if __name__ == "__main__":
    main()
