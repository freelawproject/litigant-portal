# Agent evaluation baseline

Compare raw Bedrock questions (`raw`), the existing `LitigantAssistant` chat
engine (`old`), and `PortalAgent` with its Direct runtime (`new`). Raw receives
only the question: no system prompt, history, tools, or corpus. This is an API
baseline, not a measurement of chatgpt.com.

## Run

Run commands from the repository root. `make agent-eval` uses this directory's
independent uv project, lockfile, and `.venv`; it reads the root `.env` if present.
It does not install evaluation dependencies into the application environment or
Docker image.

```bash
# Full matrix: 3 systems × 2 models × 14 cases × 3 attempts = 252 attempts.
make agent-eval

# Small live run, including the separate Sol judge.
make agent-eval ARGS='run --models luna --cases nd-fee --repetitions 1 --slug smoke'

# Generate answers now; grade them separately later.
make agent-eval ARGS='run --systems raw --models luna --cases nd-fee --repetitions 1 --no-judge'
make agent-eval ARGS='judge evals/YYYYMMDD_HHMMSS-initial-baseline'
make agent-eval ARGS='judge evals/YYYYMMDD_HHMMSS-initial-baseline --model sol'

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

Old/new calls require the usual **already-running** Django development container
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

[cases.yml](cases.yml) contains eight real-reference and six fictional cases.
[references/](references/) freezes repository corpus content for answer keys,
with provenance and draft review status. It is not independently verified law.

The fictional chicken-law variants change the fee and procedural order while
retaining identical questions. Both include the 200-square-feet-per-chicken
boundary. Fixtures enter through normal corpus files and an evaluation database
flow. The new agent currently does not retrieve this content; the benchmark does
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

Results live in ignored `evals/YYYYMMDD_HHMMSS-slug/` (UTC). JSON and logs capture
visible answers, tool/model traces, usage, timing, judgments, corpus snapshots,
and recovery state. Local evaluator and container application provenance are
recorded separately. Timing excludes setup and judging; timeouts bound the actual
candidate child process. Temporary worker files are removed when its session ends.

Rejudging saves a new batch and preserves earlier answers and judgments. Reports
use the latest batch, including incomplete grading. Reweighting/comparison writes
a separate report; incompatible cases/references/rubrics cannot be pooled.
Reports and Matplotlib PNGs can be rebuilt without API calls or running services.

This internal suite has no automated tests or pre-commit test integration. Verify
changes with a small live run, fixture/restoration checks, and inspection of saved
JSON and charts. Inspect judge evidence before treating any run as a baseline.
