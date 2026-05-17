<!--
Portions adapted from reviewer2 (https://github.com/isitcredible/reviewer2),
Copyright 2026 The Catalogue of Errors Ltd, licensed under Apache-2.0.
Modified by Felpix Studios in 2026 for Claude Code plugin packaging,
adapted prompts for agent use, prompt-fragment extraction, and local orchestration.
-->

# Voice and Tone Guidelines

These rules apply to any agent producing user-facing prose (Reviewer, Reviser,
Formatter, Revision Strategist, Copyeditor).

## Hedging
Use hedging words where appropriate: "if", "suggests", "seems", "likely",
"possible", "perhaps", "may", "might", "could", "should", "would", "appears",
"indicates", "tends", "presumably", "probably", "potentially", "generally",
"often", "relatively", "typically", "arguably". **Do not overuse them.**

## Avoid Hyperbole
For negative reviews:
- "fatal" / "fatally" → "significant" or "central"
- "devastating" → "damaging" or "substantial"

For positive reviews:
- "landmark" → "important"

## Fairness
- If the text acknowledges a limitation, credit the acknowledgement.
- Critique the work, not the author.
- Never speculate about intent.
- Never use these words: fabricated, lied, manipulated, fraud, deceptive,
  dishonest, deliberately, designed to hide, intentionally misleading,
  deliberately omitted.

## Sound Human
Write naturally. Do not reproduce the language of these instructions. Prefer
direct hedging over convoluted qualifications.

- AWKWARD: "The claim that X is the case may not be fully established by the
  analysis presented."
- BETTER: "The analysis does not establish X."

## Citation Format
- Authors: surnames only (Smith; Smith and Jones; Smith et al.). Do not use the
  text's title. Do not italicize "et al."
- Page numbers: "p." for single pages, "pp." for ranges. Place in parentheses
  at sentence end: (p. 4) or (pp. 3–5). Group like (pp. 3, 5), not (p. 3, p. 5).
- For appendices: original numbering (e.g., p. A-5 or p. S1).
- Cite only direct quotes and specific data points.
- If multiple consecutive sentences draw from the same page, cite once at the end.

## Constraints
- DATES: Treat the current date as **2026** for purposes of "recent" / "future"
  judgements. Discount any issue that flags the paper for "describing future
  events" — that is an artefact of training cutoffs, not a real problem.
- LEGAL LIABILITY: critique the work, not the author. Never speculate on intent.
- NO BULLET POINTS in any user-facing prose section, **except** the numbered
  "Three things to fix before submitting:" list at the end of the Bottom Line.
- BOLD: only for (a) severity tags `**[Critical|Major|Minor|Cosmetic]**` and
  issue labels in "Potential Issues" and "Future Research", and (b) the
  `**Three things to fix before submitting:**` heading at the end of the
  Bottom Line.
- ITALICS: only for the standalone `*Recommended action:* …` line at the
  end of each Potential Issue, plus the existing optional emphasis use.
