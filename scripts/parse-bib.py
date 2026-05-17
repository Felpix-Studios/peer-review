#!/usr/bin/env python3
# Copyright 2026 Felpix Studios
#
# Licensed under the Apache License, Version 2.0. See LICENSE.

"""
Parse a BibTeX file into a normalized JSON list for the citation-checker.

Usage:
    parse-bib.py <bibfile.bib> --out <work_dir>/bib_entries.json

Output: a JSON array of entries, each with:
    { "key": "smith2024", "year": "2024", "authors": ["Smith, John", ...],
      "title": "...", "venue": "...", "type": "article|book|...",
      "raw": "<verbatim entry block, for display in the dossier>" }

Strategy: prefer the bibtexparser library when available (handles
concatenations, cross-refs, escaped braces correctly). Fall back to a small
regex parser that handles the common 90% of entries — good enough for a
"does this citation key exist with roughly this year/authors/title" check,
which is the only thing the citation-checker needs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _strip_braces(value: str) -> str:
    value = value.strip()
    while len(value) >= 2 and (
        (value[0] == "{" and value[-1] == "}")
        or (value[0] == '"' and value[-1] == '"')
    ):
        value = value[1:-1].strip()
    return re.sub(r"\s+", " ", value)


def _split_authors(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"\s+and\s+", raw, flags=re.IGNORECASE)
    return [_strip_braces(p) for p in parts if p.strip()]


def parse_with_bibtexparser(text: str) -> list[dict[str, Any]] | None:
    try:
        import bibtexparser
    except ImportError:
        return None

    parser_cls = getattr(bibtexparser, "bparser", None)
    try:
        if parser_cls is not None:
            bib_db = bibtexparser.loads(text)
        else:
            bib_db = bibtexparser.parse_string(text)
    except Exception as exc:
        sys.stderr.write(f"WARNING: bibtexparser failed ({exc}); falling back to regex parser.\n")
        return None

    entries_raw = getattr(bib_db, "entries", None)
    if entries_raw is None:
        return None

    out: list[dict[str, Any]] = []
    for entry in entries_raw:
        if isinstance(entry, dict):
            fields = {k.lower(): v for k, v in entry.items()}
            key = fields.pop("id", fields.pop("ID", "")) or ""
            entry_type = fields.pop("entrytype", fields.pop("ENTRYTYPE", "")) or ""
        else:
            fields = {f.key.lower(): f.value for f in getattr(entry, "fields", [])}
            key = getattr(entry, "key", "") or ""
            entry_type = getattr(entry, "entry_type", "") or ""

        out.append(
            {
                "key": str(key).strip(),
                "type": str(entry_type).strip().lower(),
                "year": _strip_braces(str(fields.get("year", ""))),
                "authors": _split_authors(str(fields.get("author", ""))),
                "title": _strip_braces(str(fields.get("title", ""))),
                "venue": _strip_braces(
                    str(fields.get("journal") or fields.get("booktitle") or fields.get("publisher") or "")
                ),
                "raw": "",
            }
        )
    return out


_ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)


def _split_entries(text: str) -> list[tuple[str, str, str]]:
    """Yield (entry_type, key, body) per entry. body is the brace-balanced
    content between the first `{` after the key and its matching `}`."""
    entries: list[tuple[str, str, str]] = []
    for match in _ENTRY_RE.finditer(text):
        entry_type = match.group(1).lower()
        key = match.group(2)
        body_start = match.end()
        depth = 1
        i = body_start
        while i < len(text) and depth > 0:
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        body = text[body_start : i - 1] if depth == 0 else text[body_start:]
        entries.append((entry_type, key, body))
    return entries


_FIELD_RE = re.compile(r"(\w+)\s*=\s*", re.MULTILINE)


def _parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    pos = 0
    while pos < len(body):
        m = _FIELD_RE.search(body, pos)
        if not m:
            break
        name = m.group(1).lower()
        value_start = m.end()
        if value_start >= len(body):
            break
        opener = body[value_start]
        if opener == "{":
            depth = 1
            i = value_start + 1
            while i < len(body) and depth > 0:
                c = body[i]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                i += 1
            value = body[value_start + 1 : i - 1]
            pos = i
        elif opener == '"':
            i = value_start + 1
            while i < len(body) and body[i] != '"':
                i += 1
            value = body[value_start + 1 : i]
            pos = i + 1
        else:
            comma = body.find(",", value_start)
            end = comma if comma != -1 else len(body)
            value = body[value_start:end]
            pos = end
        fields[name] = value.strip().rstrip(",").strip()
        comma = body.find(",", pos)
        pos = comma + 1 if comma != -1 else len(body)
    return fields


def parse_with_regex(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry_type, key, body in _split_entries(text):
        fields = _parse_fields(body)
        out.append(
            {
                "key": key.strip(),
                "type": entry_type,
                "year": _strip_braces(fields.get("year", "")),
                "authors": _split_authors(fields.get("author", "")),
                "title": _strip_braces(fields.get("title", "")),
                "venue": _strip_braces(
                    fields.get("journal") or fields.get("booktitle") or fields.get("publisher") or ""
                ),
                "raw": f"@{entry_type}{{{key},{body}}}".strip(),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("bib", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if not args.bib.exists():
        sys.exit(f".bib file not found: {args.bib}")

    text = args.bib.read_text(encoding="utf-8", errors="replace")
    entries = parse_with_bibtexparser(text)
    if entries is None:
        entries = parse_with_regex(text)

    if not entries:
        sys.stderr.write(
            f"WARNING: parsed 0 entries from {args.bib}. The file may be empty, "
            f"malformed, or use a non-BibTeX format.\n"
        )

    args.out.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.out} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
