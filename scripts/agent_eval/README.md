# Agent evaluation baseline

Compare raw Bedrock questions (`raw`), the existing `LitigantAssistant` chat
engine (`current`), and `PortalAgent` with its Direct runtime (`standalone`). Raw receives
only the question: no system prompt, history, tools, or corpus. This is an API
baseline, not a measurement of chatgpt.com.

## Run

Run commands from the repository root. `make agent-eval` uses this directory's
independent uv project, lockfile, and `.venv`; it reads the root `.env` if present.
It does not install evaluation dependencies into the application environment or
Docker image.

```bash
# Grounded-chat baseline: 2 systems × 2 models × 25 cases × 3 attempts = 300 attempts.
make agent-eval

# Include PortalAgent: 426 attempts, excluding its unsupported history cases.
make agent-eval ARGS='run --systems raw current standalone --slug all-systems'

# Small live run, including the separate Sol judge.
make agent-eval ARGS='run --models luna --cases nd-fee --repetitions 1 --slug smoke'

# Generate answers now; grade them separately later.
make agent-eval ARGS='run --systems raw --models luna --cases nd-fee --repetitions 1 --no-judge'
make agent-eval ARGS='judge evals/YYYYMMDD_HHMMSS-initial-baseline'
make agent-eval ARGS='judge evals/YYYYMMDD_HHMMSS-initial-baseline --model sol'

# Recover saved judge responses without API calls, then retry only failures.
make agent-eval ARGS='recover evals/RUN --dry-run'
make agent-eval ARGS='recover evals/RUN'
make agent-eval ARGS='judge evals/RUN --retry-failed --dry-run'
make agent-eval ARGS='judge evals/RUN --retry-failed'

# Offline: rebuild charts, compare compatible runs, or try different weights.
make agent-eval ARGS='report evals/RUN_A evals/RUN_B'
make agent-eval ARGS='report evals/RUN_A --facts-weight 0.8'
```

The CLI is `python -m scripts.agent_eval` in the evaluation environment, run
from the repository root. Edit [config.yml](config.yml) for the systems, model
aliases, judge, repetitions, cases, timeout, seed, weights, and pricing overrides.
Judge and candidate models may overlap. Credentials never belong in this file.

Orchestration, raw calls, judging, and charts run locally. Export
`AWS_BEARER_TOKEN_BEDROCK` locally for raw calls and judging. Raw-only runs,
judging saved answers, and offline reports do not require Docker.

Current/standalone calls require the usual **already-running** Django development container
and its database/Redis services. The runner uses `docker compose exec -T django`
to upload a temporary Python worker. That worker imports the container's app,
uses its credentials and services, and streams artifacts back to local `evals/`.
No image rebuild, new container, volume mount, or application endpoint is needed.
It creates normal database conversation records under an evaluation identity;
those records remain after the run. It does not migrate or reset the database.

## Legacy configuration and fixtures

The legacy agent also calls the site's fast model to generate a chat title.
The original smoke run's answers succeeded, but its Haiku title calls failed
because that model did not support the selected chat-completions API endpoint.
`legacy_fast_model: luna` temporarily selects Luna through the existing site
setting; `null` preserves the current setting. Original/effective models are
recorded, and the setting is restored afterward. Legacy agent code is unchanged.

[cases.yml](cases.yml) contains fifteen real-reference cases, six fictional
cases, and four multi-turn conversation cases. Every case with `history` takes
the `conversation` group, because the standalone system does not run history cases;
keeping them out of `real` keeps that group comparable across all three
systems.
[references/](references/) freezes repository corpus content for answer keys,
with provenance and draft review status. It is not independently verified law.
When the corpus changes, copy the source files over the frozen ones and update
the hashes in `provenance.json`; a stale reference makes the judge penalize
answers that follow the current corpus. The frozen files carry the authored
source ids from #949, which the citation check depends on. The post-949 baseline
references include the current ND corpus. Keep cases, references, and the rubric
unchanged between this baseline and its later judged-chat comparison.

