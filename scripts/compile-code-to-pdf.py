#!/usr/bin/env python3
# Copyright 2026 Felpix Studios
#
# Licensed under the Apache License, Version 2.0. See LICENSE.

"""
Walk a code directory and compile every text file into a single dense PDF for
the code-audit agents (paper-code-auditor, bug-hunter, data-construction-auditor).

Uses a dense single-column 7pt Courier layout so a 500-page limit
comfortably holds most replication packages.

Usage:
    python compile-code-to-pdf.py <code-dir> --out code.pdf [--max-bytes 5000000]
"""

import argparse
import sys
from pathlib import Path

CODE_EXTENSIONS = {
    ".py", ".r", ".R", ".do", ".m", ".jl", ".ipynb", ".sql",
    ".sh", ".bash", ".zsh",
    ".js", ".ts", ".jsx", ".tsx",
    ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".java", ".scala",
    ".pl", ".rb",
    ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg",
    ".md", ".rst", ".txt", ".tex",
    ".csv", ".tsv",
    ".gitignore", ".env",
}

# Suppress generated/binary directories
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".idea", ".vscode", ".pytest_cache", "dist", "build", ".tox",
    "renv", "packrat",
}


def collect(root: Path, max_bytes: int) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    total = 0
    for p in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_dir():
            continue
        if p.suffix.lower() not in CODE_EXTENSIONS and p.name not in CODE_EXTENSIONS:
            continue
        try:
            data = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        size = len(data.encode("utf-8"))
        if total + size > max_bytes:
            sys.stderr.write(
                f"Reached {max_bytes:,} byte cap; skipping {p} and the rest.\n"
            )
            break
        out.append((p.relative_to(root), data))
        total += size
    return out


def to_pdf(files: list[tuple[Path, str]], out_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        sys.stderr.write(
            "reportlab is not installed. Install with `pip install reportlab`.\n"
        )
        sys.exit(1)

    c = canvas.Canvas(str(out_path), pagesize=letter)
    width, height = letter
    margin_x = 36  # 0.5 inch
    margin_y = 36
    leading = 8.5
    font_size = 7.0
    line_w = int((width - 2 * margin_x) / (font_size * 0.6))  # rough char width

    c.setFont("Courier-Bold", 9)
    c.drawString(margin_x, height - margin_y, "FILE MAP")
    y = height - margin_y - 14
    c.setFont("Courier", 7)
    for idx, (p, _) in enumerate(files, 1):
        if y < margin_y:
            c.showPage()
            c.setFont("Courier", 7)
            y = height - margin_y
        c.drawString(margin_x, y, f"{idx:4d}  {p}")
        y -= leading

    for p, content in files:
        c.showPage()
        c.setFont("Courier-Bold", 9)
        c.drawString(margin_x, height - margin_y, f"=== {p} ===")
        c.setFont("Courier", font_size)
        y = height - margin_y - 14
        for raw_line in content.splitlines():
            # rough wrap
            chunks = (
                [raw_line[i : i + line_w] for i in range(0, len(raw_line), line_w)]
                if raw_line
                else [""]
            )
            for chunk in chunks:
                if y < margin_y:
                    c.showPage()
                    c.setFont("Courier-Bold", 9)
                    c.drawString(margin_x, height - margin_y, f"=== {p} (cont.) ===")
                    c.setFont("Courier", font_size)
                    y = height - margin_y - 14
                # PDF-safe: replace tabs and stray non-printables
                safe = chunk.replace("\t", "    ").encode("latin-1", "replace").decode("latin-1")
                c.drawString(margin_x, y, safe)
                y -= leading

    c.save()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("code_dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-bytes", type=int, default=5_000_000)
    args = ap.parse_args()

    if not args.code_dir.is_dir():
        sys.exit(f"Not a directory: {args.code_dir}")

    files = collect(args.code_dir, args.max_bytes)
    if not files:
        sys.exit("No code files found.")
    to_pdf(files, args.out)
    print(f"Wrote {args.out} ({len(files)} files).")


if __name__ == "__main__":
    main()
