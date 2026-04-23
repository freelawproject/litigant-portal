# Prompts as Infrastructure

## Principle

The prompt layer is the Litigant Portal's core system contract. All AI capability, court-specific content, flow conventions, and topic knowledge enter the product through one composition interface. Fixture prompts today and retrieval-backed, agentic-tool-enabled prompts tomorrow both satisfy the same contract — so the front end, the flow logic, and the user's experience don't change when capability deepens.

This isn't a new abstraction layer to build. It's a stance about what LP _is_: a guided conversation over legal process, where the AI is the medium and the structured conversation is the product.

## The composition contract

One function, four layers:

```python
build_system_prompt(phase, topic, court) -> str
```

| Layer     | Stable across                    | What it holds                                                                                                                             | Replaced by                     |
| --------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| **Base**  | Everything                       | Universal LP ethos — tone, UPL compliance, inform-first, "what before why," escalation ladder, scope-adjacent framing, privacy commitment | Nothing (always present)        |
| **Phase** | Topics + courts                  | Triage / Prepare / Resolve conventions — sidebar behavior, blocker pinning, deadline math, cascade rendering, end-goal threading          | Nothing (always present)        |
| **Topic** | Courts                           | Topic-specific legal framing — eviction concepts, name-change concepts, track forks, domain vocabulary                                    | RAG over topic corpus           |
| **Court** | Topics _(within a jurisdiction)_ | Jurisdictional content — forms, fees, procedural specifics, clerk contacts, handoff preferences, branding                                 | Court-configurable corpus / RAG |

Session state determines the current Phase. Topic and Court come from the deep-link URL or the topic-card click that started the session. Composition happens per-turn and returns a single system prompt string.

## Fixture-to-real upgrade path

Today, Topic and Court layers are Python strings (`chat/prompts/eviction_il.py`, `chat/prompts/adult_name_change_nd.py`). That's the fixture form.

As real infrastructure lands, the content source changes, not the contract:

| Capability                                         | Replaces                          | What shrinks                                                                                                |
| -------------------------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| RAG over topic corpus                              | Hardcoded Topic prompt            | Topic prompt shrinks to conversation framing; factual content comes from retrieval                          |
| RAG over court corpus                              | Hardcoded Court prompt            | Court prompt shrinks to branding + conventions; facts/forms/fees come from retrieval                        |
| Agentic tools (form assembly, deadline calc, etc.) | Inline instructions in Base/Phase | Tool definitions register into the model's tool list; Base/Phase reference them by name                     |
| Court self-service content                         | Hardcoded Court prompt            | Court layer is sourced from a per-court CMS or config API; courts change their own content without a deploy |

In each case, the front end, the flow orchestration, and the user-facing experience are untouched. Only the content source behind a layer changes.

## What this unlocks

- **New court adopts an existing topic** — provide Court-layer content, not code. If ND wants Adult Name Change and Minnesota wants the same topic, the Topic prompt survives; the Court prompt changes.
- **New topic ships** — write a Topic prompt, wire the deep link, update the topic grid. No front-end rework.
- **Demo-to-production parity** — demos and production use the same composition engine. Fixtures are the only difference. Every improvement to the contract benefits both.
- **Capability-driven upgrades** — RAG, agentic tools, memory, retrieval-augmented summarization can each land independently by replacing the content source for a specific layer. No coordinated rewrite.

## What this is not

- **Not a prompt-management platform.** No versioning, A/B testing, or observability infrastructure is implied by this architecture. Those can come later if they're needed.
- **Not an abstraction over everything.** Domain knowledge lives in prompt text, not in a generic DSL. The point is the composition interface, not the elimination of concrete content.
- **Not a replacement for `BASE_PROMPT`'s UPL and tone framing.** Base is the layer where those live; this architecture reinforces rather than replaces them.
- **Not a commitment to a specific retrieval technology.** "RAG" here is shorthand for whatever retrieval/augmentation mechanism we choose when the time comes. The contract is the interface; retrieval internals are implementation.

## Current state vs target state

**Current** — 2-layer, combined topic+jurisdiction:

```
chat/prompts/
├── __init__.py          build_system_prompt(topic, jurisdiction)
├── base.py              BASE_PROMPT (UPL, tone, conversation style, tools)
├── eviction_il.py       Illinois eviction + DuPage specifics (combined)
└── adult_name_change_nd.py   ND adult name change (combined)
```

