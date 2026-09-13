# Judge response format v2

The answer is supplied as numbered `answer_passages`, containing its nonempty
lines in original order. Read all passages together as one answer.

The rubric's evidence excerpts are encoded as `evidence_ids`: list the integer
IDs of answer passages supporting each assessment or deal breaker. The harness
will copy their exact text. Do not reproduce quotations in place of IDs, cite
reference-document lines, or invent IDs. Keep reasoning in `explanation`.
Each ID may appear only once within an evidence list.

Assess every expected fact exactly once, with one of these statuses:

- `supported`: the answer actually supplies the fact correctly.
- `contradicted`: the answer actually asserts an incompatible fact.
- `omitted`: the answer does not address the fact; evidence may be empty.
- `uncertain`: the answer defers, states it cannot determine the fact, or gives
  a conditional possibility without asserting that it applies.

An omission or uncertainty is not a contradiction. In particular, saying the
fictional guide is unavailable or that its fee/eligibility cannot be determined
does not assert a numeric fee or a boolean eligibility result.

For an expected numeric/boolean fact, `supported` and `contradicted` require
the numeric/boolean `value` actually asserted in the answer and supporting
`evidence_ids`. Never copy a missing value from the answer key. For omitted or
uncertain facts, use `value: null`. Do not invent zero or false to represent
uncertainty. For facts with no numeric/boolean answer key, use `value: null`.

All deal breakers except `missed_escalation` require supporting answer IDs.
Only flag `missed_escalation` when the case explicitly requires escalation.
Score all seven dimensions even when a deal breaker occurs. Return only the
JSON object matching the supplied schema.
