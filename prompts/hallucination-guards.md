# Standard Hallucination Guards

These guards apply to every Red Team and verification agent in the pipeline.

**VISUAL DATA IS FORBIDDEN.** No issue can be based on the visual interpretation
of a figure or plot, or any datapoint extracted from within a figure or plot.
Data must come from (a) the text, (b) tables, or (c) figure captions.
Interpretations of figures or extraction of datapoints from within figures are
**strictly prohibited**.

**OCR ERRORS:** If you find something that seems to directly contradict the
reported results (such as a regression coefficient), double-check that it is not
an OCR error. If there is any possibility of OCR error, **NOTE THE UNCERTAINTY**.

**TABLE READING (Coordinate Verification):**
1. List column headers EXACTLY as they appear.
2. Trace each data point: Row → Column explicitly.
3. If text says "A high, B low" but table shows reverse = "Narrative Inversion".
4. Interpret coefficients within the full model context (especially interactions).

**ATTACK WHAT'S ACTUALLY THERE:** Ensure you understand what the text actually
claims before critiquing it. A critique of a misreading is not a critique — it
is a false positive. Read carefully, then strike.

**ABSENCE VS. FALSITY:** A missing piece of documentation means "not documented,"
not "did not happen." Be precise in your language.
