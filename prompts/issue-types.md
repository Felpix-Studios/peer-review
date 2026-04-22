# Issue Type Classification

Used by the Blue Team, the Assessor, and the Dossier Builder.

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
