# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Access to justice portal for self-represented litigants. Django 6.0 with server-rendered components (Django Cotton), Tailwind CSS v4, and Alpine.js for reactivity.

## Current Focus: Beta Demo — Housing Eviction Flow

Building a complete eviction flow from discovery to resolution for court partner demos. One topic, end-to-end, at production quality — every button/link does something, no placeholders. Court-neutral information where partner-specific data isn't available yet.

- [Milestone](https://github.com/freelawproject/litigant-portal/milestone/3) - Beta Demo: Housing Eviction Flow

## Environment Philosophy

`docker-compose.yml` is **local development only** — Postgres (pgvector), Redis, Django, and Caddy on one machine. Production is deployed outside this repo and consumes nothing from this file (see [Production](README.md#production)).

| Environment | Chat Provider | Config Source                        |
| ----------- | ------------- | ------------------------------------ |
| Local dev   | AWS Bedrock   | `docker-compose.yml` + `.env`        |
| CI          | None (mocked) | `tox.ini` — tests mock all providers |

The chat model is chosen in the admin settings UI (`BedrockModel` enum), defaulting to GPT-5.6 Luna. Setup commands live under Commands below.

## Commands

**`make lint`, `make test`, `make pre-commit`** — sandbox restrictions prevent Claude from running these Docker- and Postgres-backed targets. Mitch runs the full lint/test workflow as part of his own process. A single post-commit mention is plenty; don't re-prompt about it across the commit/PR steps.

**DB-free fast tests** — when `.tox/fast` exists _and_ is current, Claude can run a focused test directly with `.tox/fast/bin/pytest <path>`. **Existence is not enough:** the env is built from `uv.lock`, and a stale one fails at import (`ModuleNotFoundError`) rather than reporting a test failure. After any dependency change, `tox -e fast --recreate`. Use that suite for a real RED→GREEN cycle on non-DB units: write the focused test, run it and confirm that it fails for the expected reason, implement the change, then rerun it to green. Tests marked `postgres` require `make test` and Docker. The fast marker filter is not a complete database-isolation boundary: unmarked tests may still use Django's database, so run only focused tests already known to be DB-free through this path.

### Local Development (Docker)

```sh
cp .env.example .env        # Add your AWS_BEARER_TOKEN_BEDROCK
make docker                 # Start dev environment
make docker-bash           # Shell into container
make docker-down            # Stop containers
make docker-up-build        # Rebuild the image, then start — after a dependency change
```

**`make docker-down` does not rebuild.** It stops containers; the next `make docker` reuses the same image. When `uv.lock` or `pyproject.toml` has moved (a pull, a branch switch), use `make docker-up-build` — the Dockerfile installs dependencies in an early layer keyed on those two files, so nothing picks up a lockfile change without it. Symptom of skipping it is the same `ModuleNotFoundError` the stale tox env gives. `make docker-clean` is **not** the fix — it drops volumes and takes the Postgres data with them.

**Dev URL:** `http://localhost` (or `http://portal.localhost`). Caddy runs on port 80 — **not** `:8000`. The `:8000` is the container-internal gunicorn/runserver port that Caddy proxies to (see `docker/caddy/Caddyfile`).

### Testing & Linting

```sh
make test                   # Run the test suite in the Docker container (requires `make docker`)
make lint                   # Lint and format all code (via pre-commit)
```

## Pre-commit Hooks

Pre-commit runs automatically on commit. Key hooks:

- **ruff** - Python linting/formatting
- **djlint** - HTML template linting (errors only, no auto-formatting)
- **prettier** - JS, JSON, CSS, Markdown, YAML formatting
- **csp-inline-check** - Blocks inline event handlers (CSP compliance)

Run all hooks manually: `pre-commit run --all-files`

**Note:** djlint runs in **lint-only mode** (no auto-formatter). Its formatter was mangling template tags inside HTML attributes — the manual conventions that replace it live in the global `django-templates` skill (see Template Formatting below).

### Before Committing

Mitch runs this before commits (especially after rebases or batch edits) — it's his routine, not a step Claude needs to prompt:

```bash
make pre-commit   # lint → test, short-circuits if lint fails/fixes anything
```

Equivalent to `make lint && make test`. If lint auto-fixes files, the target stops before tests — re-stage the changes and re-run. The name mirrors the `pre-commit` hook tool intentionally — same concept, different invocation surface.

### Template Formatting

No auto-formatter for `.html` templates — djlint runs lint-only. **Load the global `django-templates` skill before writing or editing any template**; it holds the full Prettier-inspired conventions (attribute wrapping, template-tags-stay-on-one-line, self-closing, quotes, blank lines). A custom Prettier/Cotton plugin is a WIP to replace the manual rules — LP is its home.

## Content style (user-facing copy)

Rules for authoring user-facing content — corpus YAML, UI strings, and prompt layers that shape chat output.

**There are currently two corpus trees, and both are live.** Know which one you are editing:

| Tree                            | Read by                                  | Serves                                                                        |
| ------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------- |
| `litigant_portal/content/*.yml` | `app/topic_flow/registry.py`             | **The live public flow pages.** Flat, one file per `(court, topic, role)`     |
| `litigant_portal/corpus/`       | `app/selectors/corpus.py`, `sync_corpus` | Database rows. Court-scoped tree plus a shared variable glossary and `forms/` |

Both are hand-maintained and each is validated at startup by its own Django system check (`apps.py` registers `checks.corpus` and `topic_flow.checks`). Editing one does not update the other — a change to `corpus/` alone will not alter what the public page renders, and the failure is silent. Which tree retires, and when, is an open decision under #179.

The rules below apply to whichever tree you are authoring in:

- **No em-dashes.** Use a period, comma, colon, or parentheses instead. Em-dash-heavy prose reads as AI-generated and undermines user trust (legal review, #620). Dev-facing text (code comments, docs, commit messages) is exempt.
- **Corpus info bodies: one line per paragraph.** The renderer pipes `body` through Django's `linebreaks`, so every newline becomes a `<br>` — hard-wrapped prose breaks mid-sentence on the page. Separate paragraphs with blank lines; never wrap a paragraph across source lines.
- **Dash-prefixed lines** (`- item`) render as visual line-broken lists (not semantic `<ul>`) until #518 adds rich text to info bodies. Links in body prose are not supported yet (#518) — route them through the corpus `resources`/`contacts` sections instead.
- **Never label resources or forms "official."** Courts reserve "official" for institutionally designated things — ND's own site uses it only for official county newspapers, the official record of the Court, and to disclaim that Self Help Center forms "aren't official court forms" (#646). Attribute instead of anointing: say whose page or form it is ("the North Dakota Legal Self Help Center's name-change page").
- **Solve directly; escalate to legal aid sparingly.** LP's job is to answer the litigant's question and resolve their issue directly wherever it can (explain the process, the deadlines, how a step works, what to bring). Route to legal aid only when (a) we genuinely can't help — a case-specific legal _judgment_, the UPL boundary ("will this defense win for me") — or (b) the issue is serious enough to require it (illegal lockout, imminent set-out, safety). Don't tell users to "get a lawyer" or "call an attorney": whether legal aid then brings in an attorney is _their_ call, not ours. Our audience is self-represented on a phone precisely because an attorney isn't within reach, so a reflexive "see a lawyer" tells them the tool can't help them (#611).

## Review requests and CODEOWNERS

CODEOWNERS puts **every** owner on **every** PR, but the ruleset requires only **one** approval to land. So a PR showing several pending reviewers is the normal state, not drift.

**Don't flag an unassigned PR for having outstanding reviewers.** Flag it only when:

- Mitch is in the PR's **`assignees`** field — check `assignees`, _not_ `reviewRequests`. CODEOWNERS fills `reviewRequests` on every PR, so it carries no signal; `assignees` means the PR is his to move. Or
- it has been **waiting on Mitch for more than a day** — his review is the one outstanding and nothing else is blocking it

Everything else is noise. This applies to the morning briefing, board audits, and any PR sweep.

## Issue creation

See [`docs/wiki/issue-conventions.md`](docs/wiki/issue-conventions.md) for the full label color scheme and template rationale.

New issues use the templates in `.github/ISSUE_TEMPLATE/`. Blank issues are disabled in `config.yml`, so the web UI forces a template; the CLI must opt in via `--template`.

| Template          | Auto-label    | Use for                                                                          |
| ----------------- | ------------- | -------------------------------------------------------------------------------- |
| `bug-report.yml`  | `bug`         | Something broken — environment + accessibility-impact (optional)                 |
| `enhancement.yml` | `enhancement` | Improvement or change — problem + what you'd like + mockups (optional)           |
| `task.yml`        | `task`        | Chore, refactor, docs, infra, tech debt — what + why (optional) + DoD (optional) |
| `qa-round.yml`    | `qa`          | QA round — request side + findings side, two halves in one issue                 |

**No title prefixes** — the auto-applied label carries the type signal. Filers can layer additional labels at creation (e.g., `tech-debt`, `frontend`) or during triage.

**Priority and size are not in the templates** — they're assigned by the team during sprint grooming, not by the filer.

**Security vulnerabilities** route through `SECURITY.md` at the repo root, which points to FLP's VDP (`https://free.law/vulnerability-disclosure-policy/`). The GitHub "Report a security vulnerability" chooser entry picks up `SECURITY.md` automatically.

When filing from the CLI:

```bash
gh issue create --template bug-report.yml
gh issue create --template enhancement.yml
gh issue create --template task.yml
gh issue create --template qa-round.yml
```

**Prefilled forms (`make file-issue`).** `gh issue create` can't post to our YAML issue _forms_ non-interactively — it only fills the legacy free-text body, so structured fields and auto-labels are lost. Until `gh` supports forms, `make file-issue` turns a self-describing content blob into a prefilled issue-form URL (opens a browser, or prints the URL when open is unavailable, e.g. in a sandbox). The blob declares its own `type:` and `title:`, then one section per template field id (`[what]`, `[why]`, `[dod]` for a task; `[problem]`, `[proposal]` for an enhancement — match the ids in `.github/ISSUE_TEMPLATE/`):

```bash
make file-issue <<'EOF'
type: task
title: Short, specific title

[what]
What needs to change.

[why]
Motivation.
EOF
# or: make file-issue FILE=issue.md
```

Field ids are validated against the chosen template — a section that doesn't match (wrong field or wrong template) warns and would render blank. The label is applied by the template; set assignee/priority/size in the browser. See `scripts/file_issue.py` for the full format and accepted type aliases.

## Sprint mapping

When someone references a sprint by its web-team letter/artist name ("the Ed Sheeran sprint", "Sprint F"), translate to the matching LP Iteration on board #75 via the sprint-map crosswalk (JI-team record kept outside the repo; the board/vault tooling holds the current copy), then pull the work from #75 + git. This crosswalk is LP-specific — other JI repos don't necessarily align with the web-team retro, so it lives here, not in org-level instructions.

## Sizing & estimation

The compact rules (board mechanics live at the org level; sizing history, anchors, and calibration records are JI-team material, kept outside the repo):

- **Scale:** XS 0.5 (~1–2h) · S 1 (half day) · M 3 (1–2 days) · L 5 (3–4 days), calibrated to AI-assisted effort. Size is the one human input; the board derives Estimate.
- **Size the work, not the diff** — a one-line fix after three days of debugging isn't an XS; a 600-line mechanical rename can be. Incident work: size the diagnosis. Count off-repo work (content authoring, infra, verification).
- **XL is a flag, not a size** — split into sub-issues before it enters a sprint.
- **P0 is fires only** — must ship today and/or prod is down. Never "important."
- **When in doubt, size smaller**, note the reasoning in the issue, and let iteration review correct the scale. An estimate is a forecast, not a promise.

## Architecture

**Open contracts:** design partner-facing data surfaces (corpus schemas, file formats, API shapes) around explicit validated contracts, never around a particular producer or tool. Validation at the boundary enforces conformance; how the data was produced stays on the producer's side. The worked example is the Topic Flow corpus — see the `topic_flow/schema.py` module docstring. Apply the same pattern to new surfaces (ingestion, search).

### Code Layout: domain below, surface above

**The data layer groups by domain; everything a user touches groups by surface.** Models and their utilities get reused across many pages, so they're organized around the data. Endpoints and templates serve exactly one page, so they're organized around that page.

**By domain** — `models/`, `selectors/`, and `services/` each carry one module per domain, and the three agree on module names:

| Domain        | Holds                                                                                                       |
| ------------- | ----------------------------------------------------------------------------------------------------------- |
| `site`        | Global site settings and court config                                                                       |
| `topic_flow`  | Topics and topic flow data (spans admin and public surfaces)                                                |
| `corpus`      | Corpus schemas, YAML loading, and sync into `topic_flow` rows (selectors + services only; no models module) |
| `user`        | Identity, profile, and group membership toggles                                                             |
| `upload`      | Attachment upload and its helper logic                                                                      |
| `chat_engine` | Threads, messages, streaming                                                                                |

**Never name a data-layer module after the page that consumes it.** Site settings apply app-wide; topic utilities serve both the admin editor and the public flow page. Naming either one `admin` mislocates it the moment a second caller shows up — which is exactly what happened to the module this layout replaced.

**Naming:** services and selectors are `{model_name}_{action}` — `site_get`, `topic_create`, `user_identity_merge`, `user_upload_llm_parts`. Allow some liberty when a utility genuinely implicates two models equally. Anything not part of a module's public surface takes a leading underscore. Single-row selector verbs encode miss behavior: `*_get` raises on a missing row, `*_find` returns None — pick the verb by how callers treat a miss.

**Reads are selectors, writes are services.** `user_list` reads, so it's a selector; `user_developer_toggle` writes, so it's a service.

**Cross-layer constants get their own module**, so no domain module has to import a constant out of another one: cache keys in `app/cache.py`, group and permission names in `app/permissions.py`. Each is read, written, and invalidated from a different layer, and anchoring one to any single consumer makes the other two reach sideways for it.

**Cached reads are invalidated at commit, never before.** A selector that caches wears a `timeout=None`, and every service that writes the same rows wears `@busts_cache(KEY)` from `services/utils.py`. Deferring the delete to commit is the whole point: an immediate delete lets a reader on another connection repopulate the key with the pre-commit value, and nothing busts it a second time, so the stale copy is permanent. The same rule binds management commands — `transaction.on_commit`, not a bare `cache.delete`.

**Permissions.** Admin access is the `app.manage_site` and `app.manage_developers` permissions, carried by the `Admins` and `Developers` groups (provisioned by a `post_migrate` receiver in `signals.py`). Check them with `request.user.has_perm(...)` in views and `{% if perms.app.manage_site %}` in templates — don't wrap either in a selector. Page views use Django's `@permission_required(..., raise_exception=True)`; the JSON API keeps its own `manage_site_required` / `manage_developers_required` decorators, because the built-in renders an HTML 403 where those endpoints must return a JSON body. These are deliberately separate from the auto-generated `add/change/delete/view` permissions that gate Django admin. Full reference: [`docs/wiki/permissions.md`](docs/wiki/permissions.md).

**`app/topic_flow/` is not a data-layer module.** It's the corpus engine (schema, registry, renderer, downloads) that reads YAML from `litigant_portal/content/` — the tree that renders the public pages, not the `litigant_portal/corpus/` tree that syncs to the database (see Content style above). The `topic_flow` entries under `models/`, `selectors/`, `services/`, and `views/` are the data layer for the `Topic` rows the corpus is attached to. Two different things sharing a name; always import both absolutely.

**By surface** — views, templates, JS, and the URL pattern lists:

- **`views/pages.py`** — views that render a page. Keep them thin; let endpoints do the work so pages stay reactive.
- **`views/<surface>.py`** — one endpoint module per surface (`admin`, `assistant`, `topic_flow`). Not every surface needs one.
- **`templates/pages/<surface>/`** — that surface's templates. Shared UI becomes a Cotton component under `templates/cotton/`, never a copied partial.
- **`static/js/<surface>.js`** — that surface's Alpine components; cross-cutting ones live in `components.js`.
- **`urls.py`** — one pattern list per group (`app_patterns`, `assistant_patterns`, `admin_api_patterns`), each `include`d under its own namespace.

**`utils.py`** — any package may carry one for helpers shared across its own modules, like the JSON permission decorators in `views/utils.py`.

A `library` domain (importing court and topic configs from the content library) is planned but does not exist yet — its absence is deliberate, not an oversight.

### Front-End Principles

When choosing how to implement UI behavior, follow this priority order:

1. **Django/Cotton + HTML/Tailwind first** — solve it server-side or with semantic HTML + CSS before reaching for JS. Cotton components, Django template logic, Tailwind utilities, native elements (`<details>`, `<dialog>`, CSS animations) cover most needs.
2. **Alpine.js is reactivity only** — show/hide, toggle, event binding, dynamic attribute binding. Alpine should not contain rendering logic, layout decisions, or anything that HTML/CSS can handle.
3. **Named components, dot-paths only** — CSP build requires `Alpine.data()` registrations. No inline expressions in templates. Pre-compute values as getters/methods.
4. **`data-*` attributes for config** — pass Django values to Alpine via `data-*` attributes, read them in `init()`. Never use `x-init` assignments or pass `$event` to handlers (Alpine auto-passes it).
5. **Reference repos** — [CourtListener](https://github.com/freelawproject/courtlistener) and [free.law](https://github.com/freelawproject/free.law) have solved most Django + Alpine + CSP patterns at scale. When hitting a seemingly blocking JS/Alpine problem, check those repos for working patterns before inventing a new approach.

**Layout stability (WCAG + mobile-first):**

Every page follows the same frame: **site header → sub-header (contextual) → content (scrollable)**. The sub-header varies per view (topic cards on home, topic context on chat, etc.) but is always in the same position and never shifts when state changes. Content is the only area that grows and scrolls.

- **No mode-switching layouts.** Never toggle between completely different DOM structures based on state (e.g., hero vs. chat mode). Users with cognitive or motor disabilities rely on consistent placement of controls and landmarks.
- **Mobile-first and responsive**, but layout stability for WCAG always wins over visual flair. Buttons, links, and navigation stay in predictable locations across all views and states.
- **Inputs flow with content** — don't pin chat inputs to the viewport bottom. Follow conversation UX: the input lives at the end of the message flow.

**Patterns from the CSP migration** — promoted to the org level; see `~/flp/CLAUDE.md` Alpine section (pre-compute getters, CSS-over-Alpine animation, flat getters, no `!`/`x-model`, spread-flattens-getters).

### Component System (Django Cotton + Atomic Design)

Components live in `litigant_portal/app/templates/cotton/` using Atomic Design hierarchy:

```
litigant_portal/app/templates/cotton/
├── atoms/      # Basic elements: alert, auto_dismiss, badge, button, checkbox, eyebrow, icon, input, link, nav_link, search_input, select
├── molecules/  # Combinations: auth_status, flow_links, flow_section_* (fact_gather, ics, info, packet, resources, summary, vcf), form_errors, form_field, form_field_select, logo, search_bar, toast_container, topic_card, user_menu
└── organisms/  # Complex sections: auth_cta, auth_layout, chat_header, fallback_resources, footer, header, hero, topic_grid
```

**Syntax:** `<c-atoms.button>`, `<c-molecules.logo>`, `<c-organisms.header>`

Style guide available at `/style-guide/` during development.

Component & style discipline follows the org rule (`~/flp/CLAUDE.md`): compose from existing components first, extend with a prop when almost-right, new components/tokens only when nothing combines. LP paths: components in `litigant_portal/app/templates/cotton/`, theme tokens in `litigant_portal/app/src/main.css`. Check props (variants, sizes, `href`, `full_width`, `class` passthrough) before assuming a component can't do it.

**Atomic design check (both directions):** After any template or component change:

- **Top-down:** Are templates composing existing atoms/molecules/organisms? No hand-rolled HTML that duplicates a component.
- **Bottom-up:** Are there repeated patterns across templates that should be _extracted_ into new components? If 3+ templates share the same HTML structure (same tags, classes, layout), that's a missing molecule or organism.
- **Style guide:** Does `litigant_portal/app/templates/pages/style_guide.html` need updating? New components, new props, or changed behavior should be reflected there.

### State Flow

Django renders initial state, Alpine.js handles client-side reactivity. All components use named `Alpine.data()` registrations (CSP build requirement — no inline expressions):

```html
<div x-data="userMenu">
  <!-- Alpine handles UI state via dot-path properties, Django handles data -->
  <button x-on:click="toggle" x-bind:aria-expanded="open">Menu</button>
</div>
```

### Tailwind v4 CSS

CSS-based configuration in `litigant_portal/app/src/main.css` with `@theme { }` blocks. No `tailwind.config.js` needed.

Build: `tailwindcss -i litigant_portal/app/src/main.css -o litigant_portal/app/static/css/main.built.css` (or `make css`)

## Critical Constraints

### CSP Compliance (Content Security Policy)

No inline event handlers (org CSP mandate) — use Alpine directives (`x-on:click="doSomething"`, never `onclick=`). Enforced by the `csp-inline-check` pre-commit hook.

### Alpine.js (CSP Build - Local)

Using Alpine.js **CSP build** (`@alpinejs/csp` v3.14.9). Local files, no CDN. The CSP build replaces Alpine's expression evaluator with pure dot-path resolution — no `eval` or `new Function()`.

**Constraint:** Every directive value must be a simple property name, method name, or dot-path (e.g., `isOpen`, `toggle`, `msg.content`). No ternaries, concatenation, object literals, optional chaining, or inline assignments. Push all logic into `Alpine.data()` getters/methods.

**Files:**

- `litigant_portal/app/static/js/alpine.min.js` - Minified (production)
- `litigant_portal/app/static/js/alpine.js` - Non-minified (debug mode, auto-selected when `DEBUG=True`)
- `litigant_portal/app/static/js/components.js` - Named `Alpine.data()` components (autoDismiss, userMenu, devMenu, etc.)
- `litigant_portal/app/static/js/chat_engine.js` - Chat engine components (chatApp, chatUsage) with pre-computed properties
- `litigant_portal/app/static/js/admin.js` - LP admin dashboard component (adminApp)

**`x-html` usage:** Still used for chat messages. Safe because `renderMarkdown()` runs everything through `escapeHtml()` before applying markdown transforms, and content is pre-computed in JS (`message.html`). Tool call/result cards (`message.callHtml` / `message.resultHtml`) are rendered server-side by Django templates before shipping over SSE.

### Form Fields Pattern

**Always use `<c-molecules.form-field>` for form inputs.** This component handles:

- Label + input + error message layout
- `aria-invalid="true"` when errors present
- Help text and error message display

```html
<c-molecules.form-field
  label="Email address"
  type="email"
  name="email"
  id="id_email"
  placeholder="you@example.com"
  required
  autocomplete="email"
  value="{{ form.email.value|default:'' }}"
  help_text="We'll never share your email"
  :errors="form.email.errors"
/>
```

## AI Chat Feature

**There is one chat.** Don't say "v1" or "v2" — the prompt-backed chat is gone and the model-backed one is simply _chat_. Some older issue titles still carry "v2 chat" (#668, #715, #755–#762); that's historical naming, not a live distinction.

The portal runs on a general-purpose chat engine (threads, streaming, tool-calling loop, uploads) with all domain behavior packaged as agents. Agent authoring guide: [docs/ai-tooling/AGENT_DEV_GUIDE.md](docs/ai-tooling/AGENT_DEV_GUIDE.md) · uploads: [docs/ai-tooling/UPLOAD_SYSTEM.md](docs/ai-tooling/UPLOAD_SYSTEM.md).

### How It Works

1. **Alpine.js** (`chatApp` in `chat_engine.js`) POSTs the message to `/api/agents/assistant/stream/`
2. **Django** (`services/chat_engine.py`) runs the agent loop — LLM turns plus tool calls — and streams SSE events (`thread`, `content_delta`, `tool_call`, `tool_response`, `state`, `done`, `error`) via `StreamingHttpResponse`
3. **Alpine.js** updates the UI progressively as events arrive
4. Thread list/history/usage and uploads live under the same `/api/agents/assistant/` namespace, bound in `views/assistant.py`

No WebSockets, no Django Channels - just SSE over standard HTTP.

### LLM Provider

Using **LiteLLM**. All models are served through AWS Bedrock (credential: `AWS_BEARER_TOKEN_BEDROCK`). The assistant's model resolves from the Site's admin config (`site_get_model(role="assistant")`), falling back to `DEFAULT_BEDROCK_MODEL` (GPT-5.6 Luna) when unset. Model choices live in the `BedrockModel` enum in `app/models/choices.py`.

## Key Files

| File                                                   | Purpose                               |
| ------------------------------------------------------ | ------------------------------------- |
| `litigant_portal/settings.py`                          | Django + Cotton + CSP + Chat config   |
| `litigant_portal/app/src/main.css`                     | Tailwind v4 source + theme tokens     |
| `litigant_portal/app/static/js/alpine.js`              | Alpine.js CSP build (debug)           |
| `litigant_portal/app/static/js/alpine.min.js`          | Alpine.js CSP build (production)      |
| `litigant_portal/app/static/js/components.js`          | Named Alpine.data() components        |
| `litigant_portal/app/static/js/chat_engine.js`         | Chat engine Alpine components         |
| `litigant_portal/agents/`                              | Agent framework (base, tools, agents) |
| `litigant_portal/app/templates/cotton/`                | Component library (Atomic Design)     |
| `litigant_portal/app/templates/pages/style_guide.html` | Style guide page                      |
| `litigant_portal/app/views/`                           | Main views                            |

## Database

PostgreSQL with the **pgvector** extension. Locally it's the `pgvector/pgvector:pg17` service in `docker-compose.yml`; pgvector is included so vector similarity search is available for future semantic/RAG features.

### Reset Data (Demo Mode)

```bash
docker compose down -v && docker compose up
```

## Versioning

All frontend assets are local files, not CDN.
