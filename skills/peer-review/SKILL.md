---
name: peer-review
description: Adversarial multi-agent peer review of an academic paper PDF. Use when the user invokes /peer-review, or asks to peer-review, critique, evaluate, or red-team an academic paper. Orchestrates a Red Team → Blue Team → Assessor → Reviewer verification cascade (~20 subagents) with optional math and code audits, producing a structured peer-review report.
allowed-tools: Read, Write, Glob, Grep, Bash, Task, AskUserQuestion
---

# Peer Review — adversarial multi-agent orchestrator

You are the orchestrator of the peer-review pipeline. You coordinate ~20 specialized subagents through a verification cascade designed to remove LLM hallucinations and produce a fair-but-rigorous assessment of an academic paper.

## When this skill fires

Invoke this skill when the user:
- Types `/peer-review ...` (e.g. `/peer-review my paper is named "working-paper.pdf"`).
- Asks to peer-review, critique, red-team, evaluate, or "tear apart" an academic paper PDF.
- Drops a `.pdf` into the conversation with intent to review it.

The user's invoking message is free-form prose — there are no flags to parse. Before doing anything else, run the Preflight check below. Only if it passes, proceed to STEP 0 to identify the PDF and collect options via AskUserQuestion.

## Preflight — verify Python and required packages

**Run this check first — before asking the user any questions, before creating any directory, before invoking any agent.** If it fails, stop the pipeline and tell the user what to install.

Run this single `Bash` command:

```bash
python -c "import sys; print('PY_OK' if sys.version_info >= (3, 10) else 'PY_OLD'); import importlib.util; print('PYPDF_OK' if importlib.util.find_spec('pypdf') else 'PYPDF_MISSING')" 2>&1
```

Possible failures:
- **`python: command not found`** (or any shell error) → Python is missing or not on `PATH` as `python`. (If the user only has `python3`, that is also a failure — STEP 1a invokes `python` directly.)
- **`PY_OLD`** → Python is older than 3.10. The helper scripts use PEP 604 `str | None` syntax and require 3.10+.
- **`PYPDF_MISSING`** → the `pypdf` package is not importable. Required for the PDF text extraction at STEP 1a.

If any check fails, do NOT proceed — do not call `AskUserQuestion`, do not create the work directory, do not invoke any agent. Print exactly this message to the user and stop:

> **Cannot start peer-review — missing dependency.**
>
> This plugin needs **Python 3.10+** with **`pypdf`** installed. Please install the required packages and then re-run `/peer-review`:
>
> ```bash
> pip install pypdf reportlab
> ```
>
> (`reportlab` is only used by the optional `compile-code-to-pdf.py` helper for the code audit, but installing both now avoids a second failure later.)

Only if the command returns `PY_OK` and `PYPDF_OK`, continue.

### Advisory: PDF export tooling (non-blocking)

After the required check passes, run these two additional checks:

```bash
command -v pandoc >/dev/null 2>&1 && echo "PANDOC_OK" || echo "PANDOC_MISSING"
command -v xelatex >/dev/null 2>&1 && echo "XELATEX_OK" || echo "XELATEX_MISSING"
```

If either reports `_MISSING`, proceed anyway — the `.md` report will still be produced, but the optional STEP 11 PDF export will be skipped. Tell the user once, upfront:

> *PDF export will be skipped (`pandoc` or `xelatex` is not installed). The Markdown report will still be written. To enable the PDF: install `pandoc` (`brew install pandoc`) and a LaTeX distribution (MacTeX / TeX Live / MiKTeX).*

These advisory checks never halt the pipeline. After running them, continue to STEP 0.

## STEP 0 — Identify the PDF and gather options

### 0a. Find the PDF path

Scan the user's invoking message for a `.pdf` reference:
- Quoted filename: `"working-paper.pdf"`, `'paper.pdf'`
- Bare path: `./papers/smith-2024.pdf`, `~/Desktop/draft.pdf`
- Just a filename: `working-paper.pdf` (resolve relative to cwd)

Resolve the path. If it does not exist, try common nearby locations (cwd, `~/Desktop`, `~/Downloads`) before asking.

If no PDF can be identified, ask the user in plain text for the path. **Do not proceed without a PDF.**

### 0b. Collect options (single AskUserQuestion call)

