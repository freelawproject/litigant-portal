# State reduction and projection

This package owns state models, snapshot loading, database-free transitions, computed progress, and the Docassemble handoff. Application services still own identity resolution, glossary validation, transactions, and persistence.

The current checkpoint includes the domain layer, shared corpus conditions, stored-row adapters, guided selection and Continue actions, chat integration, and corpus cleanup. The optional System One backend is scaffolded only. The application is intentionally incomplete; the single feature migration, database rebuild, and live verification come during final assembly.

## Contract

`reduce(current_state, action)` returns an independent `StateType`. It does not query the database, read the clock, call a model, or mutate either input.

The Pydantic contracts reject unknown fields and carry explicit actor authority:

| Action                   | Authority          | Result                                                                             |
| ------------------------ | ------------------ | ---------------------------------------------------------------------------------- |
| `SetFactsActionType`     | Human or assistant | Save or clear the supplied facts. Changed assistant values require human review.   |
| `ConfirmFactsActionType` | Human              | Confirm named, nonempty facts last changed at or before the review card's `as_of`. |
| `MarkViewedActionType`   | Human              | Record a component signature within the snapshot's selected flow.                  |

An unchanged fact retains its timestamp, existing evidence, and confirmation. It can gain missing evidence or explicit human confirmation. A cleared value removes its evidence. Viewing history never changes fact values or confirmation.

## Application boundary

The existing write boundary in `app/services/topic_flow.py` is retained for the integration stage:

- `variable_answer_set` and `variable_answer_set_many` preserve the existing single-write and atomic-batch interfaces.
- `variable_answers_record` accepts the assistant's valid facts in one batch. `RecordFact` reports invalid siblings separately; the service cannot accept human confirmation authority.
- `variable_answer_confirm` retains the human confirmation endpoint's timestamp guard and excludes out-of-schema and currently inapplicable facts.
- `topic_flow_section_viewed` records a server-resolved component reference and signature for a human Continue action. The HTTP caller must establish applicability before invoking it.

The service locks the identity before reading its snapshot, validates the action against current glossary rows, invokes the reducer, and persists changed fields only. Django assigns persisted answer timestamps; the next snapshot reads those timestamps rather than reusing the reducer's in-memory result.

`FlowViewState` stores viewing history by identity and flow. Identity merging preserves the target's existing viewing record, transfers nonconflicting records, and deletes the source. Reset and deletion remove viewing history along with the identity's other data.

## Docassemble

`state/docassemble.py` owns the existing session client and explicit prefill mapping. HTTP redirects and fallback handling stay in the application view. `docassemble.request_interview` remains an intentional no-op lifecycle boundary; it creates no session, operation result, or completion status.

## System One

`system_one.reduce` and `system_one.project` are no-op placeholders with the same inputs as their Python counterparts. Both return `None`, perform no model calls, and leave their inputs unchanged. They are not wired into the application; Python reduction and projection remain active. Implementing the model backend and its validated result contracts is deferred.

## Conditions

`types.ConditionType` accepts `{variable, value}` comparisons with an optional `operator` (`equals` by default, or `not_equals`), and nested `all`, `any`, and `not` expressions. `condition_matches` returns true only for a satisfied condition. Missing or cleared prerequisites remain unknown under negation; they do not satisfy `not_equals`.

Variables retain `asked_when`, components and packet entries use `when`, and checkbox mappings retain `checked_when`. Corpus validation checks every nested comparison against the glossary and stores these expressions as JSON. Conditional pages must place their prerequisites on earlier pages.

`applicable_facts` evaluates prerequisites before dependents. Hidden answers stay stored with their evidence, review status, and timestamps. The projector excludes them from current requirements and outputs; restoring a matching condition makes them available again.

## Projection

`project(state, court_rules, time_context, limit=1)` accepts a flow-scoped snapshot, validated rules, and the explicit local calendar date. Components arrive in authored layout order. Their `content` is authored source text, including question wording and choices, supplied by the selector; candidates reference that content by component ID.

`state/selectors.py` adapts already-loaded answer rows into snapshots and the prefetched flow graph into court rules. The write service uses the snapshot adapter inside its existing identity lock. The rules adapter includes every authored interview page and preserves layout order, conditions, question wording, forms, and deadline metadata without embedding identity answers.

The result contains applicable variables in question order, answered and unconfirmed variables, missing required answers, applicable components with completion and `can_continue` status, selected form references, resolved deadlines, and the next N unfinished components. Python candidates have no fit score. Empty question groups, packets without forms or an available interview, and calendars without applicable deadlines are omitted.

Required questions remain unfinished until answered and confirmed. Optional questions can be skipped by viewing the component. Information and output components finish when their current content signature is viewed. Signatures incorporate authored content, applicable question definitions, selected forms, and computed deadlines, so a previously viewed output can become unfinished when its contents change.

The projector leaves its inputs unchanged and never records a view or confirms a fact. A flow mismatch or nonpositive candidate limit is rejected. Deadline calculation now lives here; application display formatting stays in `app/topic_flow/deadlines.py`.

The guided view displays projected candidates and links to every applicable component for revisiting. Saving accepts only that component's applicable questions and preserves valid siblings when another answer fails validation. Continue records the displayed content signature, rejects stale content, and cannot bypass required answers or their confirmation. Optional questions may be skipped. The calendar download uses the same projected deadlines as the page. These paths reuse the existing forms and work through ordinary GET and POST requests.

The assistant's identity prompt contains the active flow's projected guidance, facts, forms, deadlines, and progress. It refreshes each turn and after `LoadTopicFlow` or a fact change, using the turn's fixed local date. The stored snapshot masks private fact values and dates derived from private facts. Shared prompt artifacts contain no identity projection. Successful historical `LoadTopicFlow` payloads are replaced only in the outgoing model context; stored history stays intact, and citation diagnostics inspect the actual model request.

`ReviewFacts`, the active-flow briefcase, and Docassemble prefill use projected answers. Prefill additionally requires human confirmation. The briefcase follows the displayed chat thread, verifies thread ownership, and ignores late responses for a different thread. Hidden answers remain stored so changing a condition can reveal them again.

Both North Dakota name-change flows place conviction details in their own question group, conditional on the existing criminal-history answer. General criminal-history guidance remains unconditional. Fee-waiver answers select the additional packet form, and the standard flow computes the publication waiting date. The retired `on_page` flag is absent from the application schema and corpus; every question group uses projected applicability.

## Verification

Run the domain tests independently of the unfinished Django integration:

```sh
uv run --no-sync pytest -c /dev/null --noconftest -p no:django \
  litigant_portal/app/tests/test_state_reducer.py \
  litigant_portal/app/tests/test_state_rules.py \
  litigant_portal/app/tests/test_state_projector.py \
  litigant_portal/app/tests/test_topic_flow_deadlines.py
```

These checks make no database or model calls. Application and fresh-database verification remain part of final assembly.
