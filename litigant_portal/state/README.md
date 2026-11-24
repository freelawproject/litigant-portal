# State transitions

This package owns database-free state transitions. Django services own identity resolution, glossary validation, transactions, persistence, and external operations.

## Contract

`reduce(current_state, action)` returns an independent `StateType`. It does not query the database, read the clock, call a model, or mutate either input.

The Pydantic contracts reject unknown fields and carry explicit actor authority:

| Action | Authority | Result |
| --- | --- | --- |
| `SetFactsActionType` | Human or assistant | Save or clear the supplied facts. Changed assistant values require human review. |
| `ConfirmFactsActionType` | Human | Confirm named, nonempty facts last changed at or before the review card's `as_of`. |
| `MarkViewedActionType` | Human | Record a component signature within the snapshot's selected flow. |

An unchanged fact retains its timestamp, existing evidence, and confirmation. It can gain missing evidence or explicit human confirmation. A cleared value removes its evidence. Viewing history never changes fact values or confirmation.

## Application boundary

Live writes use the existing services in `app/services/topic_flow.py`:

- `variable_answer_set` and `variable_answer_set_many` preserve the existing single-write and atomic-batch interfaces.
- `variable_answers_record` accepts the assistant's valid facts in one batch. `RecordFact` reports invalid siblings separately; the service cannot accept human confirmation authority.
- `variable_answer_confirm` retains the human confirmation endpoint's timestamp guard and excludes out-of-schema facts.
- `topic_flow_section_viewed` records a server-resolved component reference and signature for a human Continue action. The HTTP caller must establish applicability before invoking it.

The service locks the identity before reading its snapshot, validates the action against current glossary rows, invokes the reducer, and persists changed fields only. Django assigns persisted answer timestamps; the next snapshot reads those timestamps rather than reusing the reducer's in-memory result.

`FlowViewState` stores viewing history by identity and flow. Identity merging preserves the target's existing viewing record, transfers nonconflicting records, and deletes the source. Reset and deletion remove viewing history along with the identity's other data.

## Docassemble

`docassemble.request_interview` is an intentional no-op lifecycle boundary. It creates no session, operation result, or completion status. The existing user-initiated interview launch remains in the application service.

## Conditions

`rules.ConditionType` accepts `{fact, equals}` expressions and nested `all`, `any`, and `not` expressions. `condition_matches` returns true only for a satisfied condition. Missing or cleared prerequisites remain unknown under negation; they do not satisfy `not_equals`.

Existing question gates and packet conditions use this evaluator through their current row adapter. The corpus schema and storage still use their existing condition fields until the next integration slice replaces those representations.

## Verification

Reducer tests run without a database or model calls. The existing answer, confirmation, and agent-tool tests cover the integrated write paths. Focused PostgreSQL tests cover owner locking, batch rollback, and viewing-state ownership and deletion.
