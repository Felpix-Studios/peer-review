#!/usr/bin/env python3
# Copyright 2026 Felpix Studios
#
# Licensed under the Apache License, Version 2.0. See LICENSE.

"""
Extract plain text from a PDF for use by peer-review agents.

Usage:
    python extract-pdf-text.py <paper.pdf> [--pages 1-20] [--out paper.txt]

Reads the PDF with pypdf and writes a UTF-8 text file with [Page N] markers
between pages. Designed to be a fallback when an agent prefers OCR-extracted
text over reading the PDF directly (e.g. the math-verifier, which works
better with the explicit text dump).
"""

import argparse
import sys
from pathlib import Path


def extract_text(pdf_path: Path, pages: str | None = None) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.stderr.write(
            "pypdf is not installed. Install it with `pip install pypdf` "
            "(or `uv pip install pypdf`).\n"
        )
        sys.exit(1)

    reader = PdfReader(str(pdf_path))
    n = len(reader.pages)

    if pages:
        # parse "1-20" or "5,7,9-12"
        wanted: set[int] = set()
        for chunk in pages.split(","):
            chunk = chunk.strip()
            if "-" in chunk:
                a, b = chunk.split("-", 1)
                wanted.update(range(int(a), int(b) + 1))
            else:
                wanted.add(int(chunk))
    else:
        wanted = set(range(1, n + 1))

    out_chunks: list[str] = []
    for idx in range(1, n + 1):
        if idx not in wanted:
            continue
        text = reader.pages[idx - 1].extract_text() or ""
        out_chunks.append(f"[Page {idx}]\n{text.strip()}")
    return "\n\n".join(out_chunks), len(out_chunks)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--pages", default=None, help='e.g. "1-20" or "5,7,9-12"')
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if not args.pdf.exists():
        sys.exit(f"PDF not found: {args.pdf}")

    text, n_pages = extract_text(args.pdf, args.pages)
    total_chars = len(text)
    chars_per_page = total_chars / max(n_pages, 1)

    # Scanned/image-only PDFs yield ~0-50 chars/page of OCR garbage;
    # normal papers produce ~1,000-3,000 chars/page. 100 is a comfortable
    # floor that catches scanned PDFs without false-positives on
    # image-heavy-but-legitimate papers.
    if chars_per_page < 100:
        sys.stderr.write(
            f"WARNING: {args.pdf} appears scanned or image-only — "
            f"{total_chars:,} chars / {n_pages} pages = {chars_per_page:.1f} "
            f"chars/page (typical: 1,000-3,000). Extracted text will likely "
            f"be useless.\n"
        )

    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(
            f"Wrote {args.out} ({total_chars:,} chars, {n_pages} pages, "
            f"{chars_per_page:.1f} chars/page)"
        )
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
