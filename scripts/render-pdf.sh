#!/bin/bash
# render-pdf.sh — Convert peer-review-report.md to PDF via LaTeX, then clean up.
#
# Pipeline: .md -> (pandoc) -> .tex -> (xelatex ×2) -> .pdf -> remove .tex + build artifacts.
# xelatex runs twice so the TOC page numbers resolve.
#
# The .md is expected to be a YAML-frontmatter Markdown document produced by
# the peer-review skill's STEP 10 — title page, TOC, geometry, and math
# preamble are all carried in the frontmatter, not passed as -V flags here.
#
# Usage:
#     bash render-pdf.sh [path/to/peer-review-report.md]
#
# Defaults to ./peer-review-report.md if no argument given.
#
# Exit codes:
#     0 — PDF generated successfully, OR pandoc/xelatex missing (graceful skip)
#     1 — .md file not found, or LaTeX compilation failed (.tex preserved for debugging)

set -u

MD_FILE="${1:-./peer-review-report.md}"

if [ ! -f "$MD_FILE" ]; then
    echo "ERROR: $MD_FILE not found." >&2
    exit 1
fi

# Resolve absolute directory + basename (no .md extension)
DIR="$(cd "$(dirname "$MD_FILE")" && pwd)"
BASE="$(basename "$MD_FILE" .md)"

# Dependency check — warn and skip if either tool is missing. Do NOT fail
# the overall pipeline just because the user doesn't have a LaTeX install.
if ! command -v pandoc >/dev/null 2>&1; then
    echo "WARNING: pandoc not installed; skipping PDF generation." >&2
    echo "  Install with 'brew install pandoc' (macOS) or your package manager." >&2
    echo "  Final report remains at $MD_FILE." >&2
    exit 0
fi

if ! command -v xelatex >/dev/null 2>&1; then
    echo "WARNING: xelatex not installed; skipping PDF generation." >&2
    echo "  Install a LaTeX distribution (MacTeX, TeX Live, or MiKTeX)." >&2
    echo "  Final report remains at $MD_FILE." >&2
    exit 0
fi

TEX_FILE="$DIR/$BASE.tex"
PDF_FILE="$DIR/$BASE.pdf"

# Step 1: Markdown -> standalone LaTeX.
#
# All rendering options (title page, TOC, geometry, fontsize, math-package
# preamble) live in the report's YAML frontmatter, so no per-option -V flags
# are needed here.
#
# Pandoc's tex_math_dollars extension (on by default in -f markdown) preserves
# inline $...$ math as LaTeX $...$ verbatim. Escaped currency US\$50 is read as
# literal "$50" and will NOT be misinterpreted as math. Raw-LaTeX directives
# written into the .md (e.g. \newpage) also flow through untouched.
if ! pandoc -f markdown -s \
        --pdf-engine=xelatex \
        -o "$TEX_FILE" "$MD_FILE" 2>/dev/null; then
    echo "WARNING: pandoc failed to convert $MD_FILE to LaTeX; skipping PDF." >&2
    rm -f "$TEX_FILE"
    exit 1
fi

# Step 2: LaTeX -> PDF (run in DIR so build artifacts land there, not in cwd).
# xelatex runs twice: first pass writes .aux and .toc; second pass reads them
# back so the table-of-contents page numbers resolve correctly.
if ! (cd "$DIR" && \
        xelatex -interaction=nonstopmode "$BASE.tex" >/dev/null 2>&1 && \
        xelatex -interaction=nonstopmode "$BASE.tex" >/dev/null 2>&1); then
    echo "WARNING: xelatex compilation failed. Keeping $TEX_FILE for debugging." >&2
    # Clean up transient artifacts but preserve the .tex
    rm -f "$DIR/$BASE.aux" "$DIR/$BASE.log" "$DIR/$BASE.out" \
          "$DIR/$BASE.toc" "$DIR/$BASE.synctex.gz" \
          "$DIR/$BASE.fdb_latexmk" "$DIR/$BASE.fls"
    exit 1
fi

# Verify the PDF actually landed
if [ ! -f "$PDF_FILE" ]; then
    echo "WARNING: xelatex reported success but $PDF_FILE is missing." >&2
    exit 1
fi

# Step 3: Clean up all LaTeX intermediates on success
rm -f "$TEX_FILE" \
      "$DIR/$BASE.aux" "$DIR/$BASE.log" "$DIR/$BASE.out" \
      "$DIR/$BASE.toc" "$DIR/$BASE.synctex.gz" \
      "$DIR/$BASE.fdb_latexmk" "$DIR/$BASE.fls" \
      "$DIR/$BASE.nav" "$DIR/$BASE.snm" "$DIR/$BASE.vrb" \
      "$DIR/$BASE.bbl" "$DIR/$BASE.blg" "$DIR/$BASE.bcf" \
      "$DIR/$BASE.run.xml"

echo "PDF generated: $PDF_FILE"
