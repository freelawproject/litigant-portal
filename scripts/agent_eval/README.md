# Agent evaluation baseline

Compare raw Bedrock calls (`raw`) with the `LitigantAssistant` chat engine (`current`). Raw receives the user turns without a system prompt, tools, or corpus. This is an API baseline, not a measurement of chatgpt.com.

## Run

Run commands from the repository root. `make agent-eval` uses this directory's
independent uv project, lockfile, and `.venv`; it reads the root `.env` if present.
It does not install evaluation dependencies into the application environment or
Docker image.

```bash
# Default run: 2 systems × 2 models × 25 cases × 3 attempts = 300 attempts.
make agent-eval

# Small live run, including the separate Sol judge.
make agent-eval ARGS='run --models luna --cases nd-fee --repetitions 1 --slug smoke'

# Generate answers now; grade them separately later.
make agent-eval ARGS='run --systems raw --models luna --cases nd-fee --repetitions 1 --no-judge'
make agent-eval ARGS='judge /path/to/run'
make agent-eval ARGS='judge /path/to/run --model sol'

# Recover saved judge responses without API calls, then retry only failures.
make agent-eval ARGS='recover /path/to/run --dry-run'
make agent-eval ARGS='recover /path/to/run'
make agent-eval ARGS='judge /path/to/run --retry-failed --dry-run'
make agent-eval ARGS='judge /path/to/run --retry-failed'

# Offline: rebuild charts, compare compatible runs, or try different weights.
make agent-eval ARGS='report /path/to/run-a /path/to/run-b'
make agent-eval ARGS='report /path/to/run --facts-weight 0.8'
```

Replace `/path/to/run` and the comparison paths with the output directories printed by your own runs.

The CLI is `python -m scripts.agent_eval` in the evaluation environment, run
from the repository root. Edit [config.yml](config.yml) for the systems, model
aliases, judge, repetitions, cases, timeout, seed, weights, and pricing overrides.
Judge and candidate models may overlap. Credentials never belong in this file.

Orchestration, raw calls, judging, and charts run locally. Export
`AWS_BEARER_TOKEN_BEDROCK` locally for raw calls and judging. Raw-only runs,
judging saved answers, and offline reports do not require Docker.

Current chat calls require the usual **already-running** Django development container and its database/Redis services. The runner uses `docker compose exec -T django` to upload a temporary Python worker. That worker imports the container's app, uses its credentials and services, and streams artifacts back to the local run directory. No image rebuild, new container, volume mount, or application endpoint is needed. It creates normal database conversation records under an evaluation identity; those records remain after the run. It does not migrate or reset the database.

## Chat engine configuration and fixtures

The chat engine calls the site's fast model to generate a chat title. `legacy_fast_model: luna` temporarily selects Luna through the existing site setting; `null` preserves the current setting. The original and effective models are recorded, and the setting is restored afterward.

[cases.yml](cases.yml) contains fifteen real-reference cases, six fictional cases, and four multi-turn conversation cases. Cases with `history` are reported in the `conversation` group, separately from single-turn cases. Both systems run all selected cases.
[references/](references/) freezes repository corpus content for answer keys, with provenance and draft review status. It is not independently verified law. When updating the benchmark corpus, update the frozen files and their hashes in `provenance.json`, preserving the authored source IDs used by citation checks. Keep cases, references, and the rubric unchanged across runs you intend to compare.

A case may carry `history`: user turns sent on the same thread before `question`. Their replies are recorded in the attempt's `detail.transcript` and shown to the judge as context; only the final answer is graded. The current system continues one chat thread across turns and clears the evaluation identity's stored facts before each case, recording what the agent stored as `detail.stored_facts`. Raw replays the turns as a message list. Timing covers all turns of the case. The conversation cases (`nd-convo-*`) follow the personas in `docs/ai-tooling/qa-scripts/ai-agent-testing-script-nd-name-change.md`.

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

The fictional chicken-law variants change the fee and procedural order while retaining identical questions. Both include the 200-square-feet-per-chicken boundary. Fixtures enter the current chat engine through normal corpus files and an evaluation database flow. Raw receives no corpus.

Evaluations of the chat engine temporarily change site settings and may enable the fictional flow; other development requests can see those changes while the run is active. The worker holds the fixture lock, enforces child-process timeouts, and restores settings on normal exit, Ctrl-C, or controller disconnect. After a hard kill or failed cleanup, use the locally saved recovery journal:

```bash
make agent-eval ARGS='restore /path/to/run'
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

By default, results are written beneath Git-ignored `evals/`, in directories named `YYYYMMDD_HHMMSS-slug` (UTC). These files are generated locally and are not included in the repository. JSON and logs capture visible answers, tool/model traces, usage, timing, judgments, corpus snapshots, and recovery state. Local evaluator and container application provenance are recorded separately. Timing excludes setup and external grading, but includes runtime judge calls; timeouts bound the actual candidate child process. Temporary worker files are removed when its session ends.

Rejudging saves a new batch and preserves earlier answers and judgments. Reports
use the latest batch, including incomplete grading. Reweighting/comparison writes
a separate report; incompatible cases/references/rubrics cannot be pooled.
Reports and Matplotlib PNGs can be rebuilt without API calls or running services.

Only `raw` and `current` systems are supported for execution and reporting. The legacy `old` tag is accepted as `current`; other system names are rejected. Rebuilt summaries and charts use the canonical names; saved manifests, attempts, judgments, and their paths remain unchanged.

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
