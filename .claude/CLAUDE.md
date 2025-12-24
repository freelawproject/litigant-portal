# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Access to justice portal for self-represented litigants. Django 5.2 with server-rendered components (Django Cotton), Tailwind CSS v4, and Alpine.js for reactivity.

## Commands

```sh
./dev.sh                    # Start Django + Tailwind watch (main dev command)
make test                   # Run tests (builds CSS + collectstatic first)
make format                 # Format Python (ruff) + HTML templates (djlint)
make lint                   # Lint Python (ruff) + HTML templates (djlint)

# Django commands (outside of ./dev.sh, prefix with SECRET_KEY=dev)
SECRET_KEY=dev python manage.py makemigrations
SECRET_KEY=dev python manage.py migrate
SECRET_KEY=dev python manage.py shell

# Individual tools
ruff format .               # Format Python
ruff check --fix            # Lint Python with auto-fix
djlint templates/ --reformat  # Format HTML templates
djlint templates/ --lint    # Lint HTML templates

# Docker
make docker-dev             # Start dev environment with PostgreSQL
make docker-prod            # Start production environment
```

## Architecture

### Component System (Django Cotton + Atomic Design)

Components live in `templates/cotton/` using Atomic Design hierarchy:

```
templates/cotton/
├── atoms/      # Basic elements: button, input, link, select, icon
├── molecules/  # Combinations: logo, search_bar, topic_card
└── organisms/  # Complex sections: header, footer, hero, topic_grid
```

**Syntax:** `<c-atoms.button>`, `<c-molecules.logo>`, `<c-organisms.header>`

Component library available at `/components/` during development.

### State Flow

Django renders initial state, Alpine.js handles client-side reactivity:
```html
<div x-data="{ expanded: false }">
  <!-- Alpine handles UI state, Django handles data -->
</div>
```

### Tailwind v4 CSS

CSS-based configuration in `static/css/main.css` with `@theme { }` blocks. No `tailwind.config.js` needed.

Build: `tailwindcss -i static/css/main.css -o static/css/main.built.css`

## Critical Constraints

### CSP Compliance (Content Security Policy)

**No inline event handlers.** Use Alpine.js directives instead:
```html
<!-- BAD: Violates CSP -->
<button onclick="doSomething()">

<!-- GOOD: CSP-compliant -->
<button x-on:click="doSomething">
```

Pre-commit hook enforces this (`csp-inline-check`).

### Alpine.js (Standard Build)

Currently using standard Alpine.js (`static/js/alpine.min.js` v3.14.9) for markdown rendering support via `x-html`.

**All directives available:**
- `x-html` - HTML content rendering (used for markdown)
- `x-text` - Plain text content
- `x-data`, `x-init`, `x-bind`, `x-on`, `x-show`, `x-if`, `x-for`, `x-model`, `x-ref`

### Future: Re-enable CSP Build for Production

For production hardening, switch back to CSP build:

1. Download CSP build:
   ```bash
   curl -sL "https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.14.9/dist/cdn.min.js" -o static/js/alpine.min.js
   ```

2. Replace `x-html` with `x-text` + `whitespace-pre-wrap`

3. Or implement server-side markdown rendering + DOMPurify sanitization

**CSP build blocks:** `x-html`, `eval()`, property assignments in expressions

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
│   └── search_service.py # PostgreSQL full-text search fallback
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

| File | Purpose |
|------|---------|
| `config/settings.py` | Django + Cotton + CSP + Chat config |
| `static/css/main.css` | Tailwind v4 source + theme tokens |
| `static/js/chat.js` | Alpine.js chat component |
| `templates/cotton/` | Component library (Atomic Design) |
| `templates/pages/components.html` | Component documentation page |
| `chat/` | AI chat app with providers and services |
| `portal/views.py` | Main views |

## Database

- **Local dev / Demo:** SQLite (`db.sqlite3`)
- **Docker / Production:** PostgreSQL via `DATABASE_URL`

### Reset Data (Demo Mode)

```bash
rm db.sqlite3
SECRET_KEY=dev python manage.py migrate
```

### Database Compatibility

The codebase supports both SQLite and PostgreSQL:
- Models avoid PostgreSQL-specific features for compatibility
- Search service uses simple `icontains` queries (works everywhere)
- PostgreSQL full-text search can be added later for production

## Versioning

### Pinned Dependencies

| Tool | Version | Location |
|------|---------|----------|
| Tailwind CSS | v4.1.16 | `Dockerfile`, `dev.sh` |
| Alpine.js | 3.14.9 (standard) | `static/js/alpine.min.js` |
| Ollama model | llama3.2:3b | `chat/providers/ollama.py` |

Update these in sync when upgrading.
