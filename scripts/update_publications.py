#!/usr/bin/env python3
"""Enrich the curated BibTeX bibliography from official arXiv metadata."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as element_tree
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from time import sleep


ROOT = Path(__file__).resolve().parents[1]
BIBLIOGRAPHY = ROOT / "assets/bibliography/bibliography.bib"
PUBLICATIONS_DATA = ROOT / "_data/publications.json"
ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_AUTHOR_QUERY = os.environ.get("ARXIV_AUTHOR_QUERY", "au:Arbel_Michael")
ARXIV_AUTHOR_NAME = os.environ.get("ARXIV_AUTHOR_NAME", "Michael Arbel")
ARXIV_PAGE_SIZE = 100
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
ARXIV_NAMESPACE = "http://arxiv.org/schemas/atom"


@dataclass(frozen=True)
class ArxivRecord:
    """The fields used from one entry in the arXiv Atom feed."""

    identifier: str
    title: str
    authors: tuple[str, ...]
    published: str
    primary_category: str

    @property
    def year(self) -> str:
        return self.published[:4]

    @property
    def month(self) -> str:
        month_number = int(self.published[5:7])
        return ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")[
            month_number - 1
        ]


@dataclass(frozen=True)
class SyncSummary:
    """A concise, human-readable summary of an arXiv synchronization."""

    records_found: int
    existing_entries_enriched: int
    entries_added: int


def plain_text(value: str) -> str:
    """Convert the common LaTeX markup found in BibTeX into display text."""
    from pylatexenc.latex2text import LatexNodes2Text

    text = LatexNodes2Text().latex_to_text(value)
    return re.sub(r"\s+", " ", text).strip()


def normalized_text(value: str) -> str:
    """Normalize titles and names for conservative matching across sources."""
    text = unicodedata.normalize("NFKD", plain_text(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def publication_month(entry: dict[str, str]) -> str:
    """Return a numeric BibTeX month when one is available, otherwise an empty string."""
    value = str(entry.get("month", "")).strip().lower()
    date_value = str(entry.get("date", "")).strip()
    date_match = re.search(r"\d{4}[-/]([01]?\d)", date_value)
    if date_match:
        value = date_match.group(1)

    month_names = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    if value[:3] in month_names:
        return str(month_names[value[:3]])

    try:
        numeric_month = int(value)
    except ValueError:
        return ""
    return str(numeric_month) if 1 <= numeric_month <= 12 else ""


def publication_venue(entry: dict[str, str]) -> str:
    """Return the most useful human-readable venue or outlet for an entry."""
    for field in ("journal", "booktitle", "venue", "school", "howpublished", "note"):
        if entry.get(field):
            return plain_text(entry[field])
    return ""


def publication_category(entry: dict[str, str], venue: str) -> str:
    """Classify records for the public bibliography without losing any entries."""
    entry_type = entry.get("ENTRYTYPE", "").lower()
    venue_text = venue.lower()
    if entry_type in {"misc", "phdthesis", "mastersthesis", "techreport", "unpublished"}:
        return "other"
    if "workshop" in venue_text or "arxiv" in venue_text:
        return "other" if "workshop" in venue_text else "preprint"
    return "peer_reviewed"


def publication_records(bibliography: str) -> list[dict[str, str]]:
    import bibtexparser

    entries = bibtexparser.loads(bibliography).entries
    records: list[dict[str, str]] = []
    for entry in entries:
        year = entry.get("year", entry.get("pub_year", ""))
        url = entry.get("url", "")
        if not url and entry.get("doi"):
            url = f"https://doi.org/{entry['doi']}"
        if not url and entry.get("eprint"):
            url = f"https://arxiv.org/abs/{entry['eprint']}"

        venue = publication_venue(entry)
        records.append(
            {
                "title": plain_text(entry.get("title", "Untitled")),
                "author": plain_text(entry.get("author", "")),
                "venue": venue,
                "year": str(year),
                "month": publication_month(entry),
                "url": url,
                "type": entry.get("ENTRYTYPE", ""),
                "category": publication_category(entry, venue),
            }
        )

    def ordering_key(record: dict[str, str]) -> tuple[int, int, str]:
        match = re.search(r"\d{4}", record["year"])
        year = int(match.group()) if match else 0
        month = int(record["month"]) if record["month"].isdigit() else 0
        return (-year, -month, record["title"].casefold())

    return sorted(records, key=ordering_key)


def write_jekyll_data(bibliography: str) -> None:
    records = publication_records(bibliography)
    if not records:
        raise RuntimeError("The bibliography did not contain any publication entries")

    content = json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    if PUBLICATIONS_DATA.exists() and PUBLICATIONS_DATA.read_text(encoding="utf-8") == content:
        print("Jekyll publication data is already up to date.")
        return

    PUBLICATIONS_DATA.parent.mkdir(exist_ok=True)
    PUBLICATIONS_DATA.write_text(content, encoding="utf-8")
    print(f"Updated {PUBLICATIONS_DATA.relative_to(ROOT)} with {len(records)} publications.")


def atom_tag(name: str) -> str:
    return f"{{{ATOM_NAMESPACE}}}{name}"


def arxiv_tag(name: str) -> str:
    return f"{{{ARXIV_NAMESPACE}}}{name}"


def parse_arxiv_feed(feed: bytes) -> tuple[int, list[ArxivRecord]]:
    """Parse one official arXiv Atom response."""
    try:
        root = element_tree.fromstring(feed)
    except element_tree.ParseError as error:
        raise RuntimeError(f"arXiv returned invalid XML: {error}") from error

    total_text = root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults", default="0")
    try:
        total_results = int(total_text)
    except ValueError as error:
        raise RuntimeError("arXiv did not provide a valid result count") from error

    records: list[ArxivRecord] = []
    for entry in root.findall(atom_tag("entry")):
        source_id = entry.findtext(atom_tag("id"), default="")
        identifier_match = re.search(r"/abs/([^/]+)$", source_id)
        if not identifier_match:
            raise RuntimeError("arXiv returned a publication without an identifier")
        identifier = re.sub(r"v\d+$", "", identifier_match.group(1))
        title = " ".join(entry.findtext(atom_tag("title"), default="").split())
        published = entry.findtext(atom_tag("published"), default="")
        authors = tuple(
            " ".join(author.findtext(atom_tag("name"), default="").split())
            for author in entry.findall(atom_tag("author"))
        )
        primary_category = entry.find(arxiv_tag("primary_category"))
        category = primary_category.get("term", "") if primary_category is not None else ""

        if not title or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", published) or not authors:
            raise RuntimeError(f"arXiv returned incomplete metadata for {identifier}")
        records.append(ArxivRecord(identifier, title, authors, published, category))

    return total_results, records


def fetch_arxiv_records() -> list[ArxivRecord]:
    """Fetch every result for the configured author through the arXiv API."""
    records: list[ArxivRecord] = []
    start = 0
    total_results: int | None = None

    while total_results is None or start < total_results:
        query = urllib.parse.urlencode(
            {
                "search_query": ARXIV_AUTHOR_QUERY,
                "start": start,
                "max_results": ARXIV_PAGE_SIZE,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
        )
        request = urllib.request.Request(
            f"{ARXIV_API}?{query}",
            headers={"User-Agent": "MichaelArbel-publications/1.0 (https://michaelarbel.github.io)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                page_total, page_records = parse_arxiv_feed(response.read())
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"arXiv returned HTTP {error.code}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"Could not reach arXiv: {error.reason}") from error

        if total_results is None:
            total_results = page_total
        elif page_total != total_results:
            raise RuntimeError("arXiv's result count changed while fetching the author feed")

        records.extend(page_records)
        start += len(page_records)
        if start >= total_results:
            break
        if not page_records:
            raise RuntimeError("arXiv returned fewer records than it reported")
        sleep(3)

    target_author = normalized_text(ARXIV_AUTHOR_NAME)
    unexpected_records = [
        record.identifier
        for record in records
        if target_author not in {normalized_text(author) for author in record.authors}
    ]
    if unexpected_records:
        raise RuntimeError(
            "arXiv returned records not authored by "
            f"{ARXIV_AUTHOR_NAME}: {', '.join(unexpected_records)}"
        )
    if not records:
        raise RuntimeError("arXiv returned no publications")
    return records


def normalize_eprint(value: str) -> str:
    """Normalize arXiv identifiers whether or not they include a version or prefix."""
    identifier = value.strip()
    identifier = re.sub(r"^https?://arxiv\.org/abs/", "", identifier)
    identifier = re.sub(r"^arXiv:", "", identifier, flags=re.IGNORECASE)
    return re.sub(r"v\d+$", "", identifier)


def same_title(entry: dict[str, str], record: ArxivRecord) -> bool:
    """Match entries exactly, or only with a very strong, author-safe title match."""
    existing_title = normalized_text(entry.get("title", ""))
    arxiv_title = normalized_text(record.title)
    if existing_title == arxiv_title:
        return True

    existing_authors = entry.get("author", "").split(" and ")
    existing_first_author = normalized_text(existing_authors[0]) if existing_authors else ""
    arxiv_first_author = normalized_text(record.authors[0])
    similarity = SequenceMatcher(None, existing_title, arxiv_title).ratio()
    return existing_first_author == arxiv_first_author and similarity >= 0.96


def bibtex_entry_bounds(bibliography: str, entry_id: str) -> tuple[int, int]:
    """Return the exact range of a BibTeX entry without reformatting the file."""
    pattern = re.compile(rf"@\w+\s*\{{\s*{re.escape(entry_id)}\s*,", re.IGNORECASE)
    match = pattern.search(bibliography)
    if match is None:
        raise RuntimeError(f"Could not locate the BibTeX source for entry '{entry_id}'")

    opening_brace = bibliography.find("{", match.start(), match.end())
    depth = 0
    escaped = False
    for position in range(opening_brace, len(bibliography)):
        character = bibliography[position]
        if character == "\\" and not escaped:
            escaped = True
            continue
        if character == "{" and not escaped:
            depth += 1
        elif character == "}" and not escaped:
            depth -= 1
            if depth == 0:
                return match.start(), position + 1
        escaped = False
    raise RuntimeError(f"Could not find the end of BibTeX entry '{entry_id}'")


def entry_with_arxiv_metadata(entry_text: str, record: ArxivRecord) -> tuple[str, bool]:
    """Add missing arXiv fields while leaving all curated fields untouched."""
    metadata = [
        ("eprint", record.identifier),
        ("archivePrefix", "arXiv"),
        ("primaryClass", record.primary_category),
    ]
    missing = [
        (name, value)
        for name, value in metadata
        if value and not re.search(rf"(?im)^\s*{re.escape(name)}\s*=", entry_text)
    ]
    if not missing:
        return entry_text, False

    body = entry_text[:-1].rstrip()
    if not body.endswith(","):
        body += ","
    additions = ",\n".join(f"\t{name} = {{{value}}}" for name, value in missing)
    return f"{body}\n{additions}\n}}", True


def bibtex_key(record: ArxivRecord, used_keys: set[str]) -> str:
    """Create a readable, stable, and collision-free key for a new preprint."""
    author_text = unicodedata.normalize("NFKD", plain_text(record.authors[0])).encode("ascii", "ignore").decode("ascii")
    first_author_words = re.findall(r"[a-z0-9]+", author_text.lower())
    last_name = first_author_words[-1] if first_author_words else "arxiv"
    title_text = unicodedata.normalize("NFKD", plain_text(record.title)).encode("ascii", "ignore").decode("ascii")
    title_words = re.findall(r"[a-z0-9]+", title_text.lower())
    title_word = title_words[0] if title_words else "preprint"
    base = f"{last_name}{record.year}{title_word}"
    candidate = base
    suffix = ord("a")
    while candidate.lower() in used_keys:
        candidate = f"{base}{chr(suffix)}"
        suffix += 1
    used_keys.add(candidate.lower())
    return candidate


def bibtex_value(value: str) -> str:
    """Preserve arXiv's TeX markup while protecting literal BibTeX delimiters."""
    return value.replace("&", r"\&")


