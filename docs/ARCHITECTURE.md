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

| Decision           | Choice                        | Rationale                               |
| ------------------ | ----------------------------- | --------------------------------------- |
| **Backend**        | Django                        | Team expertise, proven at scale         |
| **Components**     | Django Cotton                 | Server-rendered, no JS framework needed |
| **Styling**        | Tailwind CSS (standalone CLI) | Utility-first, no Node.js needed        |
| **Reactivity**     | AlpineJS CSP build (CDN)      | Lightweight, CSP-compatible             |
| **Component Docs** | Custom `/style-guide/` page   | Django-native, living documentation     |
| **A11y Testing**   | Browser DevTools + Lighthouse | No dependencies, built into browsers    |

---

## Architecture Patterns

### Component Structure (Atomic Design)

```
templates/
├── cotton/                    # Django Cotton components
│   ├── atoms/                 # Basic elements: button, input, link, select, icon
│   ├── molecules/             # Combinations: logo, search_bar, topic_card
│   └── organisms/             # Complex sections: header, footer, hero, topic_grid
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

- **CSP configured** - No unsafe-eval/inline needed
- **AlpineJS CSP build** - Standard build requires unsafe-eval
- **django-csp** - Header management via `CSP_*` settings
- **VDP:** [free.law/vulnerability-disclosure-policy](https://free.law/vulnerability-disclosure-policy/)

---

## Key Files

| File                   | Purpose                                         |
| ---------------------- | ----------------------------------------------- |
| `config/settings.py`   | Django + Cotton config                          |
| `static/css/main.css`  | Tailwind v4 CSS source + theme tokens           |
| `static/js/theme.js`   | Alpine theme store                              |
| `static/js/chat.js`    | Alpine chat components (homePage, chatWindow)   |
| `templates/cotton/*/`  | Component library (atoms, molecules, organisms) |
| `templates/pages/home.html` | Main page with chat interface               |
| `Dockerfile`           | Multi-stage build (dev + prod)                  |
| `docker-compose.yml`   | Dev/prod profiles with Docker secrets           |
| `docker-entrypoint.sh` | Container startup commands                      |

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

The portal includes an AI chat feature using local LLMs via Ollama.

### Architecture

```
User Input → POST /chat/send/ → Django creates message
           → GET /chat/stream/<session_id>/ (SSE)
           → Ollama API (OpenAI-compatible)
           → StreamingHttpResponse → Alpine.js updates UI
```

### Ollama Setup

#### macOS (recommended for dev)

```bash
# Install via Homebrew
brew install ollama

# Pull the model
ollama pull llama3.2:3b

# Start as background service
brew services start ollama

# Or run manually
ollama serve
```

Ollama runs on `localhost:11434`. Django in Docker reaches it via `host.docker.internal:11434`.

**Why local on Mac?** Docker on macOS cannot access Apple Silicon GPU. Running Ollama locally uses Metal acceleration for ~5-10x faster inference.

#### Linux (with NVIDIA GPU)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the model
ollama pull llama3.2:3b

# Start service
sudo systemctl enable ollama
sudo systemctl start ollama
```

For Docker deployment with GPU access:

```yaml
# docker-compose.yml
services:
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

#### Linux (CPU only)

Same as above, but inference will be slower without GPU acceleration.

### Configuration

Environment variables in `.env` or `docker-compose.yml`:

```bash
CHAT_ENABLED=true           # Enable/disable chat feature
CHAT_PROVIDER=ollama        # Provider: ollama (more coming)
CHAT_MODEL=llama3.2:3b      # Model to use
OLLAMA_HOST=localhost:11434 # Ollama API endpoint
```

### Testing

```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Test a prompt
python scripts/test_markdown.py -p "What are tenant rights?"
```

---

## References

- [Django Cotton](https://django-cotton.com/)
- [AlpineJS](https://alpinejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Ollama](https://ollama.com/) - Local LLM runner
- [WCAG 2.1 Quick Ref](https://www.w3.org/WAI/WCAG21/quickref/)
- [CourtListener Frontend](https://github.com/freelawproject/courtlistener/wiki/New-Frontend-Architecture)