A case may carry `history`: user turns sent on the same thread before
`question`. Their replies are recorded in the attempt's `detail.transcript`
and shown to the judge as context; only the final answer is graded. The current
system continues one chat thread across turns and clears the evaluation
identity's stored facts before each case, recording what the agent stored as
`detail.stored_facts`. Raw replays the turns as a message list. The standalone
system takes single-turn cases only, so the runner does not schedule it for
history cases and the planned attempt count excludes them. Timing covers
all turns of the case. The
conversation cases (`nd-convo-*`) follow the personas in
`docs/ai-tooling/qa-scripts/ai-agent-testing-script-nd-name-change.md`.

A case may set `expects_one_question: true` when its final turn lands
mid-interview, so the graded reply must give information first and end with
exactly one question for the next missing fact. The `nd-shape-*` cases carry
it: a first turn, a turn where the user volunteers several facts at once, and
a turn deep in the first-name persona. Single-turn information cases leave it
unset. The judge may flag the `reply_shape` deal breaker only on these cases:
more than one substantive question, a question with no information before it,
or no question at all. A flag on any other case is an invalid grade. The
harness also adds a `reply_shape` failure itself, without the judge, when such
a case's answer does not end with a question (a `?` in a heading or in an
echo of the user's words does not count; a `[source:ID]` citation, quote, or
bracket after the question is ignored). Both zero `overall` like any other
deal breaker; cases without the flag are not affected.

The fictional chicken-law variants change the fee and procedural order while
retaining identical questions. Both include the 200-square-feet-per-chicken
boundary. Fixtures enter through normal corpus files and an evaluation database
flow. The standalone agent currently does not retrieve this content; the benchmark does
not insert it into the candidate prompt. Raw receives no corpus.

Legacy runs temporarily change site settings and may enable the fictional flow;
other development requests can see those changes while the run is active. The
worker holds the fixture lock, enforces child-process timeouts, and restores
settings on normal exit, Ctrl-C, or controller disconnect. After a hard kill or
failed cleanup, use the locally saved recovery journal:

```bash
make agent-eval ARGS='restore evals/YOUR_INTERRUPTED_RUN'
```

## Scores and charts

[rubric.md](rubric.md) defines the critical failures and seven dimensions. Facts
receive 70% and qualitative dimensions 30%, equally weighted within each group.
Each dimension uses 0–4 anchors. Support in the references suffices; displayed
citations are not mandatory. Honest deferral is scored and reported separately
from answering; correct answers in both changed variants demonstrate adherence.

Judges cite numbered answer passages using `evidence_ids`; the harness resolves
them to exact answer text. Explanations are separate. Unknown/duplicate IDs,
missing facts or scores, and missing asserted values fail grading. Omissions and
uncertainty use null values rather than invented amounts or eligibility results.
The response protocol and schema are frozen per judgment batch.

Charts show **weighted quality before gates**. A bright red point and the
**Critical failure** legend flag any critical failure among that system/model's
graded answers; labels show the count. Quality plots include variation bars.
JSON retains both `quality` and the gated `overall`, which becomes zero for a
critical failure. Missing/ungraded attempts leave aggregate scores unavailable;
execution failures contribute zero and appear separately in the outcome chart.

Cost-versus-quality plots show unknown-cost results in a separate **Cost
unavailable** area, without assigning them an invented price. Auxiliary title
failures are execution diagnostics, separate from rubric critical failures.
System cost includes all observed calls, including titles; judge costs are
separate. Missing usage/pricing keeps total cost unknown. Known subtotals include
priced calls even when another call's cost is missing. These are estimates;
SDK-internal retries without usage cannot be reconstructed as billed costs.

## Artifacts and manual checks

Each observed call records `request.timeout` and `request.num_retries`, including null when the application leaves the value to provider defaults. This records the request without changing it. Calls also record `error_category` (`timeout`, `provider_error`, or null for no observed failure), including errors raised while consuming a stream. Each `current` attempt saves `runtime_judge_model` before invoking the chat engine; null means disabled. The worker's whole-attempt deadline is recorded separately as `attempt_timeout`.

