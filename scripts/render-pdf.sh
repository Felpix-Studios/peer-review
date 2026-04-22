#!/bin/bash
# render-pdf.sh — Convert peer-review-report.md to PDF via LaTeX, then clean up.
#
# Pipeline: .md -> (pandoc) -> .tex -> (xelatex) -> .pdf -> remove .tex + build artifacts.
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
# Preprocessing via sed: convert any line of 3+ ═ box-drawing chars to Markdown
# HR (---) so pandoc renders them as \hrulefill rather than literal glyphs that
# xelatex may not have in its fonts. LC_ALL forces a UTF-8 locale so the
# multi-byte ═ character matches correctly regardless of the inherited locale.
#
# Pandoc options:
#   --pdf-engine=xelatex        tell pandoc's template to emit xelatex-compatible
#                               preamble (loads fontspec, handles Unicode properly)
#   -V header-includes=...      explicitly load amsmath, amssymb, amsthm, and
#                               mathtools so reviewer math (`\mathbb{R}`,
#                               `\begin{pmatrix}`, `\overset`, etc.) all resolve
#                               regardless of pandoc's auto-detection
#   -V geometry:margin=1in      decent margins for an academic-review document
#   -V fontsize=11pt            readable body text
#
# Pandoc's tex_math_dollars extension (on by default in -f markdown) preserves
# inline $...$ math as LaTeX $...$ verbatim. Escaped currency US\$50 is read as
# literal "$50" and will NOT be misinterpreted as math.
if ! LC_ALL=en_US.UTF-8 sed -E 's/^═{3,}$/---/' "$MD_FILE" | \
        pandoc -f markdown -s \
            --pdf-engine=xelatex \
            -V header-includes='\usepackage{amsmath,amssymb,amsthm,mathtools}' \
            -V geometry:margin=1in \
            -V fontsize=11pt \
            -o "$TEX_FILE" 2>/dev/null; then
    echo "WARNING: pandoc failed to convert $MD_FILE to LaTeX; skipping PDF." >&2
    rm -f "$TEX_FILE"
    exit 1
fi

# Step 2: LaTeX -> PDF (run in DIR so build artifacts land there, not in cwd)
if ! (cd "$DIR" && xelatex -interaction=nonstopmode "$BASE.tex" >/dev/null 2>&1); then
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
