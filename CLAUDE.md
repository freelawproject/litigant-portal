# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Access to justice portal for self-represented litigants. Django 5.2 with server-rendered components (Django Cotton), Tailwind CSS v4, and Alpine.js for reactivity.

## Environment Philosophy

Keep configuration **simple and consistent** across dev, CI/CD, and QA. Docker everywhere.

| Environment | Chat Provider | Config Source |
|-------------|---------------|---------------|
| Local dev | Groq | docker-compose.yml + `.env` (secrets only) |
| CI/CD | None (mocked) | tox.ini - tests mock all providers |
| QA (Fly.io) | Groq | fly.toml + `fly secrets` |

**Local dev setup:**
```bash
cp .env.example .env        # Add your GROQ_API_KEY
make docker-dev             # Start dev environment
```

Future: LiteLLM will replace direct provider calls.

## Commands

### Local Development (Docker)

```sh
cp .env.example .env        # Add your GROQ_API_KEY
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

For commands outside Docker:

```sh
# Django management commands
SECRET_KEY=dev .venv/bin/python manage.py check
SECRET_KEY=dev .venv/bin/python manage.py makemigrations
SECRET_KEY=dev .venv/bin/python manage.py migrate
SECRET_KEY=dev .venv/bin/python manage.py shell

# Run tests directly (faster than make test, skips CSS build)
SECRET_KEY=test .venv/bin/python manage.py test
SECRET_KEY=test .venv/bin/python manage.py test chat.tests.test_views

# Individual linting tools
.venv/bin/ruff format .
.venv/bin/ruff check --fix
.venv/bin/djlint templates/ --reformat
```

## Pre-commit Hooks

Pre-commit runs automatically on commit. Key hooks:

- **ruff** - Python linting/formatting
- **djlint** - HTML template linting/formatting
- **prettier** - JS, JSON, CSS, Markdown, YAML formatting
- **csp-inline-check** - Blocks inline event handlers (CSP compliance)

Run all hooks manually: `pre-commit run --all-files`

## Architecture

### Component System (Django Cotton + Atomic Design)

Components live in `templates/cotton/` using Atomic Design hierarchy:

```
templates/cotton/
├── atoms/      # Basic elements: alert, button, chat_bubble, icon, input, link, nav_link, search_input, select, typing_indicator
├── molecules/  # Combinations: chat_message, logo, search_bar, search_result, topic_card
└── organisms/  # Complex sections: chat_window, footer, header, hero, topic_grid
```

**Syntax:** `<c-atoms.button>`, `<c-molecules.logo>`, `<c-organisms.header>`

Style guide available at `/style-guide/` during development.

### State Flow

Django renders initial state, Alpine.js handles client-side reactivity:

```html
<div x-data="{ expanded: false }">
  <!-- Alpine handles UI state, Django handles data -->
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

### Alpine.js (Standard Build - Local)

Using Alpine.js standard build (`static/js/alpine.min.js` v3.14.9). Local files, no CDN.

**Files:**

- `static/js/alpine.min.js` - Minified (production)
- `static/js/alpine.js` - Non-minified (debug mode, auto-selected when `DEBUG=True`)

**All directives available:**

- `x-html` - HTML content rendering (used for markdown in demo)
- `x-text` - Plain text content
- `x-data`, `x-init`, `x-bind`, `x-on`, `x-show`, `x-if`, `x-for`, `x-model`, `x-ref`

**TODO: Switch to CSP build for production:**

1. Implement server-side markdown rendering
2. Download CSP build: `curl -sL "https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.14.9/dist/cdn.min.js" -o static/js/alpine.min.js`
3. Replace `x-html` with `x-text`

### WCAG AA Accessibility

All components must have:

- Keyboard navigation (Tab, Enter, Space, Arrows)
- Focus indicators (`focus:ring-2 focus:ring-offset-2`)
- Color contrast 4.5:1 minimum
- Touch targets 44x44px minimum
- ARIA labels for icon-only buttons

### Mobile-First

Default styles target mobile. Use breakpoints for larger screens:

- `sm:` 640px, `md:` 768px, `lg:` 1024px

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

### Running Ollama

```bash
# Install and start Ollama
brew install ollama
ollama pull llama3.2:3b
ollama serve  # Runs on localhost:11434
```

Docker connects to host Ollama via `host.docker.internal:11434`.

### Chat Endpoints

- `POST /chat/send/` - Submit user message, returns session_id
- `GET /chat/stream/<session_id>/` - SSE streaming AI response
- `GET /chat/search/` - Keyword search fallback

## Key Files

| File                               | Purpose                                 |
| ---------------------------------- | --------------------------------------- |
| `config/settings.py`               | Django + Cotton + CSP + Chat config     |
| `src/css/main.css`                 | Tailwind v4 source + theme tokens       |
| `static/js/alpine.js`              | Alpine.js standard build (debug)        |
| `static/js/alpine.min.js`          | Alpine.js standard build (production)   |
| `static/js/chat.js`                | Alpine.js chat component                |
| `templates/cotton/`                | Component library (Atomic Design)       |
| `templates/pages/style_guide.html` | Style guide page                        |
| `chat/`                            | AI chat app with providers and services |
| `portal/views.py`                  | Main views                              |

## Database

- **Local dev / Demo:** SQLite (`db.sqlite3`)
- **Docker / Production:** PostgreSQL via `DATABASE_URL`

### Reset Data (Demo Mode)

```bash
rm db.sqlite3
SECRET_KEY=dev .venv/bin/python manage.py migrate
```

### Database Compatibility

The codebase supports both SQLite and PostgreSQL:

- Models avoid PostgreSQL-specific features for compatibility
- Search service uses simple `icontains` queries (works everywhere)
- PostgreSQL full-text search can be added later for production

## Versioning

### Pinned Dependencies (Local Assets)

All frontend assets are local files, not CDN. Update these in sync when upgrading:

| Tool         | Version           | Location                                         |
| ------------ | ----------------- | ------------------------------------------------ |
| Tailwind CSS | v4.1.16 (CLI)     | `Dockerfile`                                     |
| Alpine.js    | 3.14.9 (standard) | `static/js/alpine.js`, `static/js/alpine.min.js` |
| Groq model   | llama-3.3-70b-versatile | `docker-compose.yml`, `fly.toml`           |

**Updating Alpine.js:**

```bash
curl -sL "https://cdn.jsdelivr.net/npm/alpinejs@3.14.9/dist/cdn.js" -o static/js/alpine.js
curl -sL "https://cdn.jsdelivr.net/npm/alpinejs@3.14.9/dist/cdn.min.js" -o static/js/alpine.min.js
```

## Deployment (Fly.io)

QA/staging environment deployed on Fly.io. Configuration in `fly.toml`.

### Deploy Commands

```bash
fly deploy              # Deploy latest changes
fly logs                # View logs
fly status              # Check app status
fly ssh console         # SSH into container
```

### Environment Variables

Set via `fly secrets set KEY=value`:

| Variable       | Description                       |
| -------------- | --------------------------------- |
| `SECRET_KEY`   | Django secret key                 |
| `GROQ_API_KEY` | Groq API key for AI chat          |
| `DATABASE_URL` | Auto-set by `fly postgres attach` |

Non-secret env vars configured in `fly.toml` under `[env]`.

### Database

PostgreSQL via Fly Postgres (development tier).

```bash
fly postgres connect -a litigant-portal-qa-db  # Connect to database
```
