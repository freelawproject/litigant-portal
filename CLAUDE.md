# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Access to justice portal for self-represented litigants. Django 5.2 with server-rendered components (Django Cotton), Tailwind CSS v4, and Alpine.js for reactivity.

## Current Focus: ITC Demo (Jan 2026)

Building a clickable demo for ITC San Antonio. Key docs:

- [Demo Flow](docs/demo-flow-jane.md) - Jane's 8-step user journey
- [Retro Notes](docs/itc-demo-retro.md) - Append lessons learned here
- [Milestone](https://github.com/freelawproject/litigant-portal/milestone/1) - 13 issues tracked

## Environment Philosophy

Keep configuration **simple and consistent** across dev, CI/CD, and QA. Docker everywhere.

| Environment | Chat Provider | Config Source                              |
| ----------- | ------------- | ------------------------------------------ |
| Local dev   | OpenAI        | docker-compose.yml + `.env` (secrets only) |
| CI/CD       | None (mocked) | tox.ini - tests mock all providers         |
| QA (Fly.io) | OpenAI        | fly.toml + `fly secrets`                   |

**Local dev setup:**

```bash
cp .env.example .env        # Add your OPENAI_API_KEY
make docker-dev             # Start dev environment
```

Chat model is configurable via `CHAT_MODEL` env var (LiteLLM format, e.g. `openai/gpt-4o-mini`).

## Commands

**Always use `make` commands** for linting and testing. Don't run `ruff`, `djlint`, `pytest`, or `pre-commit` directly — use `make lint` and `make test`. These ensure correct environment setup and consistent behavior.

**Note:** `make lint` and `make test` often hit sandbox restrictions. Ask the user to run them manually rather than attempting and failing.

### Local Development (Docker)

```sh
cp .env.example .env        # Add your OPENAI_API_KEY
make docker-dev             # Start dev environment
make docker-shell           # Shell into container
make docker-down            # Stop containers
```

### Testing & Linting

```sh
make test                   # Run tests (builds CSS + collectstatic first)
make lint                   # Lint and format all code (via pre-commit)
```

### Direct Python commands (use .venv/bin/python)

For Django management commands outside Docker:

```sh
SECRET_KEY=dev .venv/bin/python manage.py check
SECRET_KEY=dev .venv/bin/python manage.py makemigrations
SECRET_KEY=dev .venv/bin/python manage.py migrate
SECRET_KEY=dev .venv/bin/python manage.py shell

# Run tests directly (faster than make test, skips CSS build)
SECRET_KEY=test .venv/bin/python manage.py test
SECRET_KEY=test .venv/bin/python manage.py test portal.tests.ProfileViewTests
```

## Pre-commit Hooks

Pre-commit runs automatically on commit. Key hooks:

- **ruff** - Python linting/formatting
- **djlint** - HTML template linting/formatting
- **prettier** - JS, JSON, CSS, Markdown, YAML formatting
- **csp-inline-check** - Blocks inline event handlers (CSP compliance)

Run all hooks manually: `pre-commit run --all-files`

### Before Committing

Always run before commits (especially after rebases or batch edits):

```bash
make lint    # Format + lint all code
make test    # Run test suite
```

## Architecture

### Front-End Principles

When choosing how to implement UI behavior, follow this priority order:

1. **Django/Cotton + HTML/Tailwind first** — solve it server-side or with semantic HTML + CSS before reaching for JS. Cotton components, Django template logic, Tailwind utilities, native elements (`<details>`, `<dialog>`, CSS animations) cover most needs.
2. **Alpine.js is reactivity only** — show/hide, toggle, event binding, dynamic attribute binding. Alpine should not contain rendering logic, layout decisions, or anything that HTML/CSS can handle.
3. **Named components, dot-paths only** — CSP build requires `Alpine.data()` registrations. No inline expressions in templates. Pre-compute values as getters/methods.
4. **`data-*` attributes for config** — pass Django values to Alpine via `data-*` attributes, read them in `init()`. Never use `x-init` assignments or pass `$event` to handlers (Alpine auto-passes it).
5. **Reference repos** — [CourtListener](https://github.com/freelawproject/courtlistener) and [free.law](https://github.com/freelawproject/free.law) have solved most Django + Alpine + CSP patterns at scale. When hitting a seemingly blocking JS/Alpine problem, check those repos for working patterns before inventing a new approach.

**Patterns from the CSP migration:**

- **Pre-compute in JS, bind in templates** — ternaries (`role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'`) become getter properties (`msg.bubbleClass`). Templates only reference the result.
- **CSS over Alpine for animation** — `@keyframes` + `x-on:animationend` replaces `x-transition` + `setTimeout`. Native `<details>` + `grid-rows-[0fr]/[1fr]` replaces `x-collapse`.
- **Flat getters for nested data** — optional chaining (`caseInfo?.court_info?.phone`) can't appear in templates. Create flat getters (`get courtPhone()`) that encapsulate the traversal.
- **`x-effect` → method calls** — side effects on state change (like loading data when a menu opens) go in the method that triggers the change (`openMenu()` loads timeline), not in `x-effect`.
- **No `!` negation in templates** — `x-show="!isOpen"` fails in CSP build. Create negated getters (`get isClosed()`) instead.
- **No `x-model`** — CSP build can't evaluate the setter (`expr = __placeholder`). Use `x-bind:value="prop"` + `x-on:input="updateMethod"` instead, where the method reads `e.target.value`.
- **Spread flattens getters** — `{ ...createChat() }` invokes getters and copies static values. If a composed component needs reactive getters from a base, re-define them after the spread.

### Component System (Django Cotton + Atomic Design)

Components live in `templates/cotton/` using Atomic Design hierarchy:

```
templates/cotton/
├── atoms/      # Basic elements: alert, auto_dismiss, button, chat_bubble, checkbox, icon, input, link, nav_link, search_input, select, typing_indicator
├── molecules/  # Combinations: chat_message, form_field, form_field_select, logo, search_bar, search_result, toast_container, topic_card, user_menu
└── organisms/  # Complex sections: chat_window, footer, header, hero, topic_grid
```

**Syntax:** `<c-atoms.button>`, `<c-molecules.logo>`, `<c-organisms.header>`

Style guide available at `/style-guide/` during development.

### State Flow

Django renders initial state, Alpine.js handles client-side reactivity. All components use named `Alpine.data()` registrations (CSP build requirement — no inline expressions):

```html
<div x-data="userMenu">
  <!-- Alpine handles UI state via dot-path properties, Django handles data -->
  <button x-on:click="toggle" x-bind:aria-expanded="open">Menu</button>
</div>
```

### Tailwind v4 CSS

CSS-based configuration in `src/css/main.css` with `@theme { }` blocks. No `tailwind.config.js` needed.

Build: `tailwindcss -i src/css/main.css -o static/css/main.built.css`

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

- `static/js/alpine.min.js` - Minified (production)
- `static/js/alpine.js` - Non-minified (debug mode, auto-selected when `DEBUG=True`)
- `static/js/components.js` - Named `Alpine.data()` components (userMenu, activityTimeline, etc.)
- `static/js/chat.js` - Chat and home page components with pre-computed properties

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

### Chat Architecture

```
chat/
├── providers/
│   ├── base.py      # Abstract BaseLLMProvider class
│   ├── ollama.py    # Ollama local LLM (OpenAI-compatible API)
│   └── factory.py   # Provider factory with caching
├── services/
│   ├── chat_service.py   # Main chat orchestration + SSE streaming
│   └── search_service.py # Keyword search fallback (icontains)
├── models.py        # ChatSession, Message, Document
└── views.py         # API endpoints (send, stream, search)
```

### LLM Provider

Using **LiteLLM** with OpenAI for dev and QA. Model configured via `CHAT_MODEL` env var (default: `openai/gpt-4o-mini`). To switch providers, change the env var (e.g. `groq/llama-3.3-70b-versatile`).

### Chat Endpoints

- `POST /chat/send/` - Submit user message, returns session_id
- `GET /chat/stream/<session_id>/` - SSE streaming AI response
- `GET /chat/search/` - Keyword search fallback

## Key Files

| File                               | Purpose                                 |
| ---------------------------------- | --------------------------------------- |
| `config/settings.py`               | Django + Cotton + CSP + Chat config     |
| `src/css/main.css`                 | Tailwind v4 source + theme tokens       |
| `static/js/alpine.js`              | Alpine.js CSP build (debug)             |
| `static/js/alpine.min.js`          | Alpine.js CSP build (production)        |
| `static/js/components.js`          | Named Alpine.data() components          |
| `static/js/chat.js`                | Chat and home page Alpine components    |
| `templates/cotton/`                | Component library (Atomic Design)       |
| `templates/pages/style_guide.html` | Style guide page                        |
| `chat/`                            | AI chat app with providers and services |
| `portal/views.py`                  | Main views                              |

## Database

SQLite everywhere (local dev, Docker, Fly.io).

- **Local dev:** `db.sqlite3` in project root
- **Docker prod / Fly.io:** `sqlite:////data/db.sqlite3` on a volume
- **Concurrency:** WAL mode + `transaction_mode = "IMMEDIATE"` (Django 5.2) prevents "database is locked" under Gunicorn

### Reset Data (Demo Mode)

```bash
rm db.sqlite3
SECRET_KEY=dev .venv/bin/python manage.py migrate
```

## Versioning

### Pinned Dependencies (Local Assets)

All frontend assets are local files, not CDN. Update these in sync when upgrading:

| Tool         | Version            | Location                                         |
| ------------ | ------------------ | ------------------------------------------------ |
| Tailwind CSS | v4.1.16 (CLI)      | `Dockerfile`                                     |
| Alpine.js    | 3.14.9 (CSP build) | `static/js/alpine.js`, `static/js/alpine.min.js` |
| Chat model   | openai/gpt-4o-mini | `CHAT_MODEL` env var (docker-compose, fly.toml)  |

**Updating Alpine.js (CSP build):**

```bash
curl -sL "https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.14.9/dist/cdn.js" -o static/js/alpine.js
curl -sL "https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.14.9/dist/cdn.min.js" -o static/js/alpine.min.js
```

## Deployment (Fly.io)

QA/staging environment deployed on Fly.io. Configuration in `fly.toml`.

### Auto-Deploy

Pushes to `main` auto-deploy via GitHub Actions (`.github/workflows/fly-deploy.yml`).

### Manual Deploy (PR Testing)

To test a branch on QA before merging:

```bash
git checkout your-branch
fly deploy              # Deploys your local working directory
```

Note: This deploys local files, not the GitHub branch. After merge, `main` auto-deploys.

### Other Commands

```bash
fly logs                # View logs
fly status              # Check app status
fly ssh console         # SSH into container
```

### Environment Variables

Set via `fly secrets set KEY=value`:

| Variable         | Description                |
| ---------------- | -------------------------- |
| `SECRET_KEY`     | Django secret key          |
| `OPENAI_API_KEY` | OpenAI API key for AI chat |

Non-secret env vars (`DATABASE_URL`, `CHAT_MODEL`, etc.) configured in `fly.toml` under `[env]`.

### Database

SQLite on a Fly Volume (`/data/db.sqlite3`). WAL mode enabled at startup.
