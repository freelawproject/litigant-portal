# Litigant Portal - Architecture

## Vision

Democratize access to justice by empowering self-represented litigants with AI-augmented legal guidance, education, and document preparation tools.

**Core Principles:**

- Global by design (i18n from the start)
- WCAG AA accessibility as requirement
- Mobile-first (users on older phones)
- Human-centered AI (augments, not replaces)

---

## Tech Stack Decisions

| Decision           | Choice                        | Rationale                                 |
| ------------------ | ----------------------------- | ----------------------------------------- |
| **Backend**        | Django                        | Team expertise, proven at scale           |
| **Components**     | Django Cotton                 | Server-rendered, no JS framework needed   |
| **Styling**        | Tailwind CSS (standalone CLI) | Utility-first, no Node.js needed          |
| **Reactivity**     | AlpineJS (standard build)     | Lightweight, supports x-html for markdown |
| **Component Docs** | Custom `/style-guide/` page   | Django-native, living documentation       |
| **A11y Testing**   | Browser DevTools + Lighthouse | No dependencies, built into browsers      |

---

## Architecture Patterns

### Component Structure (Atomic Design)

```
templates/
├── cotton/                    # Django Cotton components
│   ├── atoms/                 # Basic elements: alert, button, chat_bubble, icon, input, link, nav_link, search_input, select, typing_indicator
│   ├── molecules/             # Combinations: chat_message, logo, search_bar, search_result, topic_card
│   └── organisms/             # Complex sections: chat_window, footer, header, hero, topic_grid
├── pages/                     # Full pages (extend base.html)
└── base.html                  # Responsive base layout
```

**Component syntax:** `<c-atoms.button>`, `<c-molecules.logo>`, `<c-organisms.header>`

### Page Layout

Dashboard home with separate chat page:

```
/ (Dashboard)                    /chat/ (Chat)
┌──────────────────────┐        ┌──────────────────────┐
│ Header               │        │ Header               │
├──────────────────────┤        ├──────────────────────┤
│ Hero                 │        │ Hero (pre-chat)      │
│  How can we help?    │        │  [____search____]    │
│  [____search____]    │        ├──────────────────────┤
├──────────────────────┤        │ Chat messages        │
│ Browse by Topic      │        │ (AI streaming)       │
│ [cards grid]         │        ├──────────────────────┤
├──────────────────────┤        │ [input] [send]       │
│ Footer               │        │ (no footer)          │
└──────────────────────┘        └──────────────────────┘
```

- **Dashboard** (`/`) shows hero + topic grid + footer
- **Chat** (`/chat/`) is a full-screen chat interface (no footer, `overflow-hidden`)
- **Agent testing** (`/test/<agent_name>/`) renders chat with a specific agent

### Naming Conventions

- **Files:** `snake_case.html`
- **Cotton components:** `<c-component-name>` (kebab-case)
- **AlpineJS:** `x-data="componentName"` (camelCase)
- **CSS:** Tailwind utilities at component level

### State Flow (Django → Alpine)

Django renders initial state, Alpine handles client reactivity:

```html
<div x-data="{ expanded: false }" x-init="initWithState({{ state|safe }})">
  <!-- Alpine handles UI state, Django handles data -->
</div>
```

---

## WCAG AA Compliance

**All components must have:**

1. **Keyboard navigation** - Tab, Enter, Space, Arrows
2. **Focus indicators** - `focus:ring-2 focus:ring-offset-2`
3. **Color contrast** - 4.5:1 minimum (3:1 for large text)
4. **Touch targets** - 44x44px minimum
5. **ARIA labels** - For icon-only buttons, form associations

**Testing:** Browser DevTools (Lighthouse, axe extension) + manual testing

---

## Mobile-First Strategy

**Breakpoints:**

- Default: Mobile
- `sm:` 640px (small tablets)
- `md:` 768px (tablets)
- `lg:` 1024px (desktop)

