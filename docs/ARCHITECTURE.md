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

Single-page chat-first design:

```
┌─────────────────────────────────────────┐
│ Header: [Logo] ... [Browse by Topic] [☰]│
├─────────────────────────────────────────┤
│                                         │
│   How can we help you today?            │
│   [________search________] [Ask]        │
│                                         │
├─────────────────────────────────────────┤
│                                         │
│   Chat messages appear here             │
│   (AI streaming responses)              │
│                                         │
├─────────────────────────────────────────┤
│ Footer                                  │
└─────────────────────────────────────────┘
```

- **Hero + Chat** on home page (no separate `/chat/` page)
- **Browse by Topic** in slide-out menu (hamburger)
- **Topic cards** accessible via menu, chat is primary focus

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
| `templates/pages/home.html` | Main page with chat interface                   |
| `Dockerfile`                | Multi-stage build (dev + prod)                  |
| `docker-compose.yml`        | Dev/prod profiles with Docker secrets           |
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
- PostgreSQL with default credentials
- Auto-generates `SECRET_KEY`

### Production

```bash
# Create secrets (see secrets/README.md)
docker compose --profile prod up
# or: make docker-prod
```

- Gunicorn WSGI server
- Docker secrets for credentials
- Pre-built CSS (minified)
- Non-root container user

### Architecture

```
┌─────────────────────────────────────────────┐
│ docker-compose.yml                          │
├─────────────────────────────────────────────┤
│ Profile: dev          Profile: prod         │
│ ┌───────────┐ ┌────┐  ┌───────────┐ ┌────┐  │
│ │django-dev │ │db- │  │django-prod│ │db- │  │
│ │ runserver │ │dev │  │ gunicorn  │ │prod│  │
│ │ + tailwind│ │    │  │           │ │    │  │
│ └───────────┘ └────┘  └───────────┘ └────┘  │
└─────────────────────────────────────────────┘
```

---

## AI Chat

The portal includes an AI chat feature using OpenAI's API with gpt-4o-mini.

### Architecture

```
User Input → POST /chat/send/ → Django creates message
           → GET /chat/stream/<session_id>/ (SSE)
           → OpenAI API
           → StreamingHttpResponse → Alpine.js updates UI
```

### Configuration

1. Get an API key from [OpenAI](https://platform.openai.com/)
2. Add to `.env`:

```bash
OPENAI_API_KEY=sk-...       # Required for chat
CHAT_ENABLED=true           # Enable/disable chat feature
CHAT_PROVIDER=openai        # Provider
CHAT_MODEL=gpt-4o-mini      # Model to use
```

---

## References

- [Django Cotton](https://django-cotton.com/)
- [AlpineJS](https://alpinejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [OpenAI API](https://platform.openai.com/docs) - LLM API
- [WCAG 2.1 Quick Ref](https://www.w3.org/WAI/WCAG21/quickref/)
- [CourtListener Frontend](https://github.com/freelawproject/courtlistener/wiki/New-Frontend-Architecture)