Reports include generation-timeout attempt counts, attempt-deadline counts, runtime judge review outcomes from exported audit rows, and the existing external grading diagnostics. Runtime review counts include every correction review and are not counts of failed answers. Unknown legacy diagnostics remain unknown; missing metadata is not evidence of zero failures. Report settings use `provider_default` for recorded null values and `unknown` for absent legacy fields. Scores, costs, and execution-failure treatment are unchanged.

Results live in ignored `evals/YYYYMMDD_HHMMSS-slug/` (UTC). JSON and logs capture
visible answers, tool/model traces, usage, timing, judgments, corpus snapshots,
and recovery state. Local evaluator and container application provenance are
recorded separately. Timing excludes setup and external grading, but includes runtime judge calls; timeouts bound the actual
candidate child process. Temporary worker files are removed when its session ends.

Rejudging saves a new batch and preserves earlier answers and judgments. Reports
use the latest batch, including incomplete grading. Reweighting/comparison writes
a separate report; incompatible cases/references/rubrics cannot be pooled.
Reports and Matplotlib PNGs can be rebuilt without API calls or running services.

Legacy `old` and `new` system tags are accepted on read as `current` and
`standalone`. Rebuilt summaries and charts use the canonical names; saved
manifests, attempts, judgments, and their paths remain unchanged.

`recover` revalidates saved raw judge responses offline, including legacy quoted
evidence with Markdown, punctuation, and capitalization differences. It preserves
the original records and records recovered judgments in a new batch. Unrecoverable
grades remain explicit; recovery itself exits successfully after reporting them.

`judge --retry-failed` carries forward valid judgments and makes one call per
unresolved saved answer. It uses the same judge model and never regenerates
candidate answers. There are no automatic retry loops. Both commands support
`--dry-run` without credentials, API calls, or output changes. A retry with nothing
left to grade also makes no calls. The ordinary `judge` command still rejudges all
completed answers. Copied/recovered judgments never duplicate paid-call costs.

Live grading prints each result and ends with failure counts and reasons. Invalid
judgments leave the batch incomplete and make `run`/`judge` exit nonzero; an
answer's rubric critical failures do not. Reports show coverage and recovery
provenance, retaining original and replacement judge costs separately from
candidate costs.

Judge format v4 allows `contradicted` with `value: null` for a denial without an
asserted amount. It still requires evidence and applies the critical-failure
zero. Supported numeric/boolean facts require an extracted value. Saved v1/v2
responses retain their original validation rules; v3's `asserts_value` flags
are validated and removed on read without changing saved files. Use
`judge RUN --retry-failed` for unresolved older judgments. Accepted judgments
are retained, and reports record any mix of format versions.

Focused eval tests run in the fast suite:

```bash
uv run --locked --extra dev tox -e fast -- litigant_portal/app/tests/test_agent_eval.py litigant_portal/app/tests/test_agent_eval_runtime.py -q
```

Verify live changes with a small run or failed-judgment retry and inspection of
saved JSON and charts. Fixture changes also need restoration checks. Inspect
judge evidence before treating any run as a baseline.

## Judged chat handoff

For Jessica's pilot review, include:

- The actual runtime judge model and generation timeout/retry settings for both runs. The eval config's `judge_model` selects the external grader; it does not enable runtime judging.
- Existing quality, critical-failure, latency, and cost results, alongside generation-timeout attempts, whole-attempt deadlines, and runtime judge verdicts/call failures. This comparison measures complete configurations, including the timeout difference, rather than isolating judge quality.
- The coverage limit: prose accompanying tool calls, including fact-recording calls, is released without judge approval and can contain substantive answers. Discuss this separately from fail-open on judge errors; do not claim that all visible answers were reviewed.
- The release behavior when corrections are exhausted or the judge fails: the answer is flagged and shown with a separate notice, "Warning: This answer could not be fully verified and may contain errors." Display and copying use the current translated template wording; Markdown exports mark the heading `[unverified]`, and JSON exports preserve the stored metadata. Both waiting and warning copy are provisional pending team agreement; Jessica's fail-open sign-off remains required before pilot enablement. Per-operation timeouts and heartbeats do not establish a maximum total turn duration.