**Key Pattern:** Single question per screen for forms

```html
<!-- Mobile: full screen question -->
<!-- Desktop: sidebar + main content -->
<div class="px-4 md:px-6 lg:max-w-2xl lg:mx-auto"></div>
```

---

## Security

- **CSP configured** - Inline handlers blocked, Alpine.js directives used
- **AlpineJS standard build** - Currently using standard build for markdown rendering (x-html). CSP build planned for production hardening.
- **django-csp** - Header management via `CSP_*` settings
- **VDP:** [free.law/vulnerability-disclosure-policy](https://free.law/vulnerability-disclosure-policy/)

---

## Key Files

| File                        | Purpose                                         |
| --------------------------- | ----------------------------------------------- |
| `config/settings.py`        | Django + Cotton config                          |
| `static/css/main.css`       | Tailwind v4 CSS source + theme tokens           |
| `static/js/theme.js`        | Alpine theme store                              |
| `static/js/chat.js`         | Alpine chat components (homePage, chatWindow)   |
| `templates/cotton/*/`       | Component library (atoms, molecules, organisms) |
| `templates/pages/home.html` | Dashboard with hero and topic grid              |
| `templates/pages/chat.html` | Full-screen chat interface                      |
| `Dockerfile`                | Multi-stage build (dev + prod)                  |
| `docker-compose.yml`        | Dev/prod profiles with SQLite                   |
| `docker-entrypoint.sh`      | Container startup commands                      |

---

## Docker

### Development

```bash
cp .env.example .env
docker compose --profile dev up
# or: make docker-dev
```

- Mounts source code for hot reload
- Tailwind CSS watch mode
- SQLite (file-based, zero config)
- Auto-generates `SECRET_KEY`

### Production

```bash
# Create secret key (see secrets/README.md)
docker compose --profile prod up
# or: make docker-prod
```

- Gunicorn WSGI server
- SQLite with WAL mode + IMMEDIATE transactions
- Docker secrets for Django secret key
- Pre-built CSS (minified)
- Non-root container user

### Architecture

```
┌──────────────────────────────────────────┐
│ docker-compose.yml                       │
├──────────────────────────────────────────┤
│ Profile: dev          Profile: prod      │
│ ┌───────────┐         ┌───────────┐      │
│ │django-dev │         │django-prod│      │
│ │ runserver │         │ gunicorn  │      │
│ │ + tailwind│         │ + SQLite  │      │
│ └───────────┘         └───────────┘      │
└──────────────────────────────────────────┘
```

---

## AI Chat

The portal includes an AI chat feature using LiteLLM with OpenAI (gpt-4o-mini by default).

### Architecture

```
User Input → POST /api/chat/send/ → Django creates message
           → GET /api/chat/stream/<session_id>/ (SSE)
           → Groq API (OpenAI-compatible)
           → StreamingHttpResponse → Alpine.js updates UI
```

### Configuration

1. Get an API key from [OpenAI](https://platform.openai.com/api-keys)
2. Add to `.env`:

```bash
OPENAI_API_KEY=sk-...                         # Required for chat
CHAT_ENABLED=true                             # Enable/disable chat feature
CHAT_MODEL=openai/gpt-4o-mini                 # LiteLLM model string
```

### Why OpenAI via LiteLLM?

- **LiteLLM** - Unified interface for 100+ LLM providers
- **Easy to swap** - Change `CHAT_MODEL` env var to switch providers (e.g. `groq/llama-3.3-70b-versatile`)
- **No local setup** - No GPU requirements, works anywhere

---

## References

- [Django Cotton](https://django-cotton.com/)
- [AlpineJS](https://alpinejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [LiteLLM](https://docs.litellm.ai/) - Unified LLM API interface
- [WCAG 2.1 Quick Ref](https://www.w3.org/WAI/WCAG21/quickref/)
- [CourtListener Frontend](https://github.com/freelawproject/courtlistener/wiki/New-Frontend-Architecture)
