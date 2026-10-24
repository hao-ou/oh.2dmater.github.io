"""MkDocs hook: regenerate docs/publications.md from docs/publications.bib before every build.

Wired up in mkdocs.yml:

    hooks:
      - hooks/publications.py

Why a hook instead of a manual script: the old workflow required running `python docs/ParseBib.py`
by hand after editing the .bib, which is how the committed publications.md drifted out of sync.
Now `mkdocs build` (locally and in CI) always regenerates the page, so the .bib is the single
source of truth.

No third-party dependency: the .bib in this repo only uses simple `key = {value}` fields, so a
small brace-aware reader is enough. That keeps `requirements.txt` unchanged and avoids the
bibtexparser v1/v2 API break.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

ENTRY_HEAD = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
FIELD_HEAD = re.compile(r"(\w+)\s*=\s*")

# BibTeX writes accented letters as escapes ("Moir{\'e}"); strip the braces and compose them into
# real Unicode so the page never shows a stray backslash.
_ACCENT_MARKS = {"'": "\u0301", '"': "\u0308", "`": "\u0300", "^": "\u0302", "~": "\u0303"}
_ACCENT_RE = re.compile(r"\\(['\"`^~])\{?([A-Za-z])\}?")


def decode_latex_accents(value: str) -> str:
    def _compose(match: re.Match[str]) -> str:
        mark = _ACCENT_MARKS.get(match.group(1))
        return unicodedata.normalize("NFC", match.group(2) + mark) if mark else match.group(0)

    return _ACCENT_RE.sub(_compose, value)


def _read_group(text: str, pos: int, opener: str, closer: str) -> tuple[str, int]:
    """Return (inner_text, position_after_closer) for a balanced {...} or "..." group."""
    depth = 1
    start = pos + 1
    i = start
    while i < len(text):
        ch = text[i]
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    raise ValueError(f"unbalanced {opener}{closer} group starting at offset {pos}")


def parse_bib(raw: str) -> list[tuple[str, str, dict[str, str]]]:
    """Parse a .bib file into [(entry_type, key, fields), ...]."""
    entries: list[tuple[str, str, dict[str, str]]] = []
    pos = 0
    while True:
        at = raw.find("@", pos)
        if at < 0:
            return entries
        head = ENTRY_HEAD.match(raw, at)
        if not head:
            pos = at + 1
            continue

        entry_type, key = head.group(1).lower(), head.group(2)
        body, pos = _read_group(raw, head.end(), "{", "}")

        fields: dict[str, str] = {}
        cursor = 0
        while cursor < len(body):
            while cursor < len(body) and body[cursor] in " \t\r\n,":
                cursor += 1
            if cursor >= len(body):
                break
            name_match = FIELD_HEAD.match(body, cursor)
            if not name_match:
                break
            name = name_match.group(1).lower()
            cursor = name_match.end()
            if cursor >= len(body):
                break
            char = body[cursor]
            if char == "{":
                value, cursor = _read_group(body, cursor, "{", "}")
            elif char == '"':
                value, cursor = _read_group(body, cursor, '"', '"')
            else:
                value_match = re.match(r"[^,\n]*", body[cursor:])
                value = value_match.group(0).strip()
                cursor += value_match.end()
            fields[name] = value

        entries.append((entry_type, key, fields))


def format_authors(author_string: str) -> str:
    if not author_string:
        return ""
    authors = []
    for author in author_string.split(" and "):
        author = author.strip()
        if "," in author:
            last, first = author.split(",", 1)
            authors.append(f"{first.strip()} {last.strip()}")
        else:
            authors.append(author)
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    return ", ".join(authors[:-1]) + f", and {authors[-1]}"


def render_entry(fields: dict[str, str]) -> str:
    title = decode_latex_accents(fields.get("title", "").replace("{", "").replace("}", ""))
    journal = decode_latex_accents(fields.get("journal", fields.get("booktitle", "")))
    authors = format_authors(fields.get("author", "")).replace("Hao Ou", "<u>Hao Ou</u>")
    volume = fields.get("volume", "")
    pages = fields.get("pages", "").replace("--", "-")

    pub_info = f"*{journal}*" if journal else ""
    if volume:
        pub_info += f", **{volume}**"
    if pages:
        pub_info += f", {pages}"
    year = fields.get("year", "").strip()
    if year and year.lower() != "unknown":
        pub_info += f" ({year})"

    url = fields.get("url", "").strip()
    doi = fields.get("doi", "").strip()
    link = url or (f"https://doi.org/{doi}" if doi else "")
    heading = f"[{title}]({link})" if link else title

    line = f"- {authors}. **\"{heading}\"**."
    if pub_info:
        line += f" {pub_info}."
    return line


def build_publications_markdown(raw_bib: str) -> str:
    """Same output format the committed publications.md always had (groups by year, newest first)."""
    articles = [fields for entry_type, _key, fields in parse_bib(raw_bib) if entry_type == "article"]
    articles.sort(key=lambda fields: int(fields.get("year", "0") or 0), reverse=True)

    chunks = ["# Publications\n\n"]
    current_year = None
    for fields in articles:
        year = fields.get("year", "Unknown")
        if year != current_year:
            chunks.append(f"## {year}\n\n")
            current_year = year
        chunks.append(render_entry(fields) + "\n")
    return "".join(chunks)


def on_pre_build(config) -> None:
    docs_dir = Path(config["docs_dir"])
    bib_path = docs_dir / "publications.bib"
    target = docs_dir / "publications.md"
    if not bib_path.is_file():
        return
    markdown = build_publications_markdown(bib_path.read_text(encoding="utf-8"))
    if not target.is_file() or target.read_text(encoding="utf-8") != markdown:
        target.write_text(markdown, encoding="utf-8")
