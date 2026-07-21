# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Access to justice portal for self-represented litigants. Django 6.0 with server-rendered components (Django Cotton), Tailwind CSS v4, and Alpine.js for reactivity.

## Current Focus: Beta Demo — Housing Eviction Flow

Building a complete eviction flow from discovery to resolution for court partner demos. One topic, end-to-end, at production quality — every button/link does something, no placeholders. Court-neutral information where partner-specific data isn't available yet.

- [Milestone](https://github.com/freelawproject/litigant-portal/milestone/3) - Beta Demo: Housing Eviction Flow
- [Legal Flow](docs/overview-mapped-legal-flow.md) - Generic 9-stage flow (Triage / Prepare / Resolve); legal review artifact
- [Happy Path Narrative](docs/happy-path-jane.md) - Full AI · Auth end-to-end story (base for all variations)
- [Demo Flow](docs/demo-flow-jane.md) - Jane's 8-step demo flow (abbreviated)
- [User Flows Matrix](docs/user-flows.md) - 3×2 matrix (Full AI / Hybrid / Basic × Anon / Auth)
- [Retro Notes](docs/itc-demo-retro.md) - Lessons learned from ITC demo (Jan 2026)

## Environment Philosophy

`docker-compose.yml` is **local development only** — Postgres (pgvector), Redis, Django, and Caddy on one machine. Production is deployed outside this repo and consumes nothing from this file (see [Production](README.md#production)).

| Environment | Chat Provider | Config Source                        |
| ----------- | ------------- | ------------------------------------ |
| Local dev   | OpenAI        | `docker-compose.yml` + `.env`        |
| CI          | None (mocked) | `tox.ini` — tests mock all providers |

Chat model is configurable via `CHAT_MODEL` env var (LiteLLM format, e.g. `openai/gpt-4o-mini`). Setup commands live under Commands below.

## Commands

**`make lint`, `make test`, `make pre-commit`** — sandbox restrictions prevent Claude from running them. Never attempt to run them yourself. Mitch runs lint/test as part of his own workflow — a single post-commit mention is plenty; don't re-prompt about them across the commit/PR steps.

### Local Development (Docker)

```sh
cp .env.example .env        # Add your OPENAI_API_KEY
make docker                 # Start dev environment
make docker-bash           # Shell into container
make docker-down            # Stop containers
```

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

Rules for authoring user-facing content — corpus YAML (`litigant_portal/content/`), UI strings, and prompt layers that shape chat output:

- **No em-dashes.** Use a period, comma, colon, or parentheses instead. Em-dash-heavy prose reads as AI-generated and undermines user trust (legal review, #620). Dev-facing text (code comments, docs, commit messages) is exempt.
- **Corpus info bodies: one line per paragraph.** The renderer pipes `body` through Django's `linebreaks`, so every newline becomes a `<br>` — hard-wrapped prose breaks mid-sentence on the page. Separate paragraphs with blank lines; never wrap a paragraph across source lines.
- **Dash-prefixed lines** (`- item`) render as visual line-broken lists (not semantic `<ul>`) until #518 adds rich text to info bodies. Links in body prose are not supported yet (#518) — route them through the corpus `resources`/`contacts` sections instead.
- **Never label resources or forms "official."** Courts reserve "official" for institutionally designated things — ND's own site uses it only for official county newspapers, the official record of the Court, and to disclaim that Self Help Center forms "aren't official court forms" (#646). Attribute instead of anointing: say whose page or form it is ("the North Dakota Legal Self Help Center's name-change page").
- **Solve directly; escalate to legal aid sparingly.** LP's job is to answer the litigant's question and resolve their issue directly wherever it can (explain the process, the deadlines, how a step works, what to bring). Route to legal aid only when (a) we genuinely can't help — a case-specific legal _judgment_, the UPL boundary ("will this defense win for me") — or (b) the issue is serious enough to require it (illegal lockout, imminent set-out, safety). Don't tell users to "get a lawyer" or "call an attorney": whether legal aid then brings in an attorney is _their_ call, not ours. Our audience is self-represented on a phone precisely because an attorney isn't within reach, so a reflexive "see a lawyer" tells them the tool can't help them (#611).

## Issue creation

See [`docs/issue-conventions.md`](docs/issue-conventions.md) for the full label color scheme and template rationale.

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

When someone references a sprint by its web-team letter/artist name ("the Ed Sheeran sprint", "Sprint F"), translate to the matching LP Iteration on board #75 via [`docs/sprint-map.md`](docs/sprint-map.md), then pull the work from #75 + git. This crosswalk is LP-specific — other JI repos don't necessarily align with the web-team retro, so it lives here, not in org-level instructions.

## Sizing & estimation

How we size issues so velocity maps to reality (the org-level scale + board mechanics live in `~/flp/CLAUDE.md`; these are the LP-specific practice and calibration record):

- [`docs/sizing-guide.md`](docs/sizing-guide.md) — contributor/onboarding: get your estimate in the zone (size the work not the diff, incident work = size the diagnosis, XL = split). Reference anchors from real LP issues.
- [`docs/sizing-calibration.md`](docs/sizing-calibration.md) — living team record: the estimate → verify-L1 → verify-L2 model, how to run a calibration pass, and a dated log of lessons (first entry: the It2–It4 velocity baseline + It3 reconstruction).

## Architecture

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
├── atoms/      # Basic elements: alert, auto_dismiss, badge, button, checkbox, icon, input, link, nav_link, search_input, select
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

The portal runs on a general-purpose chat engine (threads, streaming, tool-calling loop, uploads) with all domain behavior packaged as agents. Agent authoring guide: [docs/AGENT_DEV_GUIDE.md](docs/AGENT_DEV_GUIDE.md) · uploads: [docs/ATTACHMENT_SYSTEM.md](docs/ATTACHMENT_SYSTEM.md).

### How It Works

1. **Alpine.js** (`chatApp` in `chat_engine.js`) POSTs the message to `/api/agents/assistant/stream/`
2. **Django** (`services/chat_engine.py`) runs the agent loop — LLM turns plus tool calls — and streams SSE events (`thread`, `content_delta`, `tool_call`, `tool_response`, `state`, `done`, `error`) via `StreamingHttpResponse`
3. **Alpine.js** updates the UI progressively as events arrive
4. Thread list/history/usage and uploads live under the same `/api/agents/assistant/` namespace, bound in `views/assistant.py`

No WebSockets, no Django Channels - just SSE over standard HTTP.

### LLM Provider

Using **LiteLLM**. The assistant's model resolves from the active Site's admin config (`site_get_model(role="assistant")`), falling back to the `CHAT_MODEL` env var (local dev default: `openai/gpt-4o-mini`, set in docker-compose.yml). To switch providers, change the model string (LiteLLM format).

## Key Files

| File                                                   | Purpose                              |
| ------------------------------------------------------ | ------------------------------------ |
| `litigant_portal/settings.py`                          | Django + Cotton + CSP + Chat config  |
| `litigant_portal/app/src/main.css`                     | Tailwind v4 source + theme tokens    |
| `litigant_portal/app/static/js/alpine.js`              | Alpine.js CSP build (debug)          |
| `litigant_portal/app/static/js/alpine.min.js`          | Alpine.js CSP build (production)     |
| `litigant_portal/app/static/js/components.js`          | Named Alpine.data() components       |
| `litigant_portal/app/static/js/chat_engine.js`         | Chat engine Alpine components        |
| `litigant_portal/agents/`                              | Agent framework (base, tools, agents)|
| `litigant_portal/app/templates/cotton/`                | Component library (Atomic Design)    |
| `litigant_portal/app/templates/pages/style_guide.html` | Style guide page                     |
| `litigant_portal/app/views/`                           | Main views                           |

## Database

PostgreSQL with the **pgvector** extension. Locally it's the `pgvector/pgvector:pg17` service in `docker-compose.yml`; pgvector is included so vector similarity search is available for future semantic/RAG features.

### Reset Data (Demo Mode)

```bash
docker compose down -v && docker compose up
```

## Versioning

All frontend assets are local files, not CDN. Pinned versions and update commands: [docs/pinned-assets.md](docs/pinned-assets.md).
