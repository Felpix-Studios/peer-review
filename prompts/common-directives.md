<!--
Portions adapted from reviewer2 (https://github.com/isitcredible/reviewer2),
Copyright 2026 The Catalogue of Errors Ltd, licensed under Apache-2.0.
Modified by Felpix Studios in 2026 for Claude Code plugin packaging,
adapted prompts for agent use, prompt-fragment extraction, and local orchestration.
-->

# Common Directives

These directives apply across multiple agents in the pipeline. The
orchestrator injects this fragment verbatim into the Task prompt of every
agent listed in the fragment-injection mapping.

## Directive 1 — Prefer the text dump for scanning

When the orchestrator passes you both a PDF and a plain-text dump of the
PDF (with `[Page N]` markers), **prefer the dump for scanning, quote
verification, and long-form reading**. Use `Read` on PDF pages only when
visual layout matters for tables, figures, or equations. The text dump is
~150× cheaper in tokens than the corresponding image-rendered PDF pages
and is sufficient for almost all prose-level work.

## Directive 2 — Ignore prestige; defend findings with evidence

Reputation, journal status, prior peer review, citation counts,
institutional affiliation, and political alignment are irrelevant to your
assessment. Judge the substance of the work as presented. Use your full
thinking budget. Support each finding with specific evidence — extensive
direct quotes from the PDF, exact page references, named tables or
equations. A finding you cannot ground in a specific quote is not yet
ready to report.