**Target** — 4-layer, composable:

```
chat/prompts/
├── __init__.py          build_system_prompt(phase, topic, court)
├── base.py              enhanced with planning-log patterns
├── phases/
│   ├── triage.py
│   ├── prepare.py
│   └── resolve.py
├── topics/
│   ├── eviction.py
│   └── adult_name_change.py
└── courts/
    ├── dupage_il.py
    └── nd.py
```

The evolution from current to target is tracked by [#314](https://github.com/freelawproject/litigant-portal/issues/314) and its sub-issues.

## Evolution path

1. **Enhance Base** — absorb the planning-log patterns (info-not-advice, "what before why," escalation ladder, scope-adjacent framing) into `base.py`. Backward-compatible.
2. **Add Phase layer** — introduce `phases/triage.py`, `phases/prepare.py`, `phases/resolve.py` with the flow conventions captured during the ND demo planning work.
3. **Split combined prompts into Topic + Court** — extract `eviction_il.py` into `topics/eviction.py` + `courts/dupage_il.py`, and `adult_name_change_nd.py` into `topics/adult_name_change.py` + `courts/nd.py`.
4. **Update composition signature** — `build_system_prompt(phase, topic, court)`. Session state maps to current phase.
5. **Land RAG or agentic tools behind the contract** — as capabilities arrive, they replace content sources layer-by-layer without touching the composition interface.

Steps 1–4 live under #314. Step 5 is future work under separate tracking as each capability becomes real.

## Slug vocabulary

One canonical slug per topic, per court. Every surface — grid, URL, chat session, prompt registry — uses the same string.

- **Topic slugs** are lowercase-underscore identifiers that name the legal matter as-registered in `chat/prompts/topics/*.py`. Examples: `eviction`, `adult_name_change`. When a new topic ships, its module name in `topics/` is the canonical slug everywhere else.
- **Court slugs** are lowercase-underscore identifiers that name the court module in `chat/prompts/courts/*.py`. Examples: `dupage_il`, `nd`. A two-letter state code (`il`, `nd`) is a deprecated alias that maps to a default court via `_JURISDICTION_TO_COURT` in `chat/prompts/__init__.py`; prefer the explicit court slug in new code.

No aliases, no translation layers. If the grid's topic key doesn't match a module in `topics/`, the Topic prompt silently drops from composition — historically this happened and went unnoticed for a while. A regression test in `chat/tests/test_chat_session_topic.py::test_grid_eviction_slug_composes_topic_and_court_layers` reads the grid's eviction slug from `TOPICS` and asserts the composed prompt contains the eviction and court anchors; similar guards should exist for each new (topic, court) pair as they land.

## Rationale — why this emerged from two demos

Jane (DuPage eviction) shipped first with a combined Topic+Jurisdiction prompt file. Sandra (ND Adult Name Change) followed the same shape. Comparing them side by side, two things became obvious:

- **Phase-level conventions are duplicated.** How the sidebar populates, how blockers pin, how deadline math hydrates, how the cascade renders, how end-goal threading works — these aren't topic- or court-specific. They're flow conventions that should live in one place and compose with any topic+court.
- **Topic and Court interleave awkwardly in one file.** DuPage-specific courthouse details were mixed with generic Illinois eviction concepts. When a second state adopts Adult Name Change, we don't want to copy the topic prompt and edit out the ND specifics — we want to compose.

Writing the second demo surfaced the shape. Extracting layers now — before a third topic or a second court-on-existing-topic lands — keeps the refactor bounded and locks in the contract before it's stress-tested by production asks.

## References

- [#314](https://github.com/freelawproject/litigant-portal/issues/314) — parent: layered composition refactor
- [ND Adult Name Change planning log](./nd-name-change-planning-log.md) — the patterns that justify the decomposition
- [Jane's happy path](./happy-path-jane.md) — first demo narrative
- [Sandra's happy path](./happy-path-sandra.md) — second demo narrative
- `chat/prompts/base.py` — current Base prompt
- `chat/prompts/eviction_il.py` — current combined Topic+Jurisdiction for Jane
- `chat/prompts/adult_name_change_nd.py` — current combined Topic+Jurisdiction for Sandra
