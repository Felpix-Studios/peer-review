# Peer Review

> **Work in Progress.** This plugin is still under active development by a university student. For now, it is an experiment on the utility of Claude Code for peer-reviewing academic papers. If you have any feedback or suggestions, reach me on X at [@felpix_](https://x.com/felpix_).

A Claude Code plugin that runs an adversarial multi-agent peer review on an academic paper PDF. Spawns a **Red Team** of specialized critics (Foundations-Critic, Empirical Auditor, Procedural Auditor, Collector, Omissions Auditor), a **Blue Team** that writes honest defenses, an **Assessor** that adjudicates between them, fact-checkers that verify quotes and citations against the PDF, and — in writer mode — an author-facing editor, proofreader, and copyeditor. Produces a structured **Credibility Assessment / Bottom Line / Potential Issues / Future Research** report.

The pipeline's effectiveness comes from the **verification cascade**: aggressive prompting drives careful reading, and downstream verifiers strip out the LLM hallucinations that aggressive prompting also produces.

## Quick Start

### 1. Install the plugin

Use Claude Code to add the marketplace and install the plugin.

```bash
/plugin marketplace add Felpix-Studios/peer-review
```

```
/plugin install peer-review@felpix-research
```

### 2. Install Python dependencies

The plugin extracts PDFs to plain text once per run (so a 15-agent pipeline doesn't re-render the same pages 15 times as images). This requires **Python 3.10+** on `PATH` as `python` and the `pypdf` package.

```bash
pip install pypdf reportlab bibtexparser
```

`reportlab` is optional — it's only used by the `compile-code-to-pdf.py` helper when you want to pack a replication-code directory into a single dense PDF for the code-audit agents. `bibtexparser` is optional — it's only used by the `parse-bib.py` helper if you supply a `.bib` file at run start (the citation-checker uses it to verify cited references against your bibliography). The plugin's regex `.bib` parser handles common entries without `bibtexparser`; install it if your bibliography uses unusual concatenations or escape sequences. Installing all three now avoids a second failure later.

> **Preflight check.** If Python or `pypdf` is missing when you run `/peer-review`, the skill halts at preflight and prints the install command — nothing is extracted, no agent is invoked, no directory is created.

### 3. Run `/peer-review`

Point the skill at a PDF. The invocation accepts free-form prose — there are no flags to parse:

```
/peer-review path/to/paper.pdf
/peer-review my paper is named "working-paper.pdf"
```

Claude will then ask a short follow-up covering:

- **Math audit** — auto-detect (default), force, or skip
- **Code audit** — whether to audit a replication directory (and if so, its path)
- **Writer mode** — include the author-facing Editor's Note + Copyediting (default on)
- **Supplementary PDFs** — any appendices or data supplements to include

Accept the defaults for a straightforward base run.

The final report is written to `./peer-review-report.md` (top of your cwd). If `pandoc` and a LaTeX distribution with `xelatex` are installed, a companion `./peer-review-report.pdf` is produced in the same directory (all LaTeX intermediates are cleaned up automatically). Every intermediate stage file — plus a `paper_text.txt` plain-text dump of the PDF and a generated `README.md` mapping each `NN_stage.txt` to its contents — is cached under `./peer-review-output/<slug>/`, a visible folder in your cwd. A partial run can be resumed by re-invoking the command: only stages whose cached file is missing will re-run.

## Prerequisites

| Tool | Required For | Install |
|------|-------------|---------|
| Claude Code (with plugin support) | Everything | [claude.ai/download](https://claude.ai/download) |
| Python (>= 3.10) on `PATH` as `python` | PDF text extraction (every run) | [python.org](https://www.python.org/) |
| `pypdf` | PDF text extraction (every run) | `pip install pypdf` |
| `reportlab` (optional) | `compile-code-to-pdf.py` helper for code-audit runs | `pip install reportlab` |
| `bibtexparser` (optional) | `parse-bib.py` helper for citation validation when a `.bib` is supplied | `pip install bibtexparser` |
| `pandoc` (optional) | PDF export of the final report | `brew install pandoc` (macOS) / `apt install pandoc` |
| LaTeX distribution with `xelatex` (optional) | PDF export of the final report | [MacTeX](https://tug.org/mactex/) / [TeX Live](https://tug.org/texlive/) / [MiKTeX](https://miktex.org/) |
| Access to Claude Opus + Sonnet | 26 agents use Opus; 9 use Sonnet | Claude Code plan |

## How It Works

The orchestrator drives a 30+ stage pipeline of subagents through a verification cascade designed to remove LLM hallucinations:

| Stage | What Happens | Agents | Output |
|-------|--------------|--------|--------|
| 0. Preflight & setup | Verify Python + `pypdf`, ask for options, extract PDF to text, pull metadata and claimed contributions | `metadata-extractor`, `contributions-extractor`, `math-page-identifier` | `paper_text.txt`, `00a_metadata.txt`, `00c_contributions.txt`, `math_pages.txt` |
| 1. Red Team | Adversarial critics attack from different angles; optional math and code audits run in parallel | `foundations-critic`, `empirical-auditor`, `procedural-auditor`, `collector`, `omissions-auditor` (+ math + code chains) | `01a_*` through `01n_summarizer.txt` |
| 2. Synthesize & defend | Verify load-bearing numbers, Blue Team writes honest defenses and classifies each issue A-G, Assessor adjudicates, Dossier Builder consolidates | `number-checker`, `blue-team`, `assessor`, `dossier-builder` | `02a_*` through `02g_list_v1.txt` |
| 3. Cross-verify | Fact-check every quote and page reference against the PDF; audit external citations for hallucinated sources | `fact-checker`, `citation-checker`, `dossier-builder` | `03a_*`, `03b_*`, `03c_list_v2.txt` |
| 4. Write narrative | Reviewer drafts the `Credibility Assessment`, `Bottom Line`, and `Future Research` sections | `reviewer`, `data-editor` (code audit only) | `04a_reviewer.txt`, `04b_data_editor.txt` |
| 5. Verify review | Two fact-check passes on the draft review, then apply corrections | `fact-checker` (×2), `review-reviser` | `05a_*`, `05b_*`, `05c_reviser.txt` |
| 6-7. Sanitize & format | Strip defamatory phrasing; enforce final structure, citation format, and inline-LaTeX math | `legal-sanitizer`, `formatter` | `06_legal.txt`, `07_formatter.txt` |
| 8-9. Writer mode (opt) | Author-facing editor's note + typo/grammar proofread of the paper + concrete copyedits | `revision-strategist`, `editor-polisher`, `paper-proofreader`, `copyeditor` | `08a_*`, `08b_*`, `09a_*`, `09b_*` |

Conditional branches (driven by your answers to the follow-up questions):

- **Theoretical papers** (`IS_EMPIRICAL: NO`) skip the Empirical Auditor, Procedural Auditor, and Collector, and run an unconditional `foundations-critic-round-2` pass instead.
- **Math audit** adds the four deep-math agents (forced, or auto-detected when `CONTAINS_ALGEBRA: YES` and the paper has displayed equations). A lightweight math sweep always runs.
- **Code audit** adds the three code hunters + code-verifier + list-compiler + data-editor.
- **Writer mode off** skips Stages 8-9.

## What's Included

**35 specialized agents** (26 Opus + 9 Sonnet), **1 skill** (`/peer-review`), **6 shared prompt fragments**, and **4 helper scripts**.

The agents split across seven role groups: Red Team adversarial critics, math-audit chain, code-audit chain, setup/synthesis, cross-verification, writing/finalization, and writer-mode (author-facing) editing. Each agent is independently usable via `@<agent-name>`; the full pipeline runs them through a verification cascade orchestrated by `/peer-review`.

The canonical per-agent breakdown — name, role, model, stage filename it writes, conditional flags, and where it sits in the pipeline — lives in `skills/peer-review/SKILL.md` under the "Run README" file table. To find it, open SKILL.md and search for `paper_text.txt`; the table begins on the next line. The prompt-fragment injection mapping (which agents receive which shared fragment) is in the same file under "Fragment → agent mapping". When agents are added or renamed, only SKILL.md needs updating — this README does not.

Helper scripts live in `scripts/`: `extract-pdf-text.py` (PDF → text, one call per run), `compile-code-to-pdf.py` (replication directory → single PDF, called when code-audit is on), `parse-bib.py` (`.bib` → JSON for citation validation, called when a `.bib` is supplied), and `render-pdf.sh` (Markdown report → PDF via pandoc + xelatex, called at the end of every run).

## Limitations

- The pipeline produces a **critique, not a verdict**. Human expert judgement is always required for final decisions.
- The Red Team is intentionally adversarial; without the verification cascade it would over-produce false positives.
- **Visual evidence** (interpreting datapoints from inside figures or plots) is strictly forbidden by every agent — chart-only evidence is filtered out.
- The **math audit** relies on the Re-Deriver and the Math Verifier correcting each other's blind spots; for very subtle algebra, a human mathematician is irreplaceable.
- The **code audit** reads code statically — it does not execute it.

## License and Attribution

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

This plugin adapts prompt and pipeline structure from
[reviewer2](https://github.com/isitcredible/reviewer2), which is licensed
under Apache-2.0 by The Catalogue of Errors Ltd.

Modifications in this repository are Copyright 2026 Felpix Studios. The
project uses the reviewer2 pipeline as the basis for a Claude Code plugin,
adapts prompts for agent use, removes the original Python/Gemini orchestration,
adds local helper scripts for Claude Code tooling, and adds Claude plugin
metadata.

The names "Reviewer 2", "isitcredible.com", and "The Catalogue of Errors"
are trademarks of The Catalogue of Errors Ltd and are not licensed under
Apache-2.0.
