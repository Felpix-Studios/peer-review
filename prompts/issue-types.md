# Issue Type Classification

Used by the Blue Team, the Assessor, and the Dossier Builder.

## Severity tiers (used by the Dossier Builder, Reviewer, and Formatter)

Every issue that survives to the final dossier is tagged with **exactly one**
severity tier. The tag prefixes the bold issue label in the rendered
"Potential Issues" section so an author can scan severity in one pass.

- **`[Critical]`** — the headline claim does not survive the issue. The
  paper's main contribution would have to be re-framed, retracted, or
  re-derived from new evidence. A reasonable referee would push for
  rejection or major-revision-with-no-resubmit on this issue alone.
  Examples: identification strategy fails on its own terms; theorem
  statement does not actually follow from the proof; data construction
  inverts the sign of the headline coefficient.

- **`[Major]`** — the issue requires substantial new analysis, a new robustness
  check, or a substantive rewrite, but the headline claim could survive
  after the author addresses it. A referee would request explicit response
  in a revision. Examples: missing standard sensitivity test; key
  assumption asserted rather than tested; effect-size interpretation that
  ignores the practical-significance question; cited literature missing a
  directly relevant result.

- **`[Minor]`** — clarification, additional discussion, or a small
  robustness check that strengthens the paper without changing what it
  claims. A referee might mention it without making it a revision
  blocker. Examples: a regression coefficient that the author should
  explain in the text but is correctly reported in the table; a
  footnote elaboration that would help a careful reader; a missing
  citation to adjacent work.

- **`[Cosmetic]`** — wording, typography, table notes, formatting,
  notation that does not affect interpretation. The author can fix in
  the round before submission. Group cosmetic issues into a single
  paragraph using the existing **Presentation issues:** convention.

**Tag selection rules:**

- Calibrate to the run's `venue_tier` preamble. The same issue can be
  Major at a top-tier general journal and Minor at a working-paper bar.
- A Type-D structural error (per the type taxonomy below) is **never**
  Cosmetic, even when the qualitative conclusion survives — it is at
  least Minor (often Major).
- A Type-C clerical error is at most Minor unless it changes a
  load-bearing number.
- A Type-B acknowledged issue keeps the severity it would have absent
  the acknowledgement, then steps DOWN one tier if the acknowledgement
  is convincing (Critical → Major, Major → Minor, Minor → Cosmetic).
  Never below Cosmetic; if it would step out of the report entirely,
  drop the issue instead.
- Never tag the same issue with two tiers; never use compound tags
  (`[Major-Critical]`, `[Critical/Structural]`).

**(Type A) Red Team mistake**
- Issues where the Red Team's critique depends on a mistake in their
  description of the text.
- Verify they read the text correctly and have not invented an issue.
- Watch for these regression-result errors:
  - Focusing on the reduced form rather than the IV coefficient in 2SLS.
  - Mixing coefficients from different specifications.
  - Ignoring log transformations.
  - Interpreting logit as if it were OLS.
  - Misinterpreting interaction terms (treating an interaction coefficient as
    the full marginal effect, or ignoring that constituent terms' interpretation
    changes).
- For external sources, be alert to invented attributes: years, geographic
  coverage, variables included/excluded, sample restrictions, numerical values,
  data frequency, methodological procedures.
- For mathematical claims (sign errors, wrong coefficients), check the Red
  Team's algebra carefully.
- **The Red Team must not be allowed to make any mistakes.** Flag every
  technical error; specify whether the critique depends on it partly or
  entirely.

**(Type B) Acknowledged issues**
- The PDF itself **explicitly acknowledges** that X is a potential problem for
  its argument (not just mentions X). Examples: "We acknowledge that X is a
  limitation...", "We address concern Y in the robustness checks...".
- The only question is whether the paper's acknowledgement actually defuses the
  concern. If the acknowledgement is convincing — paper names the limitation
  AND shows it has been addressed in a way that leaves the critique with no
  extra analytical force — drop the issue. If unconvincing — bare admission,
  passing concession contradicted by the headline claim, or a premise the
  critique synthesizes into a stronger conclusion the authors did not draw —
  keep it. The verbatim acknowledgement quote MUST appear in the paragraph.

**(Type C) Clerical errors**
- Presentation-level issues only: sample size discrepancies, missing references,
  totals that don't equal the sum, mislabeled figures.
- We **cannot** know the impact, no matter how great they seem. Apply the
  principle of charity. Note them but downplay.

**(Type D) Structural errors**
- Misinterpreted regression coefficients, wrong functional forms, mathematical
  contradictions in the model's own terms, misinterpretations of theoretical
  concepts, incorrect derivations, wrong coefficients/missing factors/incorrect
  subscripts/dimensional mismatches in equations.
- These threaten the logic and cannot be explained as sloppiness.
- **Confirmed algebraic errors are always Type D, even when the qualitative
  conclusion survives.** A coefficient wrong by $\sqrt{2}$ is a derivation error,
  not a typo.

**(Type E) Visual evidence**
- **STRICTLY FORBIDDEN.** Any issue based on visual interpretation of a figure
  or plot, or extraction of datapoints from inside one. Must be flagged for
  deletion.
- Captions underneath figures count as text and are allowed.

**(Type F) Features-not-bugs**
- Not issues at all — intrinsic parts of the text's argument. The Red Team
  misread the text (e.g., confused the text's critique of prior literature with
  a flaw in the text itself).

**(Type G) Other**
- Anything else. **If there is no plausible defence, classify it as Other.**