def new_arxiv_entry(record: ArxivRecord, entry_id: str) -> str:
    """Generate a minimal BibTeX entry for an arXiv preprint absent from the file."""
    authors = " and ".join(record.authors)
    lines = [
        f"@article{{{entry_id},",
        f"\tauthor = {{{bibtex_value(authors)}}},",
        f"\ttitle = {{{bibtex_value(record.title)}}},",
        f"\tjournal = {{arXiv preprint arXiv:{record.identifier}}},",
        f"\tyear = {{{record.year}}},",
        f"\tmonth = {record.month},",
        f"\teprint = {{{record.identifier}}},",
        "\tarchivePrefix = {arXiv},",
    ]
    if record.primary_category:
        lines.append(f"\tprimaryClass = {{{record.primary_category}}},")
    lines.append("}")
    return "\n".join(lines)


def synchronize_arxiv(bibliography: str, records: list[ArxivRecord]) -> tuple[str, SyncSummary]:
    """Merge official arXiv metadata into, never replace, the curated bibliography."""
    import bibtexparser

    entries = bibtexparser.loads(bibliography).entries
    entries_by_identifier = {
        normalize_eprint(entry["eprint"]): entry
        for entry in entries
        if entry.get("eprint")
    }
    used_keys = {entry["ID"].lower() for entry in entries}
    matched_entries: dict[str, ArxivRecord] = {}
    additions: list[ArxivRecord] = []

    for record in records:
        entry = entries_by_identifier.get(record.identifier)
        if entry is None:
            title_matches = [candidate for candidate in entries if same_title(candidate, record)]
            if len(title_matches) > 1:
                raise RuntimeError(f"More than one curated entry matches arXiv record {record.identifier}")
            entry = title_matches[0] if title_matches else None

        if entry is None:
            additions.append(record)
            continue

        entry_id = entry["ID"]
        previous_record = matched_entries.get(entry_id)
        if previous_record is not None and previous_record.identifier != record.identifier:
            raise RuntimeError(f"Curated entry '{entry_id}' matches multiple arXiv records")
        matched_entries[entry_id] = record

    enriched = 0
    for entry_id, record in matched_entries.items():
        start, end = bibtex_entry_bounds(bibliography, entry_id)
        updated_entry, changed = entry_with_arxiv_metadata(bibliography[start:end], record)
        if changed:
            bibliography = bibliography[:start] + updated_entry + bibliography[end:]
            enriched += 1

    generated_entries = [new_arxiv_entry(record, bibtex_key(record, used_keys)) for record in additions]
    if generated_entries:
        bibliography = bibliography.rstrip() + "\n\n" + "\n\n".join(generated_entries) + "\n"

    return bibliography, SyncSummary(len(records), enriched, len(generated_entries))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-bib",
        action="store_true",
        help="Regenerate Jekyll data from the existing BibTeX file without contacting arXiv.",
    )
    arguments = parser.parse_args()

    try:
        bibliography = BIBLIOGRAPHY.read_text(encoding="utf-8")
        if arguments.from_bib:
            write_jekyll_data(bibliography)
            return 0

        updated_bibliography, summary = synchronize_arxiv(bibliography, fetch_arxiv_records())
        if updated_bibliography != bibliography:
            BIBLIOGRAPHY.write_text(updated_bibliography, encoding="utf-8")
            print(f"Updated {BIBLIOGRAPHY.relative_to(ROOT)}.")
        else:
            print("The curated bibliography already contains the current arXiv metadata.")
        print(
            f"arXiv found {summary.records_found} records; enriched "
            f"{summary.existing_entries_enriched} curated entries and added {summary.entries_added} preprints."
        )
        write_jekyll_data(updated_bibliography)
    except Exception as error:  # Keep the checked-in files untouched on failure.
        print(f"Publication update failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
