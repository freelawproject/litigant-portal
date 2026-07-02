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

`docker-compose.yml` is **local development only** — Postgres (pgvector), Redis, Django, and Caddy on one machine. Production is deployed outside this repo and consumes nothing from this file (see [Production](#production)).

| Environment | Chat Provider | Config Source                        |
| ----------- | ------------- | ------------------------------------ |
| Local dev   | OpenAI        | `docker-compose.yml` + `.env`        |
| CI          | None (mocked) | `tox.ini` — tests mock all providers |

**Local dev setup:**

```bash
cp .env.example .env        # Add your OPENAI_API_KEY
make docker                 # Start dev environment
```

Chat model is configurable via `CHAT_MODEL` env var (LiteLLM format, e.g. `openai/gpt-4o-mini`).

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
make test fast              # Pass extra tox args through make
make -- test -e fast -- -k "ReadSecretTests"
make lint                   # Lint and format all code (via pre-commit)
```

`make test ...` forwards extra positional args to `tox` inside the container. Args that start with `-` are parsed by `make` itself, so use `make -- test ...` when passing tox or pytest flags.

## Pre-commit Hooks

Pre-commit runs automatically on commit. Key hooks:

- **ruff** - Python linting/formatting
- **djlint** - HTML template linting (errors only, no auto-formatting)
- **prettier** - JS, JSON, CSS, Markdown, YAML formatting
- **csp-inline-check** - Blocks inline event handlers (CSP compliance)

Run all hooks manually: `pre-commit run --all-files`

**Note:** djlint runs in **lint-only mode** (no auto-formatter). Its formatter was mangling template tags inside HTML attributes — expanding single-line `{% block %}` tags to multi-line and injecting whitespace into rendered attributes. See "Template Formatting" below for the manual conventions that replace the formatter.

### Before Committing

Mitch runs this before commits (especially after rebases or batch edits) — it's his routine, not a step Claude needs to prompt:

```bash
make pre-commit   # lint → test, short-circuits if lint fails/fixes anything
```

Equivalent to `make lint && make test`. If lint auto-fixes files, the target stops before tests — re-stage the changes and re-run. The name mirrors the `pre-commit` hook tool intentionally — same concept, different invocation surface.

### Template Formatting (Manual Conventions)

No auto-formatter for `.html` templates — djlint runs lint-only. Follow these Prettier-inspired conventions (Prettier is the source of truth — a Cotton plugin is planned). Cotton components (`<c-atoms.button>`, `<c-organisms.header>`) are valid HTML5 custom elements and follow the same rules as any HTML tag.

**1. Indentation: 2 spaces.** For HTML elements, Cotton components, and template tags alike.

**2. Attribute wrapping: single vs multi-line.**

If all attributes fit on one line within ~120 chars, keep them inline:

```html
<div class="flex items-center gap-2">
  <c-atoms.icon name="check" class="w-4 h-4" />
  <c-atoms.button
    type="button"
    variant="primary"
    x-on:click="save"
  ></c-atoms.button>
</div>
```

If they don't fit, one attribute per line. Closing `>` or `/>` goes on its own line (Prettier default, `bracketSameLine: false`):

```html
<input
  type="text"
  x-bind:value="inputText"
  x-on:input="updateInput"
  name="q"
  placeholder="{% trans 'Ask a question' %}"
  class="chat-input"
  aria-label="{% trans 'Ask a question' %}"
/>
```

For Cotton components, same rule — first attribute on the tag line, rest aligned:

```html
<c-molecules.form-field
  label="Email"
  type="email"
  name="email"
  required
  value="{{ form.email.value|default:'' }}"
/>
```

**3. Template tags inside HTML attributes MUST stay on one line.**

This is the critical rule. Django template tags (`{% block %}`, `{% if %}`, `{{ var }}`) inside an attribute value must remain on the same line as the attribute. Multi-line = literal whitespace in the rendered HTML.

```html
<!-- GOOD -->
<body
  class="{% block body_class %}min-h-dvh flex flex-col bg-greyscale-25{% endblock body_class %}"
>
  <main class="flex-1 {% block main_class %}{% endblock main_class %}">
    <meta
      name="description"
      content="{% block meta_description %}{% trans 'Default' %}{% endblock meta_description %}"
    />

    <!-- BAD: whitespace injected into rendered class attribute -->
    <body
      class="{% block body_class %}
    min-h-dvh flex flex-col bg-greyscale-25{% endblock body_class %}
    "
    ></body>
  </main>
</body>
```

These lines will be long. That's OK — attribute values are not breakable.

**4. Block-level template tags get their own lines.**

Outside of attributes, `{% block %}`, `{% if %}`, `{% for %}` etc. get their own lines and indent their children:

```html
{% block content %}
<div class="container">
  <h1>Title</h1>
</div>
{% endblock content %} {% if user.is_authenticated %}
<p>Welcome</p>
{% else %}
<p>Please sign in</p>
{% endif %}
```

**5. Self-closing tags.**

Prettier adds `/>` to void HTML elements and self-closing components alike. Follow Prettier:

```html
<!-- Void HTML elements -->
<meta charset="UTF-8" />
<input type="text" name="q" />
<img src="logo.svg" alt="Logo" class="h-12" />

<!-- Cotton self-closing -->
<c-atoms.icon name="check" class="w-4 h-4" />
<c-atoms.typing-indicator />
<c-organisms.header />
```

**6. Quotes: double quotes** for all HTML attributes. Single quotes only inside attribute values for Django template tags: `value="{{ form.email.value|default:'' }}"`.

**`{% trans %}` in Cotton props:** Never put `{% trans %}` directly in a prop attribute — the single quotes needed to avoid closing the HTML attribute violate djlint T002. Extract to a variable first:

```html
{% trans "Check your email" as status_heading %}
<c-molecules.auth-status
  heading="{{ status_heading }}"
></c-molecules.auth-status>
```

**7. Blank lines.** One blank line between logical sections. Never multiple consecutive blank lines. No blank line immediately after an opening tag or before a closing tag:

```html
<!-- GOOD -->
<div class="container">
  <h1>Title</h1>
  <p>Content</p>
</div>

<!-- BAD: blank line after opening tag -->
<div class="container">
  <h1>Title</h1>
</div>
```

**8. Short inline elements stay on one line** when they fit:

```html
<p class="text-sm text-greyscale-500">{% trans "No activity yet" %}</p>
<span class="font-semibold">{% trans "Activity" %}</span>
```

**9. Long `class` values.** Tailwind classes stay on one line inside the `class` attribute even when long — don't break a class string across lines. If the element also has many other attributes, the `class` attribute gets its own line in the multi-line format (rule 2), but the value itself stays unbroken.

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

**Patterns from the CSP migration:**

- **Pre-compute in JS, bind in templates** — ternaries (`role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'`) become getter properties (`msg.bubbleClass`). Templates only reference the result.
- **CSS over Alpine for animation** — `@keyframes` + `x-on:animationend` replaces `x-transition` + `setTimeout`. Native `<details>` + `grid-rows-[0fr]/[1fr]` replaces `x-collapse`.
- **Flat getters for nested data** — optional chaining (`caseInfo?.court_info?.phone`) can't appear in templates. Create flat getters (`get courtPhone()`) that encapsulate the traversal.
- **`x-effect` → method calls** — side effects on state change (like loading data when a menu opens) go in the method that triggers the change (`openMenu()` loads timeline), not in `x-effect`.
- **No `!` negation in templates** — `x-show="!isOpen"` fails in CSP build. Create negated getters (`get isClosed()`) instead.
- **No `x-model`** — CSP build can't evaluate the setter (`expr = __placeholder`). Use `x-bind:value="prop"` + `x-on:input="updateMethod"` instead, where the method reads `e.target.value`.
- **Spread flattens getters** — `{ ...createChat() }` invokes getters and copies static values. If a composed component needs reactive getters from a base, re-define them after the spread.

### Component System (Django Cotton + Atomic Design)

Components live in `litigant_portal/app/templates/cotton/` using Atomic Design hierarchy:

```
litigant_portal/app/templates/cotton/
├── atoms/      # Basic elements: alert, auto_dismiss, button, chat_bubble, checkbox, icon, input, link, nav_link, search_input, select, typing_indicator
├── molecules/  # Combinations: action_item, deadline_card, form_errors, form_field, form_field_select, logo, search_bar, search_result, sidebar_section, toast_container, topic_card, user_menu
└── organisms/  # Complex sections: footer, header, hero, topic_grid
```

**Syntax:** `<c-atoms.button>`, `<c-molecules.logo>`, `<c-organisms.header>`

Style guide available at `/style-guide/` during development.

**NEVER** create custom CSS classes or raw HTML that duplicates what an existing atom/molecule already does. **ALWAYS** check existing components before writing any UI element:

1. Check `litigant_portal/app/templates/cotton/` for an existing component at the right atomic level
2. Check component props — variants, sizes, `href`, `full_width`, `class` passthrough — before assuming a component can't do what you need
3. If a component is _almost_ right, **extend it** with a new prop rather than bypassing it with custom CSS
4. Check Tailwind theme tokens in `litigant_portal/app/src/main.css` before inventing new values

Only create a new component when no combination of existing ones works. Only add new theme tokens when the design system genuinely needs them.

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

**No inline event handlers.** Use Alpine.js directives instead:

```html
<!-- BAD: Violates CSP -->
<button onclick="doSomething()">
  <!-- GOOD: CSP-compliant -->
  <button x-on:click="doSomething"></button>
</button>
```

Pre-commit hook enforces this (`csp-inline-check`).

### Alpine.js (CSP Build - Local)

Using Alpine.js **CSP build** (`@alpinejs/csp` v3.14.9). Local files, no CDN. The CSP build replaces Alpine's expression evaluator with pure dot-path resolution — no `eval` or `new Function()`.

**Constraint:** Every directive value must be a simple property name, method name, or dot-path (e.g., `isOpen`, `toggle`, `msg.content`). No ternaries, concatenation, object literals, optional chaining, or inline assignments. Push all logic into `Alpine.data()` getters/methods.

**Files:**

- `litigant_portal/app/static/js/alpine.min.js` - Minified (production)
- `litigant_portal/app/static/js/alpine.js` - Non-minified (debug mode, auto-selected when `DEBUG=True`)
- `litigant_portal/app/static/js/components.js` - Named `Alpine.data()` components (userMenu, activityTimeline, etc.)
- `litigant_portal/app/static/js/chat.js` - Chat and home page components with pre-computed properties

**`x-html` usage:** Still used for chat messages. Safe because `renderMarkdown()` escapes HTML before applying markdown transforms, and content is pre-computed in JS (`msg.renderedContent`).

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

The portal includes an AI-powered chat for legal assistance with streaming responses.

### How It Works

1. **Alpine.js** intercepts form submit, POSTs to `/chat/send/`
2. **Django** creates session/message, returns `session_id`
3. **Alpine.js** GETs `/chat/stream/<session_id>/` (SSE endpoint)
4. **Django** streams tokens via `StreamingHttpResponse`
5. **Alpine.js** updates UI progressively as tokens arrive

No WebSockets, no Django Channels - just SSE over standard HTTP.

### LLM Provider

Using **LiteLLM** with OpenAI for dev and QA. Model configured via `CHAT_MODEL` env var (default: `openai/gpt-4o-mini`). To switch providers, change the env var (e.g. `groq/llama-3.3-70b-versatile`).

## Key Files

| File                                                   | Purpose                              |
| ------------------------------------------------------ | ------------------------------------ |
| `litigant_portal/settings.py`                          | Django + Cotton + CSP + Chat config  |
| `litigant_portal/app/src/main.css`                     | Tailwind v4 source + theme tokens    |
| `litigant_portal/app/static/js/alpine.js`              | Alpine.js CSP build (debug)          |
| `litigant_portal/app/static/js/alpine.min.js`          | Alpine.js CSP build (production)     |
| `litigant_portal/app/static/js/components.js`          | Named Alpine.data() components       |
| `litigant_portal/app/static/js/chat.js`                | Chat and home page Alpine components |
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

### Pinned Dependencies (Local Assets)

All frontend assets are local files, not CDN. Update these in sync when upgrading:

| Tool         | Version            | Location                                                                                 |
| ------------ | ------------------ | ---------------------------------------------------------------------------------------- |
| Tailwind CSS | v4.1.16 (CLI)      | `Dockerfile`                                                                             |
| Alpine.js    | 3.14.9 (CSP build) | `litigant_portal/app/static/js/alpine.js`, `litigant_portal/app/static/js/alpine.min.js` |
| Chat model   | openai/gpt-4o-mini | `CHAT_MODEL` env var (docker-compose.yml, .env)                                          |

**Updating Alpine.js (CSP build):**

```bash
curl -sL "https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.14.9/dist/cdn.js" -o litigant_portal/app/static/js/alpine.js
curl -sL "https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.14.9/dist/cdn.min.js" -o litigant_portal/app/static/js/alpine.min.js
```
