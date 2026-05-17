---
name: peer-review
description: Adversarial multi-agent peer review of an academic paper PDF. Use when the user invokes /peer-review, or asks to peer-review, critique, evaluate, or red-team an academic paper. Orchestrates a Red Team → Blue Team → Assessor → Reviewer verification cascade (~20 subagents) with optional math and code audits, producing a structured peer-review report.
allowed-tools: Read, Write, Glob, Grep, Bash, Task, AskUserQuestion
---
<!--
Portions adapted from reviewer2 (https://github.com/isitcredible/reviewer2),
Copyright 2026 The Catalogue of Errors Ltd, licensed under Apache-2.0.
Modified by Felpix Studios in 2026 for Claude Code plugin packaging,
adapted prompts for agent use, prompt-fragment extraction, and local orchestration.
-->

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

### Pick a Python interpreter (`PY_BIN`)

Probe `python` first; if it is missing, fall back to `python3`. Record which one resolved as **`PY_BIN`** and reuse it for every later script invocation in this skill.

```bash
if command -v python >/dev/null 2>&1; then PY_BIN=python
elif command -v python3 >/dev/null 2>&1; then PY_BIN=python3
else PY_BIN=""
fi
echo "PY_BIN=${PY_BIN:-MISSING}"
```

If the result is `PY_BIN=MISSING`, neither interpreter is on `PATH`. Stop and print the install message in the next subsection.

### Verify version + `pypdf`

Using the resolved `PY_BIN`:

```bash
"$PY_BIN" -c "import sys; print('PY_OK' if sys.version_info >= (3, 10) else 'PY_OLD'); import importlib.util; print('PYPDF_OK' if importlib.util.find_spec('pypdf') else 'PYPDF_MISSING')" 2>&1
```

Possible failures:
- **`PY_BIN=MISSING`** → neither `python` nor `python3` is on `PATH`.
- **`PY_OLD`** → Python is older than 3.10. The helper scripts use PEP 604 `str | None` syntax and require 3.10+.
- **`PYPDF_MISSING`** → the `pypdf` package is not importable. Required for the PDF text extraction at STEP 1a.

If any check fails, do NOT proceed — do not call `AskUserQuestion`, do not create the work directory, do not invoke any agent. Print exactly this message to the user and stop:

> **Cannot start peer-review — missing dependency.**
>
> This plugin needs **Python 3.10+** with **`pypdf`** installed (and `bibtexparser` if you plan to pass a `.bib` file at STEP 0). Please install the required packages and then re-run `/peer-review`:
>
> ```bash
> pip install pypdf reportlab bibtexparser
> ```
>
> (`reportlab` is only used by the optional `compile-code-to-pdf.py` helper for the code audit; `bibtexparser` is only used if you supply a `.bib` file. Installing them now avoids a second failure later.)

Only if `PY_BIN` is non-empty and the command returns `PY_OK` and `PYPDF_OK`, continue. Hold `PY_BIN` in memory for the rest of the run; every later `Bash` invocation that calls `extract-pdf-text.py`, `compile-code-to-pdf.py`, or `parse-bib.py` MUST use `"$PY_BIN" <script>` rather than the literal word `python`.

### Conditional check: `reportlab` for code audit

After Q2 is answered in STEP 0b — and only if the user picked **"Yes — I have a replication directory"** — run an additional check before continuing past STEP 0:

```bash
"$PY_BIN" -c "import importlib.util; print('REPORTLAB_OK' if importlib.util.find_spec('reportlab') else 'REPORTLAB_MISSING')"
```

If it prints `REPORTLAB_MISSING`, stop and print:

> **Cannot run the code audit — `reportlab` is not installed.**
>
> The code audit packs your replication directory into a single PDF using `reportlab`. Install it and re-run, or re-invoke `/peer-review` and pick **"No replication code"** at the code-audit prompt:
>
> ```bash
> pip install reportlab
> ```

Catching this here means the user does not lose the 10–30 minutes of work that runs before the code audit triggers in STEP 2.

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

Call `AskUserQuestion` **once** with these bundled questions (follow the tool's 1–4 questions / 2–4 options constraint — split into two batched calls if you exceed four).

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

Q5 — header: "Venue tier"
  - "Working paper / dissertation chapter (Recommended)" — early-stage
    work, calibrate severity to "is this defensible at a workshop".
  - "Field journal" — e.g. AEJ, AJPS, JCB, JCR, J. Memory & Lang.
  - "Top-tier general journal" — e.g. AER, QJE, Nature, Science, PNAS.
  - "Conference" — e.g. NeurIPS, ICML, CHI, ACL, FAccT.
```

All questions are single-select (`multiSelect: false`). The user can always override any choice via the auto-provided "Other" free-text option. AskUserQuestion accepts at most four questions per call — bundle Q1–Q4 in the first call and Q5 in a second call (or whatever split lands under the limit).

### 0c. Follow-up prompts for free-form input

- If Q2 = "Yes", ask in plain text: *"What's the path to the replication code directory?"* Save as `code_dir`.
- If Q4 = "Yes", ask in plain text: *"List the supplementary PDF paths (one per line)."* Save as `supplements` (array).
- Always ask in plain text: *"One-word discipline (e.g. econ, CS, biology, medicine, psychology, sociology, history, physics, …)? Hit Enter to skip."* Save as `discipline` (lowercase string, or `None` if blank).
- Always ask in plain text: *"Path to a .bib file for citation validation? (Hit Enter to skip — the citation-checker still runs without it; the .bib just lets it verify cited author/year/title against your bibliography.)"* Save as `bib_path` (absolute path or `None`).
- If the user's opening message already contained an explicit citation (e.g. *"cite this as Smith (2024)..."*), capture it as `citation_override`. Otherwise leave blank — metadata-extractor will supply the citation.

### 0d. Derive defaults

- `slug` = basename of the PDF without extension, lowercased, non-alphanumerics → `-`.
- `work_dir` = `./peer-review-output/<slug>/` — **visible folder in the user's cwd**, not a dotfile.
- `out` = `./peer-review-report.md` — stays at the top of the user's cwd for easy access.
- `pdf_text_path` = `<work_dir>/paper_text.txt` — populated in STEP 1a; may be set to `None` if extraction fails.
- `is_math` = one of `auto | force | skip` (from Q1)
- `run_code_audit` = boolean (from Q2)
- `writer_mode` = boolean (from Q3, default true)
- `venue_tier` = one of `working-paper | field-journal | top-tier | conference` (from Q5; default `working-paper`)
- `discipline` = lowercase string from 0c (default `None`)
- `bib_path` = absolute path to a `.bib` file or `None` (from 0c)
- `bib_entries_path` = `<work_dir>/bib_entries.json` if `bib_path` is set; otherwise `None`

### 0e. Prepare workspace and persist options

```bash
mkdir -p <work_dir>
```

Then write the canonical options dict to `<work_dir>/options.json`. This is the single source of truth for "what was the cache built against" — it drives invalidation in 0f.

```json
{
  "is_math": "auto | force | skip",
  "run_code_audit": true | false,
  "writer_mode": true | false,
  "venue_tier": "working-paper | field-journal | top-tier | conference",
  "discipline": "<string or null>",
  "supplements": ["<absolute path>", "..."],
  "code_dir": "<absolute path or null>",
  "bib_path": "<absolute path or null>",
  "citation_override": "<string or null>",
  "schema_version": 2
}
```

`schema_version` exists so future plumbing changes can invalidate the entire cache cleanly (bump the integer; the comparison at 0f will treat any mismatch as a complete invalidation).

Tell the user in one line what's about to happen and quote the work-dir path so they can resume later:

> "Starting peer-review. Intermediate outputs cached in `./peer-review-output/<slug>/` — a visible folder in your current directory. Re-invoke with the same PDF to resume from cached stages. Final report will be written to `./peer-review-report.md`."

### 0f. Resumability check + cache invalidation

Each downstream stage writes its output to `<work_dir>/<stage>.txt`. Before invoking any agent, check whether its cached output file exists:
- If yes → skip the agent, read the cached file.
- If no → invoke the agent, `Write` its output to the cached path, continue.

**Before** that lookup, do the invalidation pass — otherwise resumed runs silently re-use stage files that are stale relative to the current options.

#### Step 1: detect option drift

If `<work_dir>/options.json` already exists from a prior run, load it as `prev_options` and diff against the current options dict (`curr_options`, computed at 0d). For every key whose value differs, look it up in the **option-impact map** below and unlink (delete) every listed cached stage file. Then unlink everything that depends on those deleted stages via the **stage-dependency graph** below (transitive closure).

If `schema_version` differs, treat it as a full invalidation: delete every `*.txt`, `*.json` file in `<work_dir>` except the (still-valid) `paper_text.txt` and any `supp_*_text.txt` whose corresponding supplement path is unchanged.

After the invalidation pass, overwrite `<work_dir>/options.json` with the current options.

#### Step 2: option-impact map

```
is_math (changed)        → 01e_math.txt, 01fa_math_check.txt,
                           01fb_math_proofread.txt, 01fc_math_audit.txt,
                           01fd_math_sober.txt, math_pages.txt
run_code_audit (changed) → code_bundle.pdf, 01h_code_gonzo.txt,
                           01i_code_gonzo_b.txt, 01j_code_gonzo_c.txt,
                           01k_code_compiler.txt, 01l_code_checker.txt,
                           01m_code_list.txt, 04b_data_editor.txt
writer_mode (changed)    → 08a_alchemist.txt, 08b_polisher.txt,
                           08c_alchemist_instructions.txt,
                           09a_proofread.txt, 09b_copyedit.txt
venue_tier (changed)     → 01a_breaker.txt, 01a_2_breaker_revisit.txt,
                           01b_butcher.txt, 01c_shredder.txt,
                           01d_collector.txt, 01g_the_void.txt,
                           02c_blue_team.txt, 02e_assessment.txt,
                           02g_list_v1.txt, 03c_list_v2.txt,
                           04a_reviewer.txt, 05c_reviser.txt,
                           06_legal.txt, 07_formatter.txt,
                           08a_alchemist.txt, 08b_polisher.txt,
                           09b_copyedit.txt
discipline (changed)     → same as venue_tier
supplements (changed)    → all Red Team outputs that read supplements:
                           01a_breaker.txt, 01a_2_breaker_revisit.txt,
                           01b_butcher.txt, 01c_shredder.txt,
                           01g_the_void.txt
code_dir (changed)       → all run_code_audit files (above)
bib_path (changed)       → 03b_external.txt
citation_override (changed) → 00b_metadata.json plus everything downstream
                              of metadata (effectively a full invalidation)
```

#### Step 3: stage-dependency graph (transitive closure)

When a file is invalidated, every file listed below as depending on it is also invalidated. Apply transitively until no more invalidations cascade.

```
00a_metadata.txt          → 00b_metadata.json, 00c_contributions.txt, every downstream stage
00b_metadata.json         → every downstream stage
00c_contributions.txt     → 01a_breaker.txt, 01a_2_breaker_revisit.txt, 01b_butcher.txt, 01g_the_void.txt, 01n_summarizer.txt, 04a_reviewer.txt
math_pages.txt            → 01e_math.txt, 01fa_math_check.txt, 01fb_math_proofread.txt, 01fc_math_audit.txt, 01fd_math_sober.txt
01a_breaker.txt           → 01a_2_breaker_revisit.txt, 01n_summarizer.txt
01a_2_breaker_revisit.txt → 01n_summarizer.txt
01b_butcher.txt           → 01d_collector.txt, 01n_summarizer.txt
01c_shredder.txt          → 01d_collector.txt, 01n_summarizer.txt
01d_collector.txt         → 01n_summarizer.txt
01e_math.txt              → 01n_summarizer.txt
01g_the_void.txt          → 01n_summarizer.txt
01fa_math_check.txt       → 01fd_math_sober.txt
01fb_math_proofread.txt   → 01fc_math_audit.txt, 01fd_math_sober.txt
01fc_math_audit.txt       → 01fd_math_sober.txt
01fd_math_sober.txt       → 01n_summarizer.txt
01h_code_gonzo.txt        → 01k_code_compiler.txt
01i_code_gonzo_b.txt      → 01k_code_compiler.txt
01j_code_gonzo_c.txt      → 01k_code_compiler.txt
01k_code_compiler.txt     → 01l_code_checker.txt, 01m_code_list.txt
01l_code_checker.txt      → 01m_code_list.txt
01m_code_list.txt         → 01n_summarizer.txt, 04b_data_editor.txt
01n_summarizer.txt        → 02a_numbers.txt, 02b_compiler_1.txt, …, 02g_list_v1.txt, 03a_checker_1.txt, 03b_external.txt, 03c_list_v2.txt, 04a_reviewer.txt, 05a_checker_2.txt, 05b_checker_3.txt, 05c_reviser.txt, 06_legal.txt, 07_formatter.txt
02a_numbers.txt           → 02b_compiler_1.txt and everything below
02b_compiler_1.txt        → 02c_blue_team.txt and below
02c_blue_team.txt         → 02d_compiler_2.txt and below
02d_compiler_2.txt        → 02e_assessment.txt and below
02e_assessment.txt        → 02f_compiler_3.txt and below
02f_compiler_3.txt        → 02g_list_v1.txt and below
02g_list_v1.txt           → 03a_checker_1.txt, 03b_external.txt, 03c_list_v2.txt, 04a_reviewer.txt and below
03a_checker_1.txt         → 03c_list_v2.txt and below
03b_external.txt          → 03c_list_v2.txt and below
03c_list_v2.txt           → 04a_reviewer.txt and below
04a_reviewer.txt          → 05a_checker_2.txt, 05b_checker_3.txt, 05c_reviser.txt, 06_legal.txt, 07_formatter.txt
04b_data_editor.txt       → 06_legal.txt, 07_formatter.txt
05a_checker_2.txt         → 05c_reviser.txt and below
05b_checker_3.txt         → 05c_reviser.txt and below
05c_reviser.txt           → 06_legal.txt, 07_formatter.txt
06_legal.txt              → 07_formatter.txt
07_formatter.txt          → 08a_alchemist.txt, 09b_copyedit.txt (writer mode)
08a_alchemist.txt         → 08b_polisher.txt, 08c_alchemist_instructions.txt
08c_alchemist_instructions.txt → 09b_copyedit.txt
09a_proofread.txt         → (terminal — no downstream)
```

The graph is data, not narrative — encode it in-memory as a dict and walk it once per invalidation.

#### Step 4: manual deletion

If the user manually deletes a stage file between runs (the documented way to force a single stage to re-run), the orchestrator MUST run the same Step 3 cascade on the next invocation: detect missing files, treat them as if they had just been invalidated, and unlink every downstream file in the dependency graph. This is what makes the `delete-and-rerun` workflow safe.

To re-run a single stage, the user deletes its file and re-invokes `/peer-review` with the same PDF — the orchestrator handles the downstream cascade automatically.

### 0g. Pre-flight cost & time estimate

Before STEP 1a fires (which kicks off the first agent and burns tokens), tell the user what they're about to spend. This is a one-screen text summary and a confirmation pause — the goal is "no surprises 20 minutes in."

Compute the agent count from the resolved options and the (cached or freshly extracted) page count of the PDF. If `paper_text.txt` already exists from a prior run, count its `[Page N]` markers; otherwise estimate from the file size of the PDF (`bytes / 50_000` is a coarse-but-fine page estimate; refine after STEP 1a).

```
opus_agents  = 5  (foundations-critic, omissions-auditor, blue-team, assessor, reviewer)
            + 1  (number-checker)
            + 1  (citation-checker)
            + 1  (fact-checker × 1 on the dossier)
            + 2  (fact-checker × 2 on the draft review)
            + 1  (review-reviser)
            + 1  (legal-sanitizer)
            + 1  (formatter)
            + 1  (dossier-builder × 2 → counts as 2)
            + 1  (red-team-summarizer)

if is_empirical:           opus_agents += 3   (empirical-auditor, procedural-auditor, collector)
if not is_empirical:       opus_agents += 1   (foundations-critic-round-2)
if math_pages != "NONE":   opus_agents += 1   (math-error-finder)
if run_deep_math_audit:    opus_agents += 4   (re-deriver, math-proofreader, math-auditor, math-verifier)
if run_code_audit:         opus_agents += 5   (paper-code-auditor, bug-hunter, data-construction-auditor, code-verifier, data-editor)
                           sonnet_agents += 1 (code-list-compiler)
if writer_mode:            opus_agents += 3   (revision-strategist, copyeditor, editor-polisher)
                           sonnet_agents += 1 (paper-proofreader)

sonnet_agents += 3   (metadata-extractor, contributions-extractor, math-page-identifier — always)
```

Token estimate is rough: assume ~`pages × 2_000` input tokens per Opus agent and ~`3_000` output tokens. The point is order-of-magnitude, not invoice-grade. Use these per-million-token rates as of 2026 unless the user has overridden them: **Opus $15 in / $75 out, Sonnet $3 in / $15 out**. If pricing changes, this number is wrong by a constant factor — that's acceptable for a "should I bail?" check.

Print this block to the user (substitute real numbers; keep it tight):

> **About to start peer-review**
>
> - Paper: ~`<N>` pages
> - Agents: `<opus_agents>` Opus + `<sonnet_agents>` Sonnet (= `<total>` total)
> - Optional chains: math = `<auto/force/skip>`, code = `<on/off>`, writer-mode = `<on/off>`, supplements = `<count>`, .bib = `<yes/no>`
> - Estimated wall time: **~`<low>`–`<high>` min** (rough — depends on Anthropic load and parallelism)
> - Estimated token cost: **~$`<low>`–$`<high>`** at 2026 list pricing
>
> If this looks reasonable, no action needed — extraction starts now. To back out, hit Ctrl-C; nothing has been spent yet.

Pick the `low`/`high` band as ±50% of the central estimate — it signals the imprecision honestly. If the user has resumed an interrupted run (i.e. several stage files are already cached), subtract their share from both the agent count and the cost estimate, and label the line "Estimated remaining cost".

This block is informational. Do not call `AskUserQuestion` here — adding another prompt is friction for the common case where the user just wants to proceed. The user can always Ctrl-C before extraction begins.

## Plugin resources (portable paths)

All plugin-internal paths below use `${CLAUDE_PLUGIN_ROOT}` so sub-agent `Task` invocations remain portable regardless of the user's cwd.

- **Shared prompt fragments** (single source of truth for cross-agent guardrails; injected inline — see next section):
  - `${CLAUDE_PLUGIN_ROOT}/prompts/hallucination-guards.md`
  - `${CLAUDE_PLUGIN_ROOT}/prompts/common-directives.md`
  - `${CLAUDE_PLUGIN_ROOT}/prompts/issue-types.md`
  - `${CLAUDE_PLUGIN_ROOT}/prompts/output-format.md`
  - `${CLAUDE_PLUGIN_ROOT}/prompts/voice-and-tone.md`
  - `${CLAUDE_PLUGIN_ROOT}/prompts/page-reference.md` — dynamic; `{PAGE_STRUCTURE}` and `{SUPPLEMENT_START_PAGE}` placeholders are filled from the metadata dict after STEP 1c, then the filled text is injected into every PDF-reading agent that cites page numbers.
- **Helper scripts** (invoked via `Bash`):
  - `${CLAUDE_PLUGIN_ROOT}/scripts/extract-pdf-text.py` — extract plain text from a PDF when an agent needs it without image/layout overhead.
  - `${CLAUDE_PLUGIN_ROOT}/scripts/compile-code-to-pdf.py` — bundle a replication directory into a single PDF for the code-audit agents.

## Prompt fragment injection

The six fragments above are the single source of truth for guardrails that apply across multiple sub-agents. **Agent files do NOT contain this content** — instead, you (the orchestrator) Read each fragment once at the start of the run and inline its text as a preamble to every applicable sub-agent's Task prompt. Do not pass paths.

### When to read

At the start of STEP 1, before invoking `@metadata-extractor`, `Read` each of the six fragments and hold the text in memory for the rest of the run. Do not re-read per invocation. The `page-reference.md` template is cached raw; its placeholders are filled after STEP 1c (see the STEP 1b / 1c sections below).

### Fragment → agent mapping

| Fragment | Inject into |
|----------|-------------|
| `hallucination-guards.md` | foundations-critic, foundations-critic-round-2, empirical-auditor, procedural-auditor, collector, omissions-auditor, math-error-finder, re-deriver, math-proofreader, math-auditor, math-verifier, paper-code-auditor, bug-hunter, data-construction-auditor, code-verifier, code-list-compiler, number-checker, fact-checker, citation-checker, red-team-summarizer, blue-team, assessor, dossier-builder, reviewer |
| `common-directives.md` | foundations-critic, foundations-critic-round-2, empirical-auditor, procedural-auditor, collector, omissions-auditor, contributions-extractor, blue-team, number-checker, fact-checker, assessor, dossier-builder, reviewer, review-reviser, revision-strategist, copyeditor |
| `issue-types.md` | blue-team, assessor, dossier-builder |
| `output-format.md` | reviewer, review-reviser, dossier-builder, formatter |
| `voice-and-tone.md` | reviewer, review-reviser, formatter, revision-strategist, editor-polisher, copyeditor, dossier-builder, data-editor, code-list-compiler |
| `page-reference.md` | foundations-critic, foundations-critic-round-2, empirical-auditor, procedural-auditor, collector, omissions-auditor, math-error-finder, re-deriver, math-proofreader, math-auditor, math-verifier, number-checker, fact-checker, citation-checker, blue-team, assessor, dossier-builder, reviewer, review-reviser, revision-strategist, copyeditor, paper-proofreader |

**No injection:** metadata-extractor, math-page-identifier, legal-sanitizer, editor-polisher, paper-code-auditor, bug-hunter, data-construction-auditor, code-verifier (mechanical tasks, code-only stages, or self-contained tasks — fragments do not apply). The agents listed in the mapping table above receive only the fragments they appear under — for example, `data-editor` and `code-list-compiler` get `voice-and-tone.md` only; `red-team-summarizer` gets `hallucination-guards.md` only.

### Injection format

Prefix each applicable sub-agent's Task prompt with:

```
---
# Shared guardrails

## Hallucination Guards
<verbatim contents of hallucination-guards.md>

## Common Directives
<verbatim contents of common-directives.md>

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

## Calibration preamble (venue tier + discipline)

In addition to the shared fragments, every **critique-producing agent** receives a one-paragraph "Calibration" preamble derived from `venue_tier` and `discipline` (collected at STEP 0). The point is to scale severity to what a real reader at this venue would expect, without giving the agent license to invent issues.

Inject this preamble — verbatim, with the `{venue_tier}` and `{discipline}` substitutions filled — at the very top of the Task prompt for: `foundations-critic`, `foundations-critic-round-2`, `empirical-auditor`, `procedural-auditor`, `omissions-auditor`, `collector`, `assessor`, `dossier-builder`, `reviewer`, `revision-strategist`, `copyeditor`, `data-editor`. Do NOT inject it into mechanical/verification agents (number-checker, fact-checker, citation-checker, formatter, legal-sanitizer, math-verifier, code-verifier, the proofreaders) — these are calibration-neutral and should not soften or harden their checks based on venue.

Build the preamble from these fragments:

```
---
# Calibration

This paper is being assessed against the **{venue_tier_human}** bar.
{venue_tier_text}

{discipline_line}

Calibration shifts severity, not the rules of evidence. You may not invent
issues that do not exist at any venue, and you may not suppress real
findings because they are "minor for this venue".
---
```

Where:

| `venue_tier` | `venue_tier_human` | `venue_tier_text` |
|---|---|---|
| `working-paper` | "working paper / dissertation chapter" | "Apply a workshop bar: the headline claim should be defensible to an informed colleague, but missing robustness checks, partial literature engagement, and rough exposition are normal at this stage. Major issues are problems that would block submission, not problems that would block acceptance. Do not flag missing items that an author would naturally add during revision (e.g. polished tables, full lit-review coverage, additional sensitivity tests) unless their absence undermines the headline claim itself." |
| `field-journal` | "field journal" | "Apply a typical field-journal bar (think AEJ, AJPS, JCB, J. Memory & Lang.). Standard robustness checks should be present; identification should be defensible to a methodologically attentive specialist; the literature engagement should cover the immediate prior work in the subfield. Issues that would draw a referee's request for revision count as Major; issues a referee would shrug at count as Minor." |
| `top-tier` | "top-tier general journal" | "Apply a top-tier-general bar (think AER, QJE, Nature, Science, PNAS). Identification must be airtight or honestly hedged; robustness must be exhaustive; the contribution must be defensible against the strongest counterargument in the broader literature, not just the subfield. Issues that would cost a desk-reject or a Reviewer 2 demolition count as Critical even if a field-journal referee would tolerate them." |
| `conference` | "conference (e.g. NeurIPS, ICML, CHI, ACL)" | "Apply a top-tier conference bar. Reproducibility (code, hyperparameters, seeds), baseline strength, ablations, and statistical significance of headline numbers must be present. Issues that would cost a meta-reviewer's confidence count as Critical. The bar for novelty is high but the bar for prose polish is lower than a journal." |

`discipline_line` is built as:
- If `discipline` is a non-empty string: `"The discipline is **{discipline}**. Apply the methodological norms of that field (preferred identification strategies, what counts as a credible robustness check, what evidence the field treats as load-bearing). Do not import standards from other fields where they would be inappropriate (e.g. do not demand RCT-grade identification of an interpretive humanities paper; do not let a quantitative ML paper escape with anecdote)."`
- If `discipline` is `None`: `"Discipline was not specified. Use general academic norms; do not assume a specific subfield's conventions."`

Do not store the rendered preamble in a stage file — it is computed once per run from the options and injected at agent-invocation time. It changes only when the user re-runs with different `venue_tier` or `discipline` (which will trigger cache invalidation per #7).

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
"$PY_BIN" ${CLAUDE_PLUGIN_ROOT}/scripts/extract-pdf-text.py \
    "<pdf_path>" --out "<work_dir>/paper_text.txt"

# Each supplement (repeat once per entry in <supplements>)
"$PY_BIN" ${CLAUDE_PLUGIN_ROOT}/scripts/extract-pdf-text.py \
    "<supp_path>" --out "<work_dir>/supp_<slug>_text.txt"
```

`$PY_BIN` was resolved during the preflight (either `python` or `python3`) — keep using it for every helper-script invocation in this run.

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

### 1b. Read the six prompt fragments

Read each of `hallucination-guards.md`, `common-directives.md`, `issue-types.md`, `output-format.md`, `voice-and-tone.md`, and `page-reference.md` from `${CLAUDE_PLUGIN_ROOT}/prompts/` and cache the text in memory. The first five are used verbatim. The `page-reference.md` fragment has two placeholders (`{PAGE_STRUCTURE}`, `{SUPPLEMENT_START_PAGE}`) — hold the raw template here; you will fill the placeholders after STEP 1c once the metadata dict is populated, then use the filled version for every subsequent sub-agent invocation.

### 1c. Invoke `@metadata-extractor`

Invoke with the PDF path and `pdf_text_path`. Save output to `00a_metadata.txt`. Parse the `CITATION:`, `IS_EMPIRICAL:`, `CONTAINS_ALGEBRA:`, `DOCUMENT_TYPE:`, `PAGE_STRUCTURE:`, and `SUPPLEMENT_START_PAGE:` fields. Persist as `00b_metadata.json` for downstream agents.

If `citation_override` was collected in Step 0c, use that string as the citation in all downstream agent prompts instead of the extracted one.

**Fill the page-reference template** now: substitute `{PAGE_STRUCTURE}` and `{SUPPLEMENT_START_PAGE}` in the cached `page-reference.md` text with the parsed values (fall back to `"NULL — treat the printed page number as whatever appears in the PDF header/footer"` if either metadata field is missing). Use this filled text as the sixth guardrail fragment for all subsequent injections.

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
| `options.json` | Canonical run-options dict (math/code/writer/venue/supplements/bib). Source of truth for cache invalidation. |
| `paper_text.txt` | pypdf-extracted text dump of the PDF with `[Page N]` markers |
| `supp_<slug>_text.txt` × N | Plain-text dump of each supplement `<basename>.pdf` *(only if supplements were provided)* |
| `bib_entries.json` | Normalized JSON of the user-supplied `.bib` *(only if `bib_path` was provided at STEP 0c)* |
| `code_bundle.pdf` | Dense single-PDF bundle of the replication code, produced by `compile-code-to-pdf.py`. Quick-scan input for the four code-audit agents *(only if `run_code_audit == true`)* |
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

### 1h. Parse `.bib` (if provided)

If `bib_path` is set (the user passed a `.bib` file at 0c), parse it once into a normalized JSON list. The citation-checker reads this in STEP 4 to verify cited author/year/title matches against the actual bibliography rather than only flagging hallucinations within the paper text.

```bash
"$PY_BIN" ${CLAUDE_PLUGIN_ROOT}/scripts/parse-bib.py \
    "<bib_path>" --out "<work_dir>/bib_entries.json"
```

The script prefers `bibtexparser` if installed, falls back to a regex parser otherwise — either path produces the same output schema. Set `bib_entries_path` to the output path on success.

**Failure modes:**
- **Resumability:** if `bib_entries.json` already exists from a prior run with the same `bib_path` (verified by the cache-invalidation pass at 0f), skip re-parsing.
- **`.bib` file not found:** the script exits with `".bib file not found: …"`. Warn the user, set `bib_entries_path = None`, and continue without bib validation. Do not halt the pipeline.
- **0 entries parsed:** the script prints a stderr warning and writes an empty array. Relay the warning to the user and set `bib_entries_path = None` (an empty array is worse than nothing — it would cause every cited reference to look "missing").
- **`bibtexparser` not installed:** the script automatically falls back to its regex parser. No user-visible failure.

If `bib_path` is `None` (the common default), skip this step entirely. The citation-checker will operate in its existing PDF-only mode.

### 1i. Compile code bundle (if `run_code_audit == true`)

When code-audit is on, produce a single dense PDF of the replication code so the code-audit agents have an alternative quick-scan format to the file-by-file directory exploration they currently do with `Bash`/`Read`/`Grep`. The bundle is **additive**, not a replacement — agents still use the directory for file-specific work; the bundle is for orientation and high-level overview when the directory is large.

```bash
"$PY_BIN" ${CLAUDE_PLUGIN_ROOT}/scripts/compile-code-to-pdf.py \
    "<code_dir>" --out "<work_dir>/code_bundle.pdf"
```

Skip the invocation if `code_bundle.pdf` already exists in the cache (the cache-invalidation pass at 0f handles re-builds when `code_dir` or `run_code_audit` changes). The script honors a 5 MB byte cap by default and skips standard generated/binary directories (`.git`, `node_modules`, `__pycache__`, etc.); if the user's code dir is unusually large, raise the cap with `--max-bytes`.

Pass `code_bundle.pdf` to the four code-audit agents (`paper-code-auditor`, `bug-hunter`, `data-construction-auditor`, `code-verifier`) at STEP 2 as an additional input alongside the existing `code_dir`.

**Failure modes:**
- **`reportlab` missing:** already gated by the preflight conditional check above; would only fire here if the user disabled the check. The script exits with a clear install message.
- **Empty code directory:** script exits with `"No code files found."` Warn the user that the code-audit will run without a bundle (agents fall back to direct directory exploration).
- **Cap reached:** the script prints a stderr message naming the first skipped file; relay it. The bundle contains the prefix that fit; agents must use the directory for the rest.

If `run_code_audit == false`, skip this step entirely.

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
2. Invoke `@citation-checker` with the PDF, `pdf_text_path`, `02g_list_v1.txt`, and — if `bib_entries_path` is non-`None` — the path to `bib_entries.json` plus the directive: *"You also have a parsed bibliography. Use it to verify, for every external source the dossier critiques (author + year + paper title), that an entry exists in the .bib with roughly matching year and roughly matching title (allow whitespace, capitalization, and punctuation differences). If the cited reference is absent from the .bib OR the .bib entry's year or title clearly disagrees with what the dossier says, raise it as a Major issue with the form `Citation mismatch: \"<paper says>\" but .bib has \"<actual>\".`"* Save as `03b_external.txt`.
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

Build the final output file at `<out>`. The report is a YAML-frontmatter
Markdown document: pandoc reads the frontmatter in STEP 11 to emit a
standalone title page, a table of contents, and page breaks before the
author-facing sections.

Fields to compute once before assembly:
- `<CITATION>` — from the metadata dict (or `citation_override` if present).
- `<RUN_DATE>` — today's ISO date (`YYYY-MM-DD`).

Template:

~~~
---
title: "Claude Code's Peer Review"
subtitle: "<CITATION>"
date: "<RUN_DATE>"
toc: true
toc-depth: 1
geometry: margin=1in
fontsize: 11pt
classoption:
  - titlepage
header-includes: |
  \usepackage{amsmath,amssymb,amsthm,mathtools}
---

> *This report was generated by an automated peer-review pipeline using
> large language models. No human editor reviewed it. Treat its findings as
> hypotheses to verify, not as authoritative judgments.*

<contents of 07_formatter.txt, with every line `^## ` promoted to `# `>

<if writer_mode:>

\newpage

# Editor's Note to Author

<contents of 08b_polisher.txt>

\newpage

# Copyediting

<contents of 09b_copyedit.txt>

\newpage

# Proofreading

<contents of 09a_proofread.txt>
~~~

Omit the Proofreading block entirely (including its leading `\newpage`) if
`09a_proofread.txt` is exactly `No proofreading issues were found.`

**Heading promotion.** The formatter emits `## Section` for each top-level
review section (and `## Data Editor` if the code audit ran). Assembly runs
an anchored substitution `^## ` → `# ` on the formatter output only. Safe
because every upstream agent uses `##` solely for top-level headers — the
"Potential Issues" item labels are bold, not headings. The writer-mode
files (`08b_polisher.txt`, `09b_copyedit.txt`, `09a_proofread.txt`) are
headingless by their own agents' constraints, so each is wrapped in a
fresh `# ...` H1 during assembly rather than promoted.

**Page breaks.** `\newpage` is pandoc raw LaTeX: it is passed through to
the `.tex` output verbatim. The four review sections therefore flow
continuously in the PDF; each of the three writer-mode sections starts on
its own page. In plain Markdown viewers the `\newpage` lines render as
literal text — a minor cosmetic cost; the PDF is the reader-facing
artifact.

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

1. `pandoc <out> -s -o ./peer-review-report.tex --pdf-engine=xelatex` — build a standalone LaTeX version from the Markdown report. Every rendering option (title page, TOC, geometry, font size, math-package preamble) is carried in the `.md`'s YAML frontmatter, so pandoc is invoked with no per-option `-V` flags.
2. `xelatex -interaction=nonstopmode peer-review-report.tex` runs **twice** — the first pass writes `.aux`/`.toc`, the second pass reads them so the TOC page numbers resolve correctly. xelatex is required (not pdflatex) because the reviewer output may include Unicode characters (author diacritics, em-dashes, the occasional rendered math symbol) that `pdflatex` cannot handle natively.
3. `rm -f` on every LaTeX intermediate (`.tex`, `.aux`, `.log`, `.out`, `.toc`, `.synctex.gz`, `.fdb_latexmk`, `.fls`, `.nav`, `.snm`, `.vrb`, `.bbl`, `.blg`, `.bcf`, `.run.xml`) so only `./peer-review-report.md` and `./peer-review-report.pdf` remain in the user's cwd.

### Math preservation

The pipeline is designed to preserve every inline LaTeX math block (`$...$`) from the Markdown source verbatim into the PDF. Flow:

- **Source** — the formatter agent (STEP 8.2) enforces inline-only `$...$` math and escaped currency (`US\$50`) per `prompts/output-format.md`. By the time STEP 10 writes the `.md`, every equation should be a well-formed `$...$` block.
- **Pandoc's `tex_math_dollars` extension** (on by default in `-f markdown`) reads `$...$` as inline math and passes the content through verbatim into the LaTeX output (as `$...$` or `\(...\)`). Escaped `\$` (currency) is read as literal and emitted as `\$` — never misinterpreted as a math delimiter.
- **`\newpage` page-break markers** inserted in STEP 10 are pandoc raw LaTeX; they pass through untouched, adjacent prose and math around them are unaffected.
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

**Two correctness rules** (full details in STEP 0f):

1. **Options-driven invalidation.** The orchestrator persists the current run's options to `<work_dir>/options.json` at STEP 0e. On every re-invocation it diffs against the cached `options.json`, and for each changed key it deletes the affected stage files (per the option-impact map at 0f) plus everything downstream (per the dependency graph). This is what stops a re-run with `--force-math-audit` from silently re-using the base-run summarizer output.
2. **Manual-deletion cascade.** If the user manually deletes a stage file to force a re-run, the orchestrator detects the missing file at 0f and unlinks every downstream file in the dependency graph before continuing. The user only ever needs to delete the stage they actually want to re-run.

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
- 26 agents use `model: opus` (Red Team auditors, the Reviewer, the deep math/code chains, the verifiers, the Blue Team, the Assessor, the Dossier Builder, the writer-mode pipeline). 9 agents use `model: sonnet`: `collector`, `contributions-extractor`, `editor-polisher`, `legal-sanitizer`, `math-page-identifier`, `metadata-extractor`, `paper-proofreader`, `red-team-summarizer`, `code-list-compiler` — mechanical aggregation, metadata extraction, and surface-level polish tasks where Opus reasoning depth is not needed. Adjust in the agent files if you need to trade quality for cost.

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
- Shared prompt fragments (output format, voice, hallucination guards, common directives, issue types, page reference) live in `${CLAUDE_PLUGIN_ROOT}/prompts/`.
- The PDF text-extraction helper is at `${CLAUDE_PLUGIN_ROOT}/scripts/extract-pdf-text.py`. It is called once per run at STEP 1a to produce `<work_dir>/paper_text.txt`, which every PDF-reading agent uses as the primary source for text-scanning (see the "Paper text dump" section).

When you're done, the user has a self-contained `peer-review-report.md` they can read.
