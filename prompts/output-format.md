# Final Report Output Structure

The final review consists of exactly four sections, in this order, with no
preamble or postscript.

---

## Credibility Assessment

The integrated assessment.

- Length: ~700–1000 words.
- Format: paragraphs only. No subheadings. No bullet points. No bold labels
  within prose.
- The goal is a high-level meta-assessment focused on the headline claims.
- **First paragraph:** explain what the text is and highlight its big claims,
  using direct quotes where possible. Optionally situate in scholarly debate.
- **Second and subsequent paragraphs:** make the integrated assessment of the
  text's contribution. Avoid starting with "However,".
- **Final paragraph:** return to the themes of the first paragraph. What does
  the text actually contribute? What can we actually learn from it?
- Each paragraph should begin with a sentence that implicitly summarizes its
  point. Read just first sentences in sequence; the logic should be visible.
- Do not overuse the word "credible".
- Do not use bold, bullet points, or subheadings here.

## The Bottom Line

A single short paragraph providing an accessible takeaway from the review,
followed by a numbered "Three things to fix before submitting" list.

- **Paragraph:** 3–5 sentences. Must align precisely with "Credibility
  Assessment" in tone and conclusion.
- **List:** Exactly the heading `**Three things to fix before submitting:**`
  on its own line, then a numbered list (`1.`, `2.`, `3.`) of the three
  highest-priority items the author should address. Draw from the
  `[Critical]` issues first; if fewer than three Critical issues exist,
  fill from the top-ranked `[Major]` issues. Each list item is a single
  sentence stating the action (not the diagnosis) — the same kind of
  sentence used in the issue paragraphs' `Recommended action` line, but
  written so the author can act on it without re-reading the dossier.
  - YES: `1. Re-run the headline IV specification with the slave-trade
    indicators added as controls and report the coefficient.`
  - NO: `1. The exclusion restriction is fragile.` (Diagnosis, not action.)
- The list is the only structured element permitted in the Bottom Line
  section. Do not add bullet points, sub-headers, or other formatting.
- If the dossier contains zero `[Critical]` and zero `[Major]` issues,
  reduce the list to whatever count exists (one or two items, or omit
  the list and the heading entirely if there are zero substantive issues
  — a paper with only `[Cosmetic]` issues does not need a "fix before
  submitting" list).

## Potential Issues

Specific issues that survived the verification cascade, ranked by how much they damage the text's central claims. Report only issues you can defend with specific evidence — fewer real issues beat a longer list with padding.

- **Severity tag — MANDATORY.** Every issue starts with one of
  `**[Critical]**`, `**[Major]**`, `**[Minor]**`, or `**[Cosmetic]**`,
  in bold, followed by a single space, then the issue label and colon.
  Tier definitions are in `issue-types.md`. Examples:
  - `**[Critical]** **Instrument validity:** The IV strategy ...`
  - `**[Major]** **Sensitivity to upper-tail observations:** ...`
  - `**[Cosmetic]** **Presentation issues:** ...`
- **Format:** Bold severity tag, then bold label in **sentence case**,
  followed by colon (also bold), then description as a single paragraph.
  NO bullet points. NO numbering.
- Sentence case: only the first word of the label is capitalized, **plus
  proper nouns** (country, region, place, person, named test, named
  dataset). The bracketed severity tag does not count as the first word.
  - YES: **[Critical]** **Instrument validity:** The IV strategy ...
  - YES: **[Major]** **Falsification test in Nigeria:** ...
  - NO: **[critical]** **Instrument Validity:** ...
- Each issue is a standalone paragraph.
- Provide more detail for issues with greater magnitude. A `[Critical]`
  issue typically warrants a denser paragraph than a `[Minor]` one.
- Page numbers required: (p. 4) or (pp. 3–5) at the end of relevant sentences.
- If the text acknowledges/recognizes the issue, mention it in the description —
  do not state "Acknowledged" in the issue label.
- Do not begin the bold label with the word "Potential" — the section heading
  already says it.
- Group `[Cosmetic]` issues into a single **[Cosmetic]** **Presentation issues:** paragraph (no bullet points). Do not group across other tiers.
- Mathematical errors must include the equation number/location and both the
  incorrect and corrected expression. Inline LaTeX (`$...$`) only — no display
  math, no code blocks.
- **Recommended action — MANDATORY.** Every issue paragraph ends with a
  standalone `*Recommended action:* <one sentence>` line in italics. The
  action names a concrete next step the author can perform: a regression
  to run, a paragraph to rewrite, a robustness check to add, a citation to
  reconcile, a derivation to redo. Diagnosis without action is incomplete.
  - YES: `*Recommended action:* Re-run Table 4 column 1 dropping
    observations with log mortality > 6 and report the coefficient
    side-by-side with the headline estimate.`
  - YES: `*Recommended action:* Reconcile the discrepancy between the
    text ("$N=1{,}482$") and Table 2 ("$N=1{,}478$") and pick one number.`
  - NO: `*Recommended action:* The author should think more carefully
    about identification.` (Too vague — name the specific test, citation,
    or rewrite.)
  - **Grouped paragraphs** (the `[Cosmetic]` "Presentation issues:" paragraph
    or the `[Minor]` "Replication notes:" paragraph): a single combined
    `*Recommended action:* <one sentence>` line at the end of the
    paragraph, naming the bulk action (e.g. *"Walk the listed cosmetic
    issues in a final copyedit pass before submission."*). Do not emit one
    action line per sub-item — that defeats the grouping.

## Future Research

Up to 5 constructive research proposals. Same format as Potential Issues.

- **Bold label in sentence case:** then description.
- Examples:
  - **Alternative identification strategy:** Future work could exploit ...
  - **Extended time horizon:** A longer panel would allow ...
- Rules:
  - If the text failed to prove X because of flaw Y, propose how to prove X
    correctly.
  - Must be methodologically feasible today (2026+).
  - Do not suggest research that has already been done since the text's
    publication.

---

## Mathematical Notation

Use inline LaTeX (`$...$`) for all Greek letters, variables with subscripts, and
mathematical symbols. **Do not** use display math (`$$...$$`). **Do not** wrap
LaTeX in backticks or code blocks.

- CORRECT: The value of $\beta_1$ is significant.
- WRONG: `$\beta_1$` or `$$\beta_1$$`.

For currency, escape the dollar sign: write `US\$50`, not `US$50`.

## Strict constraints
- No bullet points anywhere, **except** the numbered "Three things to fix
  before submitting:" list at the end of the Bottom Line.
- No bold except where specified above (severity tags, issue labels, the
  "Three things" heading).
- No midrules or separator lines.
- Output ONLY these four sections. No preamble. No postscript.
