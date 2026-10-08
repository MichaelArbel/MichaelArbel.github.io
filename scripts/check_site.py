#!/usr/bin/env python3
"""Check the built site's primary pages, local assets, and publication metadata."""

from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.references = []
        self.ids = set()
        self.title = ""
        self.description = ""
        self.in_title = False
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "title":
            self.in_title = True
        if tag == "meta" and attrs.get("name") == "description":
            self.description = attrs.get("content", "")
        for field in ("href", "src"):
            if attrs.get(field):
                self.references.append(attrs[field])

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def check():
    paths = ["", "team", "opportunities", "projects", "publications", "software", "talks", "teaching"]
    for project in ("bonsai", "erc"):
        paths.extend(f"projects/{project}/{section}" for section in ("", "publications", "software", "jobs"))
    pages = [Page(SITE / path / "index.html") for path in paths]
    for page in pages:
        assert page.title.strip(), f"Missing title: {page.path}"
        assert page.description.strip(), f"Missing description: {page.path}"
        for reference in page.references:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc:
                continue
            target = SITE / unquote(parsed.path).lstrip("/") if parsed.path.startswith("/") else page.path.parent / unquote(parsed.path)
            if not parsed.path:
                target = page.path
            if target.is_dir():
                target /= "index.html"
            assert target.exists(), f"Missing local target {reference!r} on {page.path}"
            if parsed.fragment and target.suffix == ".html":
                assert unquote(parsed.fragment) in Page(target).ids, f"Missing anchor {reference!r} on {page.path}"

    for project, name in (("bonsai", "BONSAI"), ("erc", "DELPHI")):
        headings = []
        for section in ("", "publications", "software", "jobs"):
            page = Page(SITE / "projects" / project / section / "index.html")
            assert name in page.title, f"Missing project context: {page.title}"
            html = page.path.read_text(encoding="utf-8")
            heading = re.search(r'<div class="project-heading has-funder-logo">.*?</a>\s*</div>', html, re.S)
            assert heading, f"Missing project header or funding logo: {page.path}"
            headings.append(heading.group())
        assert len(set(headings)) == 1, f"Inconsistent shared header for {name}"

    records = json.loads((ROOT / "_data/publications.json").read_text(encoding="utf-8"))
    assert len({record["title"] for record in records}) == len(records), "Duplicate publication titles"
    for record in records:
        assert "\\" not in record["title"], f"Unconverted TeX: {record['title']}"
        venue_years = re.findall(r"\b20\d{2}\b", record["venue"])
        if record["category"] == "peer_reviewed" and venue_years:
            assert record["year"] == venue_years[-1], f"Conference/year mismatch: {record['title']}"
    html = (SITE / "publications/index.html").read_text(encoding="utf-8")
    publication_text = PageText(html)
    for record in records:
        assert record["title"] in publication_text, f"Publication missing from HTML: {record['title']}"
    assert (SITE / "cv/CV.pdf").read_bytes() == (ROOT / "cv/CV.pdf").read_bytes(), "Built CV differs from source PDF"
    print(f"PASS: {len(pages)} pages, local links/assets, shared project headers, CV copy, and {len(records)} publications.")
    print("Publication categories:", dict(Counter(record["category"] for record in records)))


class PageText(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.text = []
        self.feed(html)

    def handle_data(self, data):
        self.text.append(data)

    def __contains__(self, value):
        return value in " ".join(self.text)


if __name__ == "__main__":
    check()
