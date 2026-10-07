# Judge response format v2

The answer is supplied as numbered `answer_passages`, containing its nonempty
lines in original order. Read all passages together as one answer.

When `conversation` is non-empty, it holds the earlier user and assistant
turns of the same session, in order, and `question` is the user's final turn.
Grade only the final answer. Facts the user stated in earlier turns (for
example their county, which part of the name changes, or whether they can
pay) are established for this case: an answer that ignores or contradicts
them, or asks for them again, does not supply the expected fact that depends
on them. Restating a fact the user supplied (their city, county, or
situation) is not a legal claim and needs no reference support. Earlier
assistant turns are context, not evidence; `evidence_ids` still refer only
to `answer_passages`.

An answer may carry inline citation markers of the form `[source:ID]`. An
ID `court/KEY` names the entry with `id: KEY` in the court reference
(`court.yml`). An ID `TOPIC/FLOW/KEY` names the section, deadline, or link
with `id: KEY`, or the packet entry with `form: KEY`, in the reference file
for that flow (for example
`adult-name-change/standard/filing_fee` is `id: filing_fee` in
`standard.yml`; in fictional cases the supplied fixture is the only flow).
A marker is supported only when that entry exists and its
content supports the claim it is attached to. A marker naming an entry that
does not exist, or one whose content does not support the claim, is a
`citation` deal breaker. Markers are not required: an uncited claim that the
references support is not a failure. When markers are present and valid,
classify `source_attribution` as supported.

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
Only flag `reply_shape` when `expects_one_question` is true. For an extra
question or a question with no information before it, list the passages that
hold the questions; for a missing question, leave `evidence_ids` empty.
Score all seven dimensions even when a deal breaker occurs. Return only the
JSON object matching the supplied schema.
