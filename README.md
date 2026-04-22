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
pip install pypdf reportlab
```

`reportlab` is optional — it's only used by the `compile-code-to-pdf.py` helper when you want to pack a replication-code directory into a single dense PDF for the code-audit agents. Installing both now avoids a second failure later if you enable the code audit.

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
| `pandoc` (optional) | PDF export of the final report | `brew install pandoc` (macOS) / `apt install pandoc` |
| LaTeX distribution with `xelatex` (optional) | PDF export of the final report | [MacTeX](https://tug.org/mactex/) / [TeX Live](https://tug.org/texlive/) / [MiKTeX](https://miktex.org/) |
| Access to Claude Opus + Sonnet | 30 agents use Opus; 5 use Sonnet | Claude Code plan |

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

<details>
<summary><strong>35 agents, 1 skill, 5 shared prompt fragments, 3 helper scripts</strong> (click to expand)</summary>

### Skill

| Skill | What It Does |
|-------|-------------|
| `/peer-review` | Orchestrate the full Red Team → Blue Team → Assessor → Reviewer cascade on an academic paper PDF |

### Agents — Red Team (adversarial critique)

| Agent | What It Does |
|-------|-------------|
| `foundations-critic` | Interrogates theoretical foundations and research design |
| `foundations-critic-round-2` | Second foundations pass for non-empirical papers; finds issues Round 1 missed |
| `empirical-auditor` | Dissects empirical machinery: design, measures, analytical decisions, effect-size interpretation |
| `procedural-auditor` | Verifies the paper actually did what it claimed, based only on documented evidence |
| `collector` | Returns to flagged locations and exhaustively collects overlooked details (footnotes, table notes, supplements) |
| `omissions-auditor` | Discovers what the paper *doesn't* say: unmeasured confounds, missing robustness checks, alternative explanations |

### Agents — Math audit

| Agent | What It Does |
|-------|-------------|
| `math-page-identifier` | Locate PDF pages containing equations, proofs, or derivations |
| `math-error-finder` | Lightweight sweep: arithmetic, table totals, calibration numbers (always on unless the paper has no math) |
| `re-deriver` | Independently re-derive proofs from first definitions |
| `math-proofreader` | Check text-equation consistency |
| `math-auditor` | Framework-level audit of the mathematical approach |
| `math-verifier` | Sift math findings and keep only the verified issues |

### Agents — Code audit

| Agent | What It Does |
|-------|-------------|
| `paper-code-auditor` | Find paper-code gaps |
| `bug-hunter` | Find bugs in the replication code |
| `data-construction-auditor` | Find errors in the data pipeline |
| `code-verifier` | Verify code issues from the three hunters |
| `code-list-compiler` | Compile the final code issue list |
| `data-editor` | Write the code/data analysis paragraph for the review |

### Agents — Setup and synthesis

| Agent | What It Does |
|-------|-------------|
| `metadata-extractor` | Pull citation, document type, empirical/theoretical flag, algebra flag, page structure |
| `contributions-extractor` | Extract the paper's claimed contributions in descending order of importance |
| `red-team-summarizer` | Deduplicate and consolidate Red Team findings |
| `number-checker` | Verify load-bearing numbers; filter prohibited visual-evidence issues |
| `blue-team` | Write honest defenses for every issue; classify A-G (mistake, acknowledged, clerical, structural, visual, feature, other) |
| `assessor` | Adjudicate Red vs Blue per issue |
| `dossier-builder` | Build the preliminary and final verified issue dossier |

### Agents — Cross-verification

| Agent | What It Does |
|-------|-------------|
| `fact-checker` | Verify quotes, page references, and figure/table citations against the PDF |
| `citation-checker` | Audit external-source attributes for hallucinated references |

### Agents — Writing and finalization

| Agent | What It Does |
|-------|-------------|
| `reviewer` | Write the integrated narrative review in the voice of a rigorous, fair, epistemically humble senior peer reviewer — impervious to prestige and politics, focused on research design and logic over narrative |
| `review-reviser` | Apply fact-check corrections to the draft review |
| `legal-sanitizer` | Scan for defamatory phrasing across four red lines |
| `formatter` | Enforce final structure, citation format, sentence-case labels, and inline-LaTeX math |

### Agents — Writer mode (author-facing)

| Agent | What It Does |
|-------|-------------|
| `revision-strategist` | Write the author-facing revision strategy plus secret copyeditor instructions |
| `editor-polisher` | Polish the final Editor's Note |
| `paper-proofreader` | Typo/grammar/punctuation list for the paper itself |
| `copyeditor` | Concrete revision suggestions implementing the revision-strategist's strategy |

### Shared prompt fragments

Single source of truth for cross-agent guardrails. The orchestrator reads each once and injects the text inline into every applicable sub-agent's task prompt — agent files do not contain this content.

| Fragment | Injected Into |
|----------|-------------|
| `hallucination-guards.md` | Every agent that reads the paper |
| `issue-types.md` | Blue Team, Assessor, Dossier Builder |
| `output-format.md` | Reviewer, Review Reviser, Dossier Builder, Formatter |
| `voice-and-tone.md` | Reviewer, Copyeditor, and author-facing agents |
| `page-reference.md` | Every PDF-reading agent that cites page numbers |

### Helper scripts

| Script | What It Does |
|--------|-------------|
| `extract-pdf-text.py` | Extract page-marked plain text from a PDF (requires `pypdf`). Called once per run. |
| `compile-code-to-pdf.py` | Pack a replication-code directory into a single dense PDF (requires `reportlab`). Optional. |
| `render-pdf.sh` | Convert the final `peer-review-report.md` to PDF via `pandoc` + `xelatex`, then clean up LaTeX intermediates. Gracefully skips if either tool is missing. |

</details>

## Limitations

- The pipeline produces a **critique, not a verdict**. Human expert judgement is always required for final decisions.
- The Red Team is intentionally adversarial; without the verification cascade it would over-produce false positives.
- **Visual evidence** (interpreting datapoints from inside figures or plots) is strictly forbidden by every agent — chart-only evidence is filtered out.
- The **math audit** relies on the Re-Deriver and the Math Verifier correcting each other's blind spots; for very subtle algebra, a human mathematician is irreplaceable.
- The **code audit** reads code statically — it does not execute it.

## License

MIT. See [LICENSE](LICENSE).