Call `AskUserQuestion` **once** with these four bundled questions (follow the tool's 1–4 questions / 2–4 options constraint):

```
Q1 — header: "Math audit"
  - "Auto-detect (Recommended)" — run the 4 deep math agents only if
    metadata-extractor reports CONTAINS_ALGEBRA=YES and the paper has
    displayed equations. A lightweight math sweep (arithmetic, table
    totals, calibrations) runs in every pipeline regardless of this
    choice.
  - "Force math audit" — always run the 4 deep math agents on top of
    the lightweight sweep.
  - "Skip math audit" — never run the deep math agents. The lightweight
    sweep still runs if the paper has any mathematical content.

Q2 — header: "Code audit"
  - "No replication code (Recommended)" — skip the code hunters.
  - "Yes — I have a replication directory" — run the 5 code-audit agents.

Q3 — header: "Writer mode"
  - "Yes — include editor's note + copyedit (Recommended)" — run Stages 8-9.
  - "No — skip writer mode" — stop after Stage 7.

Q4 — header: "Supp PDFs"
  - "None (Recommended)" — main PDF only.
  - "Yes — I will list them" — add supplementary PDFs.
```

All four questions are single-select (`multiSelect: false`). The user can always override any choice via the auto-provided "Other" free-text option.

### 0c. Follow-up prompts for free-form input

- If Q2 = "Yes", ask in plain text: *"What's the path to the replication code directory?"* Save as `code_dir`.
- If Q4 = "Yes", ask in plain text: *"List the supplementary PDF paths (one per line)."* Save as `supplements` (array).
- If the user's opening message already contained an explicit citation (e.g. *"cite this as Smith (2024)..."*), capture it as `citation_override`. Otherwise leave blank — metadata-extractor will supply the citation.

### 0d. Derive defaults

- `slug` = basename of the PDF without extension, lowercased, non-alphanumerics → `-`.
- `work_dir` = `./peer-review-output/<slug>/` — **visible folder in the user's cwd**, not a dotfile.
- `out` = `./peer-review-report.md` — stays at the top of the user's cwd for easy access.
- `pdf_text_path` = `<work_dir>/paper_text.txt` — populated in STEP 1a; may be set to `None` if extraction fails.
- `is_math` = one of `auto | force | skip` (from Q1)
- `run_code_audit` = boolean (from Q2)
- `writer_mode` = boolean (from Q3, default true)

### 0e. Prepare workspace

```bash
mkdir -p <work_dir>
```

Tell the user in one line what's about to happen and quote the work-dir path so they can resume later:

> "Starting peer-review. Intermediate outputs cached in `./peer-review-output/<slug>/` — a visible folder in your current directory. Re-invoke with the same PDF to resume from cached stages. Final report will be written to `./peer-review-report.md`."

### 0f. Resumability check

Each downstream stage writes its output to `<work_dir>/<stage>.txt`. Before invoking any agent, check whether its cached output file exists:
- If yes → skip the agent, read the cached file.
- If no → invoke the agent, `Write` its output to the cached path, continue.

To re-run a single stage, the user deletes its file (and any downstream files) and re-invokes `/peer-review` with the same PDF.

## Plugin resources (portable paths)

All plugin-internal paths below use `${CLAUDE_PLUGIN_ROOT}` so sub-agent `Task` invocations remain portable regardless of the user's cwd.

- **Shared prompt fragments** (single source of truth for cross-agent guardrails; injected inline — see next section):
  - `${CLAUDE_PLUGIN_ROOT}/prompts/hallucination-guards.md`
  - `${CLAUDE_PLUGIN_ROOT}/prompts/issue-types.md`
  - `${CLAUDE_PLUGIN_ROOT}/prompts/output-format.md`
  - `${CLAUDE_PLUGIN_ROOT}/prompts/voice-and-tone.md`
  - `${CLAUDE_PLUGIN_ROOT}/prompts/page-reference.md` — dynamic; `{PAGE_STRUCTURE}` and `{SUPPLEMENT_START_PAGE}` placeholders are filled from the metadata dict after STEP 1c, then the filled text is injected into every PDF-reading agent that cites page numbers.
- **Helper scripts** (invoked via `Bash`):
  - `${CLAUDE_PLUGIN_ROOT}/scripts/extract-pdf-text.py` — extract plain text from a PDF when an agent needs it without image/layout overhead.
  - `${CLAUDE_PLUGIN_ROOT}/scripts/compile-code-to-pdf.py` — bundle a replication directory into a single PDF for the code-audit agents.

## Prompt fragment injection

The five fragments above are the single source of truth for guardrails that apply across multiple sub-agents. **Agent files do NOT contain this content** — instead, you (the orchestrator) Read each fragment once at the start of the run and inline its text as a preamble to every applicable sub-agent's Task prompt. Do not pass paths.

### When to read

At the start of STEP 1, before invoking `@metadata-extractor`, `Read` each of the five fragments and hold the text in memory for the rest of the run. Do not re-read per invocation. The `page-reference.md` template is cached raw; its placeholders are filled after STEP 1c (see the STEP 1b / 1c sections below).

### Fragment → agent mapping

| Fragment | Inject into |
|----------|-------------|
| `hallucination-guards.md` | foundations-critic, foundations-critic-round-2, empirical-auditor, procedural-auditor, collector, omissions-auditor, math-error-finder, re-deriver, math-proofreader, math-auditor, math-verifier, paper-code-auditor, bug-hunter, data-construction-auditor, code-verifier, code-list-compiler, number-checker, fact-checker, citation-checker, red-team-summarizer, blue-team, assessor, dossier-builder, reviewer |
| `issue-types.md` | blue-team, assessor, dossier-builder |
| `output-format.md` | reviewer, review-reviser, dossier-builder, formatter |
| `voice-and-tone.md` | reviewer, review-reviser, formatter, revision-strategist, editor-polisher, copyeditor, dossier-builder, data-editor, code-list-compiler |
| `page-reference.md` | foundations-critic, foundations-critic-round-2, empirical-auditor, procedural-auditor, collector, omissions-auditor, math-error-finder, re-deriver, math-proofreader, math-auditor, math-verifier, number-checker, fact-checker, citation-checker, blue-team, assessor, dossier-builder, reviewer, review-reviser, revision-strategist, copyeditor, paper-proofreader |

**No injection:** metadata-extractor, contributions-extractor, math-page-identifier, legal-sanitizer, data-editor, editor-polisher, red-team-summarizer, paper-code-auditor, bug-hunter, data-construction-auditor, code-verifier, code-list-compiler (mechanical tasks, code-only stages, or self-contained tasks — fragments do not apply).

### Injection format

Prefix each applicable sub-agent's Task prompt with:

```
---
# Shared guardrails

## Hallucination Guards
<verbatim contents of hallucination-guards.md>

## Issue Type Classification
<verbatim contents of issue-types.md>

## Output Format
<verbatim contents of output-format.md>

## Voice and Tone
<verbatim contents of voice-and-tone.md>

## Page Number Reference
<contents of page-reference.md, with {PAGE_STRUCTURE} and
 {SUPPLEMENT_START_PAGE} replaced by the values from the metadata dict>

---

# Your task
<agent-specific task description and inputs>
```

Include ONLY the fragments listed for that agent in the mapping. Consult the mapping table on every invocation. The `page-reference.md` fragment is the only one with placeholders — every other fragment is injected verbatim.

## Paper text dump

A single plain-text dump of the paper PDF is produced once per run (at STEP 1a) and passed to every PDF-reading agent alongside the PDF path itself. It's the primary source for text-scanning; the PDF is reserved for visual content.

### Why

Reading PDF pages via Claude's `Read` tool renders them as images (~1,500+ image tokens per page, and a 20-page cap per `Read` call). For a 40-page paper examined by 15+ agents, that's prohibitive. A one-time text extraction amortizes the cost across the whole pipeline.

### Format

Each page is preceded by `[Page N]` on its own line; pages are separated by blank lines. `Grep "\[Page 7\]"` locates page 7.

### How to pass to agents

When invoking any agent that receives the paper, include in the Task prompt:
- The paper PDF path (always).
- The `pdf_text_path` (omit if `None` — see STEP 1a failure modes).
- The directive:
  > "Prefer the text dump for scanning, quote verification, and long-form reading. `Read` PDF pages only when visual layout matters (tables, figures, equations)."

**Math agents** (`math-error-finder`, `re-deriver`, `math-proofreader`, `math-auditor`, `math-verifier`) get a stronger directive:
  > "The text dump is prose context only. Always verify equations against the PDF because pypdf extraction garbles math. You have been given a `math_pages` list — use `Read` on those specific PDF page numbers to invoke Claude's multimodal vision for equations, proofs, and tables. Do not waste image tokens on non-math pages."

**Code audit agents** (`paper-code-auditor`, `bug-hunter`, `data-construction-auditor`, `code-verifier`) treat the PDF (and text dump) as paper-context only; their primary source is the replication code directory.

### Agents that receive neither PDF nor text dump

`formatter`, `legal-sanitizer`, `data-editor`, `code-list-compiler`, `editor-polisher`, `red-team-summarizer` — their inputs are downstream artifacts (citation, prior-stage outputs), not the paper.

### Supplements

If the user provided supplementary PDFs, each gets its own text dump alongside the main paper's (`supp_<slug>_text.txt`). Red Team agents that read supplements (`foundations-critic`, `empirical-auditor`, `procedural-auditor`, `collector`, `omissions-auditor`) receive both the supplement PDF paths and the parallel `supp_text_paths` — each supplement entry in `supp_text_paths` may be `None` if that file's extraction was flagged scanned or failed, in which case the agent falls back to the PDF alone for that supplement.

## STEP 1 — Stage 0 setup

### 1a. Extract PDF (and any supplements) to text dumps

Before any agent runs, produce a plain-text dump of the main PDF and of every supplement the user provided. All dumps land in `<work_dir>`. Supplements are named `supp_<slug>_text.txt`, where `<slug>` is the basename of the supplement PDF (lowercased, non-alphanumerics → `-`; if two supplements produce the same slug, append `-01`, `-02`, …).

```bash
# Main paper
python ${CLAUDE_PLUGIN_ROOT}/scripts/extract-pdf-text.py \
    "<pdf_path>" --out "<work_dir>/paper_text.txt"

# Each supplement (repeat once per entry in <supplements>)
python ${CLAUDE_PLUGIN_ROOT}/scripts/extract-pdf-text.py \
    "<supp_path>" --out "<work_dir>/supp_<slug>_text.txt"
```

After every extraction, the script prints a summary line to stdout, e.g.:

```
Wrote <work_dir>/paper_text.txt (82,417 chars, 42 pages, 1,962.0 chars/page)
```

If `chars_per_page < 100`, the script also emits a stderr warning that begins with `"WARNING: … appears scanned or image-only …"`.

Populate `pdf_text_path` (main paper) and `supp_text_paths` (a parallel list to `supplements`; each entry is the dump path or `None` if that file failed / is scanned).

**Failure modes** (apply independently to the main paper and each supplement):

- **Resumability:** if the target output file already exists and is non-empty, skip re-extraction for that PDF.
- **`pypdf` missing:** the script exits with `"pypdf is not installed."` Warn the user (`pip install pypdf`), set *all* text-dump paths to `None`, and continue with PDF-only reads downstream.
- **Scanned / image-only PDF:** on the script's stderr warning ("appears scanned or image-only"), relay the warning verbatim to the user and set that file's text-dump path to `None`. Other supplements continue unaffected.
- **On success:** log the script's stdout line so the user sees the chars-per-page figure.

### 1b. Read the five prompt fragments

Read each of `hallucination-guards.md`, `issue-types.md`, `output-format.md`, `voice-and-tone.md`, and `page-reference.md` from `${CLAUDE_PLUGIN_ROOT}/prompts/` and cache the text in memory. The first four are used verbatim. The `page-reference.md` fragment has two placeholders (`{PAGE_STRUCTURE}`, `{SUPPLEMENT_START_PAGE}`) — hold the raw template here; you will fill the placeholders after STEP 1c once the metadata dict is populated, then use the filled version for every subsequent sub-agent invocation.

### 1c. Invoke `@metadata-extractor`

Invoke with the PDF path and `pdf_text_path`. Save output to `00a_metadata.txt`. Parse the `CITATION:`, `IS_EMPIRICAL:`, `CONTAINS_ALGEBRA:`, `DOCUMENT_TYPE:`, `PAGE_STRUCTURE:`, and `SUPPLEMENT_START_PAGE:` fields. Persist as `00b_metadata.json` for downstream agents.

If `citation_override` was collected in Step 0c, use that string as the citation in all downstream agent prompts instead of the extracted one.

**Fill the page-reference template** now: substitute `{PAGE_STRUCTURE}` and `{SUPPLEMENT_START_PAGE}` in the cached `page-reference.md` text with the parsed values (fall back to `"NULL — treat the printed page number as whatever appears in the PDF header/footer"` if either metadata field is missing). Use this filled text as the fifth guardrail fragment for all subsequent injections.

### 1d. Write the run README

Use `Write` to produce `<work_dir>/README.md`. This documents the run for the user. Always overwrite on re-invocation (option flags may have changed).

Include:
- Paper path, citation (from 1c), ISO run timestamp.
- Options summary: `math audit: <auto/force/skip>`, `code audit: <on/off>`, `writer mode: <on/off>`, `supplements: <count or "none">`, `replication dir: <path or "none">`.
- Final-report path (`<out>`).
- A file table with one row per stage artifact that **will actually be produced** given the flags. Skip the deep-math rows (`01fa`–`01fd`) if `run_deep_math_audit == false`. Skip the Math Error Finder row (`01e_math.txt`) only if `math_pages == NONE`. Skip code rows if `run_code_audit == false`. Skip empirical-only rows (Empirical Auditor / Procedural Auditor / Collector) if `is_empirical == false`. Skip the Foundations-Critic Round 2 row (`01a_2_breaker_revisit.txt`) if `is_empirical == true`. Skip writer-mode rows (`08a`, `08b`, `08c`, `09a`, `09b`) if `writer_mode == false`. Keep rows ordered by stage number.
- A resumability note: "Delete any file above to force that stage (and all downstream stages) to re-run."

Rows to include in the table (all possible, filter by flags). If supplements were provided, insert one row per supplement text dump directly after the `paper_text.txt` row, using the name pattern `supp_<slug>_text.txt` and the description "Plain-text dump of supplement `<basename>.pdf`":

| File | Contents |
|------|----------|
| `paper_text.txt` | pypdf-extracted text dump of the PDF with `[Page N]` markers |
| `supp_<slug>_text.txt` × N | Plain-text dump of each supplement `<basename>.pdf` *(only if supplements were provided)* |
| `00a_metadata.txt` | Paper metadata (citation, doc type, empirical/theoretical, algebra flag, page structure, supplement start page) |
| `00b_metadata.json` | Parsed canonical metadata dict (field/value pairs with any `citation_override` applied); the downstream-agent source of truth for citation, `IS_EMPIRICAL`, `PAGE_STRUCTURE`, etc. |
| `00c_contributions.txt` | Claimed contributions in descending order of importance |
| `math_pages.txt` | Math Page Identifier — compact list of PDF pages containing equations, proofs, or derivations |
| `01a_breaker.txt` | Foundations-Critic — theoretical-foundations critique |
| `01a_2_breaker_revisit.txt` | Foundations-Critic Round 2 — deeper foundations pass finding issues Round 1 missed *(non-empirical only)* |
| `01g_the_void.txt` | Omissions Auditor — omissions and unmeasured confounds |
| `01e_math.txt` | Math Error Finder — lightweight math sweep (arithmetic, table totals, calibrations). Runs unless `math_pages == NONE`. |
| `01b_butcher.txt` | Empirical Auditor — empirical-machinery dissection *(empirical only)* |
| `01c_shredder.txt` | Procedural Auditor — procedural-integrity audit *(empirical only)* |
| `01d_collector.txt` | Collector — details from flagged locations *(empirical only)* |
| `01fa_math_check.txt` | Re-Deriver — independent re-derivation *(deep math audit only)* |
| `01fb_math_proofread.txt` | Math Proofreader — text-equation consistency *(deep math audit only)* |
| `01fc_math_audit.txt` | Math Auditor — framework-level audit *(deep math audit only)* |
| `01fd_math_sober.txt` | Math Verifier — verified math issues *(deep math audit only)* |
| `01h_code_gonzo.txt` | Paper-Code Auditor — paper-code gaps *(code audit)* |
| `01i_code_gonzo_b.txt` | Bug Hunter — code bugs *(code audit)* |
| `01j_code_gonzo_c.txt` | Data-Construction Auditor — data-pipeline errors *(code audit)* |
| `01k_code_compiler.txt` | Consolidated code issues *(code audit)* |
| `01l_code_checker.txt` | Code Verifier — verified code issues *(code audit)* |
| `01m_code_list.txt` | Code List Compiler — final code issue list *(code audit)* |
| `01n_summarizer.txt` | Red Team Summarizer — deduplicated issue list |
| `02a_numbers.txt` | Number Checker — verified load-bearing numbers |
| `02b_compiler_1.txt` | Compiled list after number corrections (mechanical) |
| `02c_blue_team.txt` | Blue Team — honest defenses with Type A-G classifications |
| `02d_compiler_2.txt` | List with Blue Team defenses merged (mechanical) |
| `02e_assessment.txt` | Assessor — per-issue adjudication |
| `02f_compiler_3.txt` | List with assessments merged (mechanical) |
| `02g_list_v1.txt` | Dossier Builder — preliminary final list |
| `03a_checker_1.txt` | Fact Checker — quote/page verification on dossier |
| `03b_external.txt` | Citation Checker — external-source hallucination audit |
| `03c_list_v2.txt` | Dossier Builder — final verified list |
| `04a_reviewer.txt` | Reviewer — narrative review (three sections) |
| `04b_data_editor.txt` | Data Editor — code/data analysis paragraph *(code audit)* |
| `05a_checker_2.txt` | Fact Checker — draft review fact-check |
| `05b_checker_3.txt` | Fact Checker — page-refs and quotes focus pass |
| `05c_reviser.txt` | Review Reviser — corrections applied |
| `06_legal.txt` | Legal Sanitizer — defamation/legal-risk scan |
| `07_formatter.txt` | Formatter — final formatted review |
| `08a_alchemist.txt` | Revision Strategist — raw output containing both the author-facing revision advice and the secret copyeditor instructions, joined by the `===COPYEDITOR_INSTRUCTIONS===` separator *(writer mode)* |
| `08b_polisher.txt` | Editor Polisher — polished Editor's Note *(writer mode)* |
| `08c_alchemist_instructions.txt` | Revision Strategist's secret copyeditor instructions — the text below the separator in `08a_alchemist.txt`, persisted standalone for `@`-reference at the copyeditor stage *(writer mode)* |
| `09a_proofread.txt` | Paper Proofreader — typo/grammar list for the author (or `No proofreading issues were found.`) *(writer mode)* |
| `09b_copyedit.txt` | Copyeditor — concrete revision suggestions *(writer mode)* |

### Stage-code numbering

Stage codes are contiguous within each stage — no gaps in the letter sequence. This diverges from the upstream `reviewer2` Gemini pipeline, which has legacy gaps at `01h` (between the paper-audit and code-audit chains) and `09b` (a data-sanitizer stage absorbed into `@paper-proofreader`'s prompt in this port). Claude Code closed those gaps by renumbering the code-audit chain down one letter and the copyeditor down one letter.

When porting behavior changes between the two pipelines, consult this mapping:

| Upstream name | This plugin's name |
|---------------|--------------------|
| `01i_code_gonzo.txt` | `01h_code_gonzo.txt` |
| `01j_code_gonzo_b.txt` | `01i_code_gonzo_b.txt` |
| `01k_code_gonzo_c.txt` | `01j_code_gonzo_c.txt` |
| `01l_code_compiler.txt` | `01k_code_compiler.txt` |
| `01m_code_checker.txt` | `01l_code_checker.txt` |
| `01n_code_list.txt` | `01m_code_list.txt` |
| `01o_summarizer.txt` | `01n_summarizer.txt` |
| `09c_copyedit.txt` | `09b_copyedit.txt` |

### 1e. Invoke `@contributions-extractor`

Invoke with the PDF, `pdf_text_path`, and the citation. Save output to `00c_contributions.txt`.

If `IS_EMPIRICAL == "NO"`, set `is_empirical=false` and **skip the Empirical Auditor, Procedural Auditor, and Collector** in Step 2. Still run Foundations-Critic, Omissions Auditor, Math Error Finder (lightweight), and — unconditionally — `@foundations-critic-round-2` after Round 1 Foundations-Critic finishes. Deep math audit still follows the Q1 rule.

### 1f. Resolve the math decision

The pipeline runs two tiers of math checking:

- **Lightweight math sweep (always on).** A single `@math-error-finder` call targeting arithmetic, table totals, elasticity/coefficient consistency, and calibration numbers on the math-heavy pages identified in STEP 1g. It runs in every pipeline, regardless of Q1.
- **Deep math audit (opt-in).** The four-agent chain — `@re-deriver`, `@math-proofreader`, `@math-auditor`, `@math-verifier` — that re-derives proofs from first definitions, audits the framework, and sifts the findings.

Use Q1 only to resolve whether the **deep** audit runs:

| `is_math` | `CONTAINS_ALGEBRA` | Run **deep** math audit? |
|-----------|-------------------|--------------------------|
| `force`   | any               | Yes                      |
| `skip`    | any               | No                       |
| `auto`    | `YES` + displayed eqs | Yes                  |
| `auto`    | otherwise         | No                       |

Set `run_deep_math_audit` accordingly. (The lightweight sweep runs unconditionally.)

### 1g. Invoke `@math-page-identifier`

Invoke with the PDF path and `pdf_text_path`. Save output to `math_pages.txt`. Parse the `MATH_PAGES:` line. Store the value as `math_pages` for downstream math agents.

Possible values:

- A compact range spec like `3, 5, 7-10, 15, 18-22` — the usual case.
- `NONE` — no mathematical content detected. Skip the lightweight math sweep in STEP 2; and if `run_deep_math_audit == true`, warn the user and ask whether to proceed anyway (the user may have forced the deep audit on a paper with no equations).
- `UNKNOWN` — text dump was missing or scanned. Pass this through to math agents; they will fall back to scanning the full PDF themselves.

The `math_pages` value is an explicit input to every math agent (`math-error-finder` in STEP 2, and `re-deriver`/`math-proofreader`/`math-auditor`/`math-verifier` if the deep audit runs). Agents use it to target their multimodal `Read` of PDF pages.

## STEP 2 — Red Team (Stage 1)

**Invoke Red Team agents in parallel** (single message with multiple Task tool calls — one per subagent). Each agent receives the PDF, `pdf_text_path` (if non-None), any supplement PDFs with their matching `supp_text_paths`, the citation, the contributions list, and the "Prefer the text dump" directive from the Paper text dump section. Math agents also receive the `math_pages` list produced in STEP 1g and the stronger math-specific directive. Inject the fragments per the mapping table.

### Parallel batch — always

- `@foundations-critic` — theoretical foundations (save: `01a_breaker.txt`)
- `@omissions-auditor` — omissions and unmeasured confounds (save: `01g_the_void.txt`)
- `@math-error-finder` — lightweight math sweep over arithmetic, table totals, and load-bearing numeric claims. Pass `math_pages`. **Skip this single call only if `math_pages == NONE`** — i.e. the paper has no mathematical content. Save: `01e_math.txt`.

### Parallel batch — empirical only (`is_empirical == true`)

- `@empirical-auditor` — empirical machinery (save: `01b_butcher.txt`)
- `@procedural-auditor` — procedural integrity (save: `01c_shredder.txt`)

### Parallel batch — deep math (`run_deep_math_audit == true`)

- `@re-deriver` — pass `math_pages` alongside the PDF and text dump (save: `01fa_math_check.txt`)
- `@math-proofreader` — pass `math_pages` (save: `01fb_math_proofread.txt`)

### Parallel batch — code (`run_code_audit == true`)

- `@paper-code-auditor` (save: `01h_code_gonzo.txt`)
- `@bug-hunter` (save: `01i_code_gonzo_b.txt`)
- `@data-construction-auditor` (save: `01j_code_gonzo_c.txt`)

### After the parallel batch — sequential follow-ups

If `is_empirical == true`:
- `@collector` — pass the PDF, text dump, citation, Empirical Auditor, and Procedural Auditor outputs (save: `01d_collector.txt`).

If `is_empirical == false`:
- `@foundations-critic-round-2` — pass the PDF, text dump, citation, contributions, supplements, and the Round 1 Foundations-Critic output from `01a_breaker.txt`. Save as `01a_2_breaker_revisit.txt`. **Unconditional** for non-empirical papers: this is the replacement for the Empirical Auditor / Procedural Auditor / Collector chain, not an optional add-on. The agent is instructed to find at least 10 issues that differ from Round 1.

If `run_deep_math_audit == true`:
- `@math-auditor` — pass the PDF, `math_pages`, and the Proofreader output (save: `01fc_math_audit.txt`).
- `@math-verifier` — pass the PDF, `math_pages`, and the Re-Deriver, Proofreader, and Auditor outputs (save: `01fd_math_sober.txt`).

If `run_code_audit == true`:
- Combine the three code-hunter outputs into a single text block, then invoke `@red-team-summarizer` (or concatenate as the consolidated list). Save as `01k_code_compiler.txt`.
- `@code-verifier` (save: `01l_code_checker.txt`).
- `@code-list-compiler` — pass the consolidated list and the code-verifier verdicts. Save as `01m_code_list.txt`.

## STEP 3 — Synthesize the Red Team (Stage 1o → 2g)

**Every agent in this step that receives the paper also receives `pdf_text_path`** (per the Paper text dump section). Inject fragments per the mapping.

1. Invoke `@red-team-summarizer` with the citation, contributions, and the concatenated outputs of every Red Team agent that ran. This will include some subset of: Foundations-Critic (`01a_breaker.txt`), Foundations-Critic Round 2 (`01a_2_breaker_revisit.txt`, non-empirical only), Empirical Auditor (`01b_butcher.txt`) + Procedural Auditor (`01c_shredder.txt`) + Collector (`01d_collector.txt`) (empirical only), Omissions Auditor (`01g_the_void.txt`), Math Error Finder (`01e_math.txt`, unless `math_pages == NONE`), the verified deep-math output (`01fd_math_sober.txt` if the deep math audit ran), and the verified code list (`01m_code_list.txt` if the code audit ran). Save as `01n_summarizer.txt`. (Does not take the PDF.)
2. Invoke `@number-checker` with the PDF, `pdf_text_path`, and the summarized list to verify load-bearing numbers and filter visual evidence. Save as `02a_numbers.txt`.
3. **Apply the number-check corrections** to the summarized list. Do this directly (you are the orchestrator) — no separate agent needed. Produce `02b_compiler_1.txt` with corrected/deleted issues. Renumber from 1.
4. Invoke `@blue-team` with the PDF, `pdf_text_path`, citation, contributions, and corrected list. Save as `02c_blue_team.txt`.
5. **Merge Blue Team defenses into each issue** (purely mechanical — no agent). Produce `02d_compiler_2.txt`.
6. Invoke `@assessor` with the PDF, `pdf_text_path`, citation, and the Red+Blue list. Save as `02e_assessment.txt`.
7. **Merge Assessments into each issue** (mechanical). Produce `02f_compiler_3.txt`.
8. Invoke `@dossier-builder` with the PDF, `pdf_text_path`, citation, and the merged list. Save the preliminary final list as `02g_list_v1.txt`.

## STEP 4 — Cross-verification (Stage 3)

**Every agent in this step that receives the paper also receives `pdf_text_path`** (per the Paper text dump section).

1. Invoke `@fact-checker` with the PDF, `pdf_text_path`, and `02g_list_v1.txt` to identify quote/page-ref errors. Save as `03a_checker_1.txt`.
2. Invoke `@citation-checker` with the PDF, `pdf_text_path`, and `02g_list_v1.txt` for the external-source hallucination audit. Save as `03b_external.txt`.
3. Invoke `@dossier-builder` again with the PDF, `pdf_text_path`, `02g_list_v1.txt`, plus the fact-check and citation-check outputs to produce the final dossier. Save as `03c_list_v2.txt`.

If `03c_list_v2.txt` is `=NULL=` or shorter than 50 chars, fall back to `02g_list_v1.txt` as the dossier.

## STEP 5 — Write the narrative review (Stage 4)

Invoke `@reviewer` with the PDF, `pdf_text_path`, citation, contributions, and the final dossier. Save the draft as `04a_reviewer.txt`. The reviewer writes `Credibility Assessment`, `The Bottom Line`, and `Future Research` sections (the `Potential Issues` slot will be filled from the dossier later).

If `run_code_audit`, also invoke `@data-editor` with the citation, the verified code issues (`01m_code_list.txt`), and the draft review (for context). Save as `04b_data_editor.txt`. (Does not take the PDF or text dump.)

## STEP 6 — Verify the review (Stage 5)

**Every agent in this step receives the PDF and `pdf_text_path`** (per the Paper text dump section).

1. Invoke `@fact-checker` with the PDF, `pdf_text_path`, and the draft review. Save as `05a_checker_2.txt`.
2. Invoke a second fact-checker pass for page numbers and quotes specifically — re-use the `@fact-checker` agent with the PDF, `pdf_text_path`, and the instruction to focus on every `(p. X)`, every quote, and every Figure/Table reference. Save as `05b_checker_3.txt`.
3. Invoke `@review-reviser` with the PDF, `pdf_text_path`, citation, the draft review, and both checker outputs. Save the revised review as `05c_reviser.txt`.

If `05c_reviser.txt` is `=NULL=` or trivial, use `04a_reviewer.txt` as the revised review.

## STEP 7 — Assemble Potential Issues into the review

Construct `review_v2.txt` by inserting the dossier (`03c_list_v2.txt` or fallback) under a `## Potential Issues` heading, between `The Bottom Line` and `Future Research` in the revised review. If a Data Editor section exists, place `## Data Editor` (with `04b_data_editor.txt` content) between `## Potential Issues` and `## Future Research`. This is mechanical concatenation — no agent.

## STEP 8 — Legal sanitization and final formatting (Stages 6-7)

1. Invoke `@legal-sanitizer` with the citation and `review_v2.txt`. Save as `06_legal.txt`.
2. Invoke `@formatter` with the citation, `review_v2.txt`, the legal output, and a `paper_context` string of the form `"Status: Working"` or `"Status: Published"` based on `DOCUMENT_TYPE`. Save the final formatted review as `07_formatter.txt`.

## STEP 9 — Writer Mode (Stages 8-9, optional)

If `writer_mode` is true:

1. **In parallel**, invoke:
   - `@revision-strategist` with the PDF, `pdf_text_path`, citation, and `07_formatter.txt`. Save the raw output as `08a_alchemist.txt`. Then split it on `===COPYEDITOR_INSTRUCTIONS===` to obtain `editor_note_raw` (above the separator — passed in-memory to the editor-polisher in the next step) and `secret_instructions` (below). Persist `secret_instructions` to `08c_alchemist_instructions.txt` so the copyeditor can reference it via `@`-notation at STEP 9.3. If `08a_alchemist.txt` is already cached from a prior run but `08c_alchemist_instructions.txt` is missing, read 08a and derive 08c without re-invoking the agent.
   - `@paper-proofreader` with the PDF and `pdf_text_path`. Save as `09a_proofread.txt`. This agent proofreads the PAPER itself (not the review) for spelling, grammar, punctuation, and repeated-word errors, and internally filters OCR artifacts and identity errors. Its output is either a clean Markdown list (`- **Page N**: "original" -> "fix" (reason)`) or the literal string `No proofreading issues were found.` It is independent of the revision-strategist / editor-polisher / copyeditor chain.
2. Invoke `@editor-polisher` with the citation and `editor_note_raw`. Save the polished editor's note as `08b_polisher.txt`. (Does not take the PDF or text dump.)
3. Invoke `@copyeditor` with the PDF, `pdf_text_path`, `07_formatter.txt`, `08b_polisher.txt`, and `08c_alchemist_instructions.txt`. Save as `09b_copyedit.txt`.

## STEP 10 — Render the final report

Build the final output file at `<out>`:

```
═══════════════════════════════════════════════════════════════

                   Claude Code's Peer Review

                    <TITLE_AUTHORS>, <YEAR>

═══════════════════════════════════════════════════════════════

<DISCLAIMER paragraph: "This report was generated by an automated peer-review
pipeline using large language models. No human editor reviewed it. Treat its
findings as hypotheses to verify, not as authoritative judgments.">

═══════════════════════════════════════════════════════════════

<CITATION>

═══════════════════════════════════════════════════════════════

<contents of 07_formatter.txt>

<if writer_mode:>

═══════════════════════════════════════════════════════════════

                       EDITOR'S NOTE TO AUTHOR

═══════════════════════════════════════════════════════════════

<contents of 08b_polisher.txt>

═══════════════════════════════════════════════════════════════

                          COPYEDITING

═══════════════════════════════════════════════════════════════

<contents of 09b_copyedit.txt>

═══════════════════════════════════════════════════════════════

                          PROOFREADING

═══════════════════════════════════════════════════════════════

<contents of 09a_proofread.txt>
```

Omit the PROOFREADING block entirely if `09a_proofread.txt` is exactly `No proofreading issues were found.` — no section heading, no empty box.

Write the report to `<out>`. Confirm to the user:
- the report path (`./peer-review-report.md`),
- the work-dir path (`./peer-review-output/<slug>/`) — contains the generated `README.md`, `paper_text.txt`, and every stage file,
- the rough number of issues that survived to the final dossier,
- the cost class ("base run" vs "with math" vs "with code" vs "with both").

## STEP 11 — Render the PDF version of the report

After the `.md` report is written, produce a companion PDF in the same directory:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/render-pdf.sh <out>
```

The helper runs a three-step conversion:

1. `pandoc <out> -s -o ./peer-review-report.tex --pdf-engine=xelatex` — build a standalone LaTeX version from the Markdown report. The script:
   - First pre-processes the `.md` via `sed` (under an explicit `LC_ALL=en_US.UTF-8` locale) to convert any line of 3+ `═` characters into Markdown HR `---`, so the banner boxes render as proper `\hrulefill`-style horizontal rules in the PDF.
   - Passes `-V header-includes='\usepackage{amsmath,amssymb,amsthm,mathtools}'` so every math package needed by reviewer output (including `\mathbb{R}`, `\begin{pmatrix}`, `\overset{}`, and theorem environments) is guaranteed to load regardless of pandoc's auto-detection.
   - Passes `-V geometry:margin=1in` and `-V fontsize=11pt` for professional document layout.
2. `xelatex -interaction=nonstopmode peer-review-report.tex` — compile to `./peer-review-report.pdf`. xelatex is required (not pdflatex) because the reviewer output may include Unicode characters (author diacritics, em-dashes, the occasional rendered math symbol) that `pdflatex` cannot handle natively.
3. `rm -f` on every LaTeX intermediate (`.tex`, `.aux`, `.log`, `.out`, `.toc`, `.synctex.gz`, `.fdb_latexmk`, `.fls`, `.nav`, `.snm`, `.vrb`, `.bbl`, `.blg`, `.bcf`, `.run.xml`) so only `./peer-review-report.md` and `./peer-review-report.pdf` remain in the user's cwd.

### Math preservation

The pipeline is designed to preserve every inline LaTeX math block (`$...$`) from the Markdown source verbatim into the PDF. Flow:

- **Source** — the formatter agent (STEP 8.2) enforces inline-only `$...$` math and escaped currency (`US\$50`) per `prompts/output-format.md`. By the time STEP 10 writes the `.md`, every equation should be a well-formed `$...$` block.
- **Sed preprocessing** — only matches whole-line `═{3,}` patterns (anchored with `^` and `$`). It cannot match inside a line of prose, so it cannot touch the content between any `$...$` delimiters.
- **Pandoc's `tex_math_dollars` extension** (on by default in `-f markdown`) reads `$...$` as inline math and passes the content through verbatim into the LaTeX output (as `$...$` or `\(...\)`). Escaped `\$` (currency) is read as literal and emitted as `\$` — never misinterpreted as a math delimiter.
- **xelatex + amsmath + amssymb** — handles Greek letters (`\alpha`, `\beta`), operators (`\sum`, `\frac`, `\sqrt`), subscripts/superscripts, mathbb (`\mathbb{R}`), matrices (`\begin{pmatrix}...\end{pmatrix}`), hat accents (`\hat{}`), and all standard academic math. Unicode author names and diacritics are handled by fontspec + Latin Modern.

If a reviewer agent ever emits a math construct not covered by amsmath + amssymb + mathtools (extremely rare — e.g., commutative-diagram packages), the `.tex` intermediate is preserved on compile failure so the user can add the needed package and re-run `xelatex` manually.

**Outcomes to handle:**

- **Exit 0 with `PDF generated: ...`** → extend the STEP 10 confirmation with the PDF path: *"Also wrote `./peer-review-report.pdf`."*
- **Exit 0 with `WARNING: pandoc not installed` or `WARNING: xelatex not installed`** → relay the warning verbatim to the user. The `.md` report is the sole deliverable; the pipeline succeeds normally.
- **Exit 1 with `WARNING: xelatex compilation failed`** → relay the warning. The script preserves `./peer-review-report.tex` for debugging and cleans up transient artifacts; the `.md` report remains authoritative.

Never let a PDF-render failure halt the pipeline — the `.md` is always the primary output, and the PDF is a convenience.

## Progress reporting

Between major steps, write a one-line progress update to the user (e.g. "✔ Red Team complete (5 agents, ~50 raw findings) — running verification cascade"). Do not narrate every sub-step. Do not show full agent outputs unless the user asks.

## Failure handling

- If any agent times out, retry once. If it times out again, surface the failure and ask whether to continue with degraded output or abort.
- If the metadata extractor returns `IS_EMPIRICAL: NULL`, default to `YES` and warn the user.
- If the PDF is over 500 pages, warn the user and ask for confirmation before proceeding (long runs are expensive).

## Conditional branching

| Condition | Effect |
|-----------|--------|
| `IS_EMPIRICAL == "NO"` | Skip Empirical Auditor, Procedural Auditor, Collector. **Unconditionally** run `@foundations-critic-round-2` after the Round 1 Foundations-Critic — this is the replacement for the empirical audit chain, not an optional add-on. |
| `math_pages == NONE` | Skip the Math Error Finder lightweight sweep. (Only when the paper contains no mathematical content at all.) |
| `run_deep_math_audit == true` | Run Re-Deriver, Math Proofreader, Math Auditor, Math Verifier; feed verified-output into the Red Team summarizer. The lightweight Math Error Finder still runs separately. |
| `run_code_audit == true` | Run Paper-Code Auditor, Bug Hunter, Data-Construction Auditor; consolidate; Code Verifier; Code List Compiler; Data Editor. |
| `writer_mode == false` | Skip Revision Strategist, Editor Polisher, Paper Proofreader, Copyeditor. |

## Resumability

Every stage writes its output to a `./peer-review-output/<slug>/<stage>.txt` file. Before invoking an agent, the orchestrator checks whether the file exists:
- If yes → skip the agent, just read the cached output.
- If no → invoke the agent, write the output, continue.

The same rule applies to `paper_text.txt` (produced at STEP 1a) and the run `README.md` (rewritten at STEP 1d).

To **re-run a single stage**, delete its file (and any downstream files) and re-invoke `/peer-review` with the same PDF (and pick the same options when re-prompted, or just accept the same defaults).

## Why so many agents?

The pipeline's effectiveness comes from the **verification cascade**:

1. **Red Team** (5+ personas) generates issues aggressively from different angles. Each persona has its own checklist and is told to find ≥10 issues. This produces many false positives. Non-empirical papers replace Empirical Auditor/Procedural Auditor/Collector with a second Foundations-Critic pass (`@foundations-critic-round-2`) that must find 10+ issues different from Round 1.
2. **Lightweight Math Error Finder** runs in every pipeline, targeting arithmetic, table totals, and calibration numbers on the math pages identified by `@math-page-identifier`. The deep math audit (Re-Deriver → Proofreader → Auditor → Verifier) is opt-in and sits behind it.
3. **Number Checker** filters issues that depend on prohibited visual evidence or arithmetic mistakes.
4. **Blue Team** writes an honest defense for every issue, classifying each into one of seven types (A=Red Team mistake, B=acknowledged, C=clerical, D=structural, E=visual, F=feature, G=other).
5. **Assessor** judges Red vs Blue per issue.
6. **Fact Checker / Citation Checker** verify quotes, page refs, and external-source attributes against the PDF.
7. **Dossier Builder** writes the final paragraph-form list, ordered by foundational-validity → internal-logic → execution → interpretation → presentation.
8. **Reviewer** writes the integrated narrative, drawing on the dossier without repeating it.
9. **Legal Sanitizer** scrubs defamatory phrasing across four red lines.
10. **Formatter** enforces structure, citation format, sentence-case labels, inline-LaTeX math, and Markdown/LaTeX compatibility.

Optional **Writer Mode** (Revision Strategist + Editor Polisher + Paper Proofreader + Copyeditor) generates an author-facing revision strategy, a polished Editor's Note, a typo/grammar list for the paper itself, and concrete copyediting suggestions.

## Cost notes

- Base run (no deep math, no code, writer mode on): ~22 agent invocations, ~10-30 min wall clock. This already includes the always-on `math-page-identifier` + `math-error-finder` pair and (for non-empirical papers) the unconditional `foundations-critic-round-2`.
- With deep math audit: +4 agents (Re-Deriver, Proofreader, Auditor, Verifier).
- With code audit: +5 agents (and `Bash` access for the code hunters).
- Writer mode adds Revision Strategist, Editor Polisher, Paper Proofreader, and Copyeditor.
- The Red Team agents, the Reviewer, and the deep math/code chains use `model: opus` because they are the highest-leverage reasoning steps. Compilers, the Collector, the Math Page Identifier, the Editor Polisher, and the Paper Proofreader use `model: sonnet`. Adjust in the agent files if you need to trade quality for cost.

## Manually invoking a single stage

Each agent is independently usable. For example:

```
@foundations-critic Review the foundations of the paper at ./mypaper.pdf. Citation: "Smith (2024). Title. Journal."
Contributions: <paste>
```

This is useful for iterating on a single agent's prompt or producing a quick foundations-only critique without running the full cascade.

## Notes for the orchestrator

- Each agent is **stateless** — pass the inputs explicitly in the agent prompt (use `@<filename>` references where possible to keep the orchestrator's context lean).
- The whole pipeline is designed to be **resumable**: deleting any `./peer-review-output/<slug>/<stage>.txt` will cause that stage and all downstream stages to re-run.
- Compilation steps (02b/02d/02f, the writer-mode split, the final report assembly) are mechanical text manipulation — do them yourself; do not spawn an agent.
- Use **parallel** invocation in Step 2 (Red Team), Step 4 (fact-checker + citation-checker), and Step 9 (revision-strategist + paper-proofreader). Everything else is sequential because it depends on the previous stage's output.

## Files

- All agents live in `${CLAUDE_PLUGIN_ROOT}/agents/*.md`.
- Shared prompt fragments (output format, voice, hallucination guards, issue types, page reference) live in `${CLAUDE_PLUGIN_ROOT}/prompts/`.
- The PDF text-extraction helper is at `${CLAUDE_PLUGIN_ROOT}/scripts/extract-pdf-text.py`. It is called once per run at STEP 1a to produce `<work_dir>/paper_text.txt`, which every PDF-reading agent uses as the primary source for text-scanning (see the "Paper text dump" section).

When you're done, the user has a self-contained `peer-review-report.md` they can read.
